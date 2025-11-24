#!/bin/bash
# This script is a thin wrapper that executes the main Python setup script.

# Exit on error
set -e

# Find a suitable Python interpreter
PYTHON_CMD="python3"
if ! command -v $PYTHON_CMD &> /dev/null; then
    PYTHON_CMD="python"
    if ! command -v $PYTHON_CMD &> /dev/null; then
        echo "Error: Python not found. Please install Python 3.11+."
        exit 1
    fi
fi

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Execute the main Python setup script
$PYTHON_CMD "$SCRIPT_DIR/setup.py"
