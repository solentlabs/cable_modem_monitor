# This script is a thin wrapper that executes the main Python setup script.

# Exit on error
$ErrorActionPreference = "Stop"

# Find a suitable Python interpreter
$PYTHON_CMD = "python"
if (-not (Get-Command $PYTHON_CMD -ErrorAction SilentlyContinue)) {
    $PYTHON_CMD = "python3"
    if (-not (Get-Command $PYTHON_CMD -ErrorAction SilentlyContinue)) {
        Write-Error "Error: Python not found. Please install Python 3.11+."
        exit 1
    }
}

# Get the directory of this script
$ScriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent

# Execute the main Python setup script
& $PYTHON_CMD (Join-Path $ScriptDir "setup.py")
