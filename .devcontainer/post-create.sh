#!/bin/bash
# Post-create setup for dev container
# This runs once when the container is first created

set -e

echo "📦 Creating Python virtual environment..."
python3.12 -m venv .venv

echo "📦 Installing Python dependencies..."
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements-dev.txt
.venv/bin/pip install --quiet -r tests/requirements.txt

echo "📦 Installing solentlabs packages (editable)..."
.venv/bin/pip install --quiet -e packages/cable_modem_monitor_core
.venv/bin/pip install --quiet -e packages/cable_modem_monitor_catalog
.venv/bin/pip install --quiet -e packages/cable_modem_monitor_catalog_tools

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
.venv/bin/pip install --quiet pre-commit

# Only install hooks if we're in a git repo (skip in CI builds)
if git rev-parse --git-dir > /dev/null 2>&1; then
    echo "📦 Installing pre-commit hooks..."
    .venv/bin/pre-commit install
else
    echo "⚠️  Not in a git repo, skipping pre-commit hook installation"
fi

echo ""
echo "✅ Dev environment ready!"
echo ""
echo "📖 Quick Start:"
echo "  • Run tests: Press Ctrl+Shift+P → 'Tasks: Run Task' → 'Test: All'"
echo "  • Start HA: Press Ctrl+Shift+P → 'Tasks: Run Task' → 'HA: Start'"
echo "  • View all tasks: Press Ctrl+Shift+P → 'Tasks: Run Task'"
echo ""
