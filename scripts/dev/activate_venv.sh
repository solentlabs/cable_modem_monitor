#!/bin/bash
# VS Code terminal auto-activation script for Bash/Zsh
# This runs automatically when you open a terminal in VS Code

VENV_PATH=".venv"
ACTIVATE_SCRIPT="$VENV_PATH/bin/activate"

if [ -f "$ACTIVATE_SCRIPT" ]; then
    # .venv exists and is set up - activate it
    source "$ACTIVATE_SCRIPT"
else
    # .venv doesn't exist or isn't set up - show helpful instructions
    echo ""
    echo "👋 Welcome to Cable Modem Monitor!"
    echo ""
    echo "📦 Setup required - .venv not found"
    echo ""
    echo -e "\033[32mRun this command to set up your development environment:\033[0m"
    echo -e "\033[1m    ./scripts/setup.sh\033[0m"
    echo ""
    echo "This will:"
    echo "  • Create Python virtual environment (.venv)"
    echo "  • Install all dependencies"
    echo "  • Set up pre-commit hooks"
    echo "  • Takes ~2 minutes"
    echo ""
    echo "After setup, close and reopen this terminal."
    echo ""
fi
