#!/usr/bin/env bash
# Wrapper script to run Python commands in various environments
# Supports: .venv, pyenv, system python
#
# Priority order (first match wins):
# 1. .venv - dev container / virtualenv (has HA deps)
# 2. pyenv 3.12.12 - local dev with deps installed
# 3. pyenv default - whatever version is active
# 4. system python - fallback (may lack deps)

set -e

# Find the best available Python with dependencies
find_python() {
    # 1. Check for .venv (dev container / virtualenv)
    if [[ -x ".venv/bin/python" ]]; then
        echo ".venv/bin/python"
        return
    fi

    # 2. Check for pyenv 3.12.12 specifically (known to have deps)
    if [[ -x "$HOME/.pyenv/versions/3.12.12/bin/python" ]]; then
        echo "$HOME/.pyenv/versions/3.12.12/bin/python"
        return
    fi

    # 3. Check for pyenv with PYENV_VERSION set
    if [[ -n "$PYENV_VERSION" ]] && command -v pyenv &> /dev/null; then
        echo "pyenv exec python"
        return
    fi

    # 4. Check for pyenv default
    if command -v pyenv &> /dev/null; then
        local pyenv_python
        pyenv_python="$(pyenv which python 2>/dev/null || true)"
        if [[ -x "$pyenv_python" ]]; then
            echo "$pyenv_python"
            return
        fi
    fi

    # 5. Check for python3
    if command -v python3 &> /dev/null; then
        echo "python3"
        return
    fi

    # 6. Fall back to python
    if command -v python &> /dev/null; then
        echo "python"
        return
    fi

    echo "ERROR: No Python interpreter found" >&2
    exit 1
}

PYTHON_CMD=$(find_python)

# Run the command with all arguments
$PYTHON_CMD "$@"
