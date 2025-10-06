#!/bin/bash

# Interactive Citation Extractor Runner for macOS
# Double-click this file to run

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_SCRIPT="$SCRIPT_DIR/extract_citations.py"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

clear
echo "========================================"
echo "  Citation Extractor - Interactive Mode"
echo "========================================"
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed."
    echo "Please install Python 3.7 or higher from python.org"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Setting up for first time..."
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "✓ Virtual environment created"
    echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"
echo "✓ Activated"
echo ""

# Install/upgrade dependencies
echo "Checking dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r "$REQUIREMENTS"
echo "✓ Dependencies ready"
echo ""

# Prompt for input file
echo "========================================"
echo "  Step 1: Report File"
echo "========================================"
echo ""
echo "Available JSON files in this folder:"
ls -1 *.json 2>/dev/null || echo "  (no JSON files found)"
echo ""
read -p "Enter report filename (without or with .json): " REPORT_FILE

# Auto-append .json if not provided
if [[ ! "$REPORT_FILE" == *.json ]]; then
    REPORT_FILE="${REPORT_FILE}.json"
    echo "Using: $REPORT_FILE"
fi

# Check if file exists
if [ ! -f "$REPORT_FILE" ]; then
    echo ""
    echo "ERROR: File '$REPORT_FILE' not found!"
    echo ""
    read -p "Press Enter to exit..."
    deactivate
    exit 1
fi

# Extract query from JSON to suggest as filename
echo ""
echo "Analyzing report..."
QUERY=$(python3 -c "import json; data=json.load(open('$REPORT_FILE')); print(data.get('query', 'citations_dois'))" 2>/dev/null)

# Clean query for use as filename (remove special chars, limit length)
SUGGESTED_NAME=$(echo "$QUERY" | sed 's/[^a-zA-Z0-9 ]//g' | sed 's/ /_/g' | cut -c1-50)
if [ -z "$SUGGESTED_NAME" ]; then
    SUGGESTED_NAME="citations_dois"
fi

# Prompt for output file
echo ""
echo "========================================"
echo "  Step 2: Output File"
echo "========================================"
echo ""
echo "Query: $QUERY"
echo ""
read -p "Enter output filename (default: ${SUGGESTED_NAME}): " OUTPUT_FILE

# Use suggested name if empty
if [ -z "$OUTPUT_FILE" ]; then
    OUTPUT_FILE="${SUGGESTED_NAME}.txt"
else
    # Auto-append .txt if not provided
    if [[ ! "$OUTPUT_FILE" == *.txt ]]; then
        OUTPUT_FILE="${OUTPUT_FILE}.txt"
    fi
fi
echo "Using: $OUTPUT_FILE"

# Run the Python script
echo ""
echo "========================================"
echo "  Processing..."
echo "========================================"
echo ""
python "$PYTHON_SCRIPT" "$REPORT_FILE" "$OUTPUT_FILE"

# Deactivate virtual environment
deactivate

echo ""
echo "========================================"
echo "  Complete!"
echo "========================================"
echo ""
echo "Output saved to: $OUTPUT_FILE"
echo ""
read -p "Press Enter to exit..."