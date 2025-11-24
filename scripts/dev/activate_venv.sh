***REMOVED***!/bin/bash
***REMOVED*** VS Code terminal auto-activation script for Bash/Zsh
***REMOVED*** This runs automatically when you open a terminal in VS Code

VENV_PATH=".venv"
ACTIVATE_SCRIPT="$VENV_PATH/bin/activate"

if [ -f "$ACTIVATE_SCRIPT" ]; then
    ***REMOVED*** .venv exists, activate it and show "next steps" message
    source "$ACTIVATE_SCRIPT"
    clear
    echo ""
    cat "${BASH_SOURCE%/*}/next_steps.txt"
    echo ""
else
    ***REMOVED*** .venv doesn't exist or isn't set up - show helpful instructions
    cat "${BASH_SOURCE%/*}/welcome_message.txt"
    echo ""
fi
