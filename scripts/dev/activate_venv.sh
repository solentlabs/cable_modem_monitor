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
    echo -e "\033[36mWelcome to Cable Modem Monitor!\033[0m"
    echo ""
    echo -e "\033[33mChoose your development environment:\033[0m"
    echo ""
    echo -e "\033[32mOption 1: Local Python (Fastest)\033[0m"
    echo -e "\033[1m  Run: ./scripts/setup.sh\033[0m"
    echo "  Or: Ctrl+Shift+P -> Tasks -> 'Setup Local Python Environment'"
    echo "  - Takes ~2 minutes"
    echo "  - Fastest test execution"
    echo "  - After setup, close and reopen this terminal"
    echo ""
    echo -e "\033[32mOption 2: Dev Container (Zero Setup)\033[0m"
    echo -e "\033[1m  Press F1 -> 'Dev Containers: Reopen in Container'\033[0m"
    echo "  - Takes ~5 minutes first time"
    echo "  - All dependencies pre-installed"
    echo "  - Guaranteed consistency with CI"
    echo ""
    echo "See docs/GETTING_STARTED.md for detailed comparison"
    echo ""
fi
