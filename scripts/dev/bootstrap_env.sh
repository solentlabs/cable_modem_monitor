#!/bin/bash
# Bootstrap script for Cable Modem Monitor development environment
# Creates virtualenv, installs dev dependencies, and sets up a cross-platform Black shim

set -e

echo "🔧 Bootstrapping Python development environment..."

# Detect platform and set interpreter path
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OS" == "Windows_NT" ]]; then
  PYTHON_BIN="venv/Scripts/python.exe"
  echo "🪟 Detected Windows environment"

  # Write Windows-compatible shim to .vscode/black-python (no .bat extension)
  mkdir -p .vscode
  cat > .vscode/black-python <<'EOF'
@echo off
REM Cross-platform shim for Black formatter on Windows
REM Used by VS Code's Black extension to launch the formatter

%~dp0..\venv\Scripts\python.exe %*
EOF

else
  PYTHON_BIN="venv/bin/python"
  echo "🐧 Detected Unix-like environment"

  # Write Unix-compatible shim to .vscode/black-python
  mkdir -p .vscode
  cat > .vscode/black-python <<'EOF'
#!/bin/bash
# Cross-platform shim for Black formatter on Unix-like systems
# Used by VS Code's Black extension to launch the formatter

exec "${PWD}/venv/bin/python" "$@"
EOF

  # Only attempt chmod on Unix-like systems
  chmod +x .vscode/black-python || echo "⚠️ Skipping chmod — not supported on this filesystem"
fi

# Create virtual environment if missing
if [ ! -f "$PYTHON_BIN" ]; then
  echo "📦 Creating virtualenv..."
  python3 -m venv venv
fi

# Install development dependencies
echo "📚 Installing requirements-dev.txt..."
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r requirements-dev.txt

echo "✅ Environment bootstrapped successfully!"
