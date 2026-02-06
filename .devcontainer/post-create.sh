#!/bin/bash
# Post-create setup for dev container
# This runs once when the container is first created

set -e

echo "📦 Installing Python dependencies..."
pip install --root-user-action=ignore -r requirements-dev.txt
pip install --root-user-action=ignore -r tests/requirements.txt

# Install CodeQL CLI if not already installed
if ! command -v codeql > /dev/null 2>&1; then
    echo "🔍 Installing CodeQL CLI..."
    wget -q https://github.com/github/codeql-cli-binaries/releases/latest/download/codeql-linux64.zip
    unzip -q codeql-linux64.zip -d /usr/local
    rm codeql-linux64.zip
    ln -s /usr/local/codeql/codeql /usr/local/bin/codeql
    echo "✅ CodeQL CLI installed"
fi

if [ -d "./cable-modem-monitor-ql" ]; then
    echo "📦 Installing CodeQL dependencies..."
    codeql pack install ./cable-modem-monitor-ql
else
    echo "⚠️  CodeQL pack directory not found, skipping pack installation"
fi

echo "📦 Installing pre-commit..."
pip install --root-user-action=ignore --break-system-packages pre-commit

# Only install hooks if we're in a git repo (skip in CI builds)
if git rev-parse --git-dir > /dev/null 2>&1; then
    echo "📦 Installing pre-commit hooks..."
    pre-commit install
else
    echo "⚠️  Not in a git repo, skipping pre-commit hook installation"
fi

echo ""
echo "✅ Dev environment ready!"
echo ""
echo "📖 Quick Start:"
echo "  • Run tests: Press Ctrl+Shift+P → 'Tasks: Run Task' → 'Run All Tests'"
echo "  • Start HA: Press Ctrl+Shift+P → 'Tasks: Run Task' → 'HA: Start (Fresh)'"
echo "  • View all tasks: Press Ctrl+Shift+P → 'Tasks: Run Task'"
echo ""
