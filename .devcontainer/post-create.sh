#!/bin/bash
# Post-create setup for dev container
# This runs once when the container is first created

set -e

echo "📦 Installing Python dependencies..."
pip install -r requirements-dev.txt

echo "📦 Installing CodeQL dependencies..."
codeql pack install ./cable-modem-monitor-ql

echo "📦 Installing pre-commit..."
pip install --break-system-packages pre-commit

echo "📦 Installing pre-commit hooks..."
pre-commit install


# Install CodeQL CLI if not already installed
if ! command -v codeql > /dev/null 2>&1; then
    echo "🔍 Installing CodeQL CLI..."
    wget -q https://github.com/github/codeql-cli-binaries/releases/latest/download/codeql-linux64.zip
    unzip -q codeql-linux64.zip -d /usr/local
    rm codeql-linux64.zip
    ln -s /usr/local/codeql/codeql /usr/local/bin/codeql
    echo "✅ CodeQL CLI installed"
fi

echo ""
echo "✅ Dev environment ready!"
echo ""
echo "📖 Quick Start:"
echo "  • Run tests: Press Ctrl+Shift+P → 'Tasks: Run Task' → 'Run All Tests'"
echo "  • Start HA: Press Ctrl+Shift+P → 'Tasks: Run Task' → 'HA: Start (Fresh)'"
echo "  • View all tasks: Press Ctrl+Shift+P → 'Tasks: Run Task'"
echo ""
