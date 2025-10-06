#!/usr/bin/env python3
"""
Extract citations from report and fetch DOIs from Semantic Scholar API.
Usage: python extract_citations.py <report.json> [output.txt]
"""

import json
import sys
import time
import requests
import re
from pathlib import Path
from typing import Set, Dict, Any, Optional, List


def justify_text(text, width):
    """Justify text to fit exactly within specified width."""
    words = text.split()
    if len(words) <= 1 or len(text) >= width:
        return text.ljust(width)
    
    total_chars = sum(len(word) for word in words)
    total_gaps = len(words) - 1
    total_spaces_needed = width - total_chars
    
    if total_gaps == 0:
        return text.ljust(width)
    
    spaces_per_gap = total_spaces_needed // total_gaps
    extra_spaces = total_spaces_needed % total_gaps
    
    result = []
    for i, word in enumerate(words[:-1]):
        result.append(word)
        result.append(' ' * (spaces_per_gap + (1 if i < extra_spaces else 0)))
    result.append(words[-1])
    
    return ''.join(result)


def wrap_text_justified(text, width, justify=False):
    """Wrap text to fit within specified width, optionally with justification."""
    words = text.split()
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        word_len = len(word)
        if current_length + word_len + len(current_line) <= width:
            current_line.append(word)
            current_length += word_len
        else:
            if current_line:
                line_text = ' '.join(current_line)
                lines.append(justify_text(line_text, width) if justify else line_text)
            current_line = [word]
            current_length = word_len
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines if lines else ['']


def format_table(table_data, width):
    """Format table data into readable text lines."""
    lines = []
    
    if not table_data:
        return lines
    
    title = table_data.get('title', 'Table')
    if title:
        lines.append(f"TABLE: {title}")
        lines.append("")
    
    columns = table_data.get('columns', [])
    rows = table_data.get('rows', [])
    cells = table_data.get('cells', {})
    
    if not columns or not rows:
        lines.append("(Table data structure not fully populated)")
        return lines
    
    # Simple table formatting - just show key information
    lines.append("Table Contents:")
    for row in rows[:5]:  # Show first 5 rows as preview
        row_id = row.get('id', '')
        display_val = row.get('displayValue', 'N/A')
        lines.append(f"  • {display_val}")
    
    if len(rows) > 5:
        lines.append(f"  ... and {len(rows) - 5} more rows")
    
    return lines


def clean_text(text: str) -> str:
    """Remove citation artifacts and clean the text."""
    import re
    
    # Remove Paper XML tags but keep the citation
    # Pattern: <Paper corpusId="..." paperTitle="(Author, Year)" isShortName></Paper>
    text = re.sub(r'<Paper[^>]*paperTitle="([^"]+)"[^>]*></Paper>', r'\1', text)
    
    # Remove any remaining XML-like tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def extract_sections_with_content(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract sections with their text content and citations."""
    sections = []
    
    if 'sections' in report_data:
        for section in report_data['sections']:
            section_info = {
                'title': section.get('title', 'Untitled Section'),
                'text': clean_text(section.get('text', '')),
                'table': section.get('table'),  # Include table if present
                'citations': []
            }
            
            if 'citations' in section:
                for citation in section['citations']:
                    if 'corpusId' in citation and 'id' in citation:
                        corpus_id = str(citation['corpusId'])
                        section_info['citations'].append({
                            'corpus_id': corpus_id,
                            'display': citation.get('id', ''),
                            'paper': citation.get('paper', {})
                        })
            
            sections.append(section_info)
    
    return sections


def parse_citation_text_file(text_file='trialreport.txt'):
    """Parse a citation text file and return a dict of citation_name -> doi."""
    citation_map = {}
    text_path = Path(text_file)
    
    if not text_path.exists():
        return citation_map
    
    print(f"Found existing citation file: {text_file}")
    print("Parsing citations...")
    
    with open(text_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or '->' not in line:
                continue
            
            # Parse format: (Author, Year) -> DOI
            match = re.match(r'\(([^)]+)\)\s*->\s*(.+)', line)
            if match:
                citation_name = match.group(1).strip()
                doi = match.group(2).strip()
                citation_map[citation_name] = doi
    
    print(f"Loaded {len(citation_map)} citations from file\n")
    return citation_map


def find_corpus_id_by_doi(doi: str) -> Optional[str]:
    """Look up corpus ID from DOI using Semantic Scholar API."""
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
    params = {"fields": "corpusId"}
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        corpus_id = data.get('corpusId')
        return str(corpus_id) if corpus_id else None
    except:
        return None


def load_doi_cache(cache_file='doi_cache.json'):
    """Load existing DOI cache from file."""
    cache_path = Path(cache_file)
    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not read cache file, starting fresh")
            return {}
    return {}


def save_doi_cache(cache, cache_file='doi_cache.json'):
    """Save DOI cache to file."""
    cache_path = Path(cache_file)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def fetch_doi_from_semantic_scholar(corpus_id: str, max_retries: int = 5) -> Optional[str]:
    """Fetch DOI for a paper using Semantic Scholar API with retry logic."""
    url = f"https://api.semanticscholar.org/graph/v1/paper/CorpusID:{corpus_id}"
    params = {"fields": "externalIds,title"}
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            # Extract DOI from externalIds
            external_ids = data.get('externalIds', {})
            doi = external_ids.get('DOI')
            
            return doi
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # Rate limited - wait longer before retry
                wait_time = (2 ** attempt) * 3  # Exponential backoff: 3s, 6s, 12s, 24s, 48s
                if attempt < max_retries - 1:
                    print(f"Rate limited, waiting {wait_time}s...", end=' ', flush=True)
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Rate limited after {max_retries} attempts", file=sys.stderr)
                    return None
            else:
                print(f"HTTP {e.response.status_code} error", file=sys.stderr)
                return None
        
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}", file=sys.stderr)
            return None
    
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_citations.py <report.json> [output.txt]")
        print("\nExample:")
        print("  python extract_citations.py report.json citations_dois.txt")
        sys.exit(1)
    
    report_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('citations_dois.txt')
    
    # Validate input file
    if not report_path.exists():
        print(f"Error: Report file not found: {report_path}")
        sys.exit(1)
    
    # Load report
    print(f"Loading report from: {report_path}")
    with open(report_path, 'r', encoding='utf-8') as f:
        report_data = json.load(f)
    
    # Extract query
    query = report_data.get('query', 'No query found')
    
    # Extract sections with content
    print("Extracting sections and citations from report...")
    sections = extract_sections_with_content(report_data)
    
    # Collect all unique corpus IDs
    unique_corpus_ids = set()
    for section in sections:
        for citation in section['citations']:
            unique_corpus_ids.add(citation['corpus_id'])
    
    total_unique = len(unique_corpus_ids)
    print(f"Found {total_unique} unique citations\n")
    
    # Fetch DOIs (with caching to avoid duplicate API calls)
    print("Fetching DOIs from Semantic Scholar API...")
    print("Loading cache...")
    
    # Load existing cache
    doi_cache = load_doi_cache()
    
    # Try to import from text file if it exists
    citation_text_map = parse_citation_text_file('trialreport.txt')
    
    # Match text file citations with current citations to populate cache
    if citation_text_map:
        print("Matching text file citations with current report...")
        imported = 0
        for section in sections:
            for citation in section['citations']:
                corpus_id = citation['corpus_id']
                display_name = citation['display']
                
                # If we have this citation in the text file and not in cache
                if display_name in citation_text_map and corpus_id not in doi_cache:
                    doi = citation_text_map[display_name]
                    doi_cache[corpus_id] = doi
                    imported += 1
        
        if imported > 0:
            print(f"Imported {imported} DOIs from text file into cache")
            save_doi_cache(doi_cache)
    
    cached_count = 0
    fetch_count = 0
    
    # Check which corpus IDs need fetching
    to_fetch = []
    for corpus_id in unique_corpus_ids:
        if corpus_id in doi_cache:
            cached_count += 1
        else:
            to_fetch.append(corpus_id)
    
    print(f"Found {cached_count} papers in cache")
    print(f"Need to fetch {len(to_fetch)} new papers\n")
    
    # Fetch DOIs for papers not in cache
    for i, corpus_id in enumerate(to_fetch, 1):
        print(f"[{i}/{len(to_fetch)}] Fetching CorpusID {corpus_id}...", end=' ')
        
        doi = fetch_doi_from_semantic_scholar(corpus_id)
        doi_cache[corpus_id] = doi
        fetch_count += 1
        
        if doi:
            print(f"✓ {doi}")
        else:
            print("✗ No DOI")
        
        # Rate limiting - increased to avoid 429 errors
        if i < len(to_fetch):
            time.sleep(2.0)
    
    # Save updated cache
    if fetch_count > 0:
        print(f"\nSaving {fetch_count} new entries to cache...")
        save_doi_cache(doi_cache)
        print("✓ Cache updated")
    
    # Build alphabetical reference list
    all_references = {}  # display_name -> doi
    
    for section in sections:
        for citation in section['citations']:
            display_name = citation['display']
            corpus_id = citation['corpus_id']
            doi = doi_cache.get(corpus_id)
            
            if display_name not in all_references:
                all_references[display_name] = doi
    
    sorted_refs = sorted(all_references.items())
    
    # Write formatted output
    print(f"\nWriting to: {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        left_width = 95
        right_width = 80
        
        # Build all left content first
        left_content = []
        
        # Header
        left_content.append("="*left_width)
        left_content.append("RESEARCH QUERY")
        left_content.append("="*left_width)
        
        # Query
        query_lines = wrap_text_justified(query, left_width - 1)
        left_content.extend(query_lines)
        left_content.append("="*left_width)
        
        # All sections
        for section in sections:
            section_title = section['title']
            section_text = section['text']
            section_table = section['table']
            
            # Section header
            left_content.append("-"*left_width)
            left_content.append(f"SECTION: {section_title}")
            left_content.append("-"*left_width)
            left_content.append("")
            
            # Section text (justified)
            if section_text:
                text_lines = wrap_text_justified(section_text, left_width - 1, justify=True)
                left_content.extend(text_lines)
                left_content.append("")
            
            # Section table if present
            if section_table:
                left_content.append("")
                table_lines = format_table(section_table, left_width - 1)
                left_content.extend(table_lines)
                left_content.append("")
        
        left_content.append("="*left_width)
        
        # Build all right content (references)
        right_content = []
        right_content.append("="*right_width)
        right_content.append("")
        right_content.append("="*right_width)
        right_content.append("")
        right_content.append("="*right_width)
        right_content.append("REFERENCES (Alphabetical)")
        right_content.append("="*right_width)
        
        for ref_name, ref_doi in sorted_refs:
            if ref_doi:
                doi_url = f"https://doi.org/{ref_doi}"
            else:
                doi_url = "NO DOI FOUND"
            right_content.append(f"{ref_name} -> {doi_url}")
        
        right_content.append("="*right_width)
        
        # Write both columns in parallel
        max_lines = max(len(left_content), len(right_content))
        for i in range(max_lines):
            left = left_content[i] if i < len(left_content) else ""
            right = right_content[i] if i < len(right_content) else ""
            f.write(left.ljust(left_width) + " | " + right + "\n")
    
    # Print summary
    successful = sum(1 for doi in doi_cache.values() if doi)
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total unique citations: {total_unique}")
    print(f"From cache: {cached_count}")
    print(f"Newly fetched: {fetch_count}")
    print(f"DOIs found: {successful}")
    print(f"No DOI: {total_unique - successful}")
    print(f"\nCache file: doi_cache.json")
    print(f"Output saved to: {output_path}")
    print("\n✓ Script completed successfully")
    
    # Exit cleanly
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)