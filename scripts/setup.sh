#!/bin/bash
# This script is a thin wrapper that executes the main Python setup script.

# Exit on error
set -e

# Initialize pyenv if available (for Python version management)
if [ -d "$HOME/.pyenv" ]; then
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"
fi

# Find a suitable Python interpreter
# Prefer 'python' (works with pyenv shims) over 'python3' (system default)
if command -v python &> /dev/null; then
    PYTHON_CMD="python"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo "Error: Python not found. Please install Python 3.12+."
    exit 1
fi

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Execute the main Python setup script
$PYTHON_CMD "$SCRIPT_DIR/setup.py"
