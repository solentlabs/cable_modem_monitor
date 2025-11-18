#!/bin/bash
# Bootstrap script for Cable Modem Monitor development environment
# Creates virtualenv, installs dev dependencies, and sets up cross-platform Black shim

set -e

echo "🔧 Bootstrapping Python development environment..."

# Detect platform and set interpreter path
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OS" == "Windows_NT" ]]; then
  PYTHON_BIN="venv/Scripts/python.exe"
  SHIM_PATH=".vscode/black-python.bat"
  echo "🪟 Detected Windows environment"
else
  PYTHON_BIN="venv/bin/python"
  SHIM_PATH=".vscode/black-python"
  echo "🐧 Detected Unix-like environment"
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

# Create Black interpreter shim
echo "🛠️ Creating Black formatter shim at $SHIM_PATH..."
mkdir -p .vscode

if [[ "$SHIM_PATH" == *.bat ]]; then
  cat > "$SHIM_PATH" <<EOF
@echo off
REM Cross-platform shim for Black formatter on Windows
REM Used by VS Code's Black extension to launch the formatter

%~dp0..\\venv\\Scripts\\python.exe %*
EOF
else
  cat > "$SHIM_PATH" <<EOF
#!/bin/bash
# Cross-platform shim for Black formatter on Unix-like systems
# Used by VS Code's Black extension to launch the formatter

exec "\${PWD}/venv/bin/python" "\$@"
EOF
  chmod +x "$SHIM_PATH"
fi

echo "✅ Environment bootstrapped successfully!"
