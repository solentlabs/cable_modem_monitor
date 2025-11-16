#!/bin/bash
# Cable Modem Monitor - Automated Development Environment Setup
# This script sets up everything you need to start developing

# Exit on error
set -e

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo "=========================================="
echo "Cable Modem Monitor - Development Setup"
echo "=========================================="
echo ""

# Function to print colored output
print_step() {
    echo -e "${CYAN}➜${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "custom_components/cable_modem_monitor/__init__.py" ]; then
    print_error "Not in project root directory"
    echo ""
    echo "Please run this script from the cable_modem_monitor/ directory:"
    echo "  cd /path/to/cable_modem_monitor"
    echo "  ./scripts/setup.sh"
    echo ""
    exit 1
fi

print_success "Running from project root"
echo ""

# Step 1: Check Python version
print_step "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 not found"
    echo "Please install Python 3.11+ first"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
    print_success "Python $PYTHON_VERSION found (requirement: 3.11+)"
else
    print_error "Python $PYTHON_VERSION found, but 3.11+ required"
    echo "Please install Python 3.11 or newer"
    exit 1
fi
echo ""

# Step 2: Check for python3-venv
print_step "Checking for python3-venv module..."
if python3 -c "import venv" 2> /dev/null; then
    print_success "python3-venv module available"
else
    print_error "python3-venv module not installed"
    echo ""
    echo "Install it with:"
    echo "  sudo apt install python3-venv"
    echo ""
    exit 1
fi
echo ""

# Step 3: Clean up dual venv situation
if [ -d "venv" ]; then
    print_warning "Found venv/ directory, removing it in favor of .venv/"
    rm -rf venv
    print_success "Removed venv/ directory"
    echo ""
fi

# Step 4: Create virtual environment
if [ ! -d ".venv" ]; then
    print_step "Creating virtual environment..."
    python3 -m venv .venv
    print_success "Virtual environment created"
    echo ""
else
    print_success "Virtual environment already exists"
    echo ""
fi

# Step 5: Upgrade pip
print_step "Upgrading pip..."
.venv/bin/pip install --upgrade pip --quiet
print_success "pip upgraded"
echo ""

# Step 6: Install dependencies
print_step "Installing development dependencies..."
echo "  (This may take a minute...)"
.venv/bin/pip install -r requirements-dev.txt --quiet
print_success "Development dependencies installed"
echo ""

print_step "Installing test dependencies..."
.venv/bin/pip install -r tests/requirements.txt --quiet
print_success "Test dependencies installed"
echo ""

# Step 7: Install pre-commit hooks
print_step "Setting up pre-commit hooks..."
if .venv/bin/pip show pre-commit &> /dev/null; then
    .venv/bin/pre-commit install --install-hooks
    print_success "Pre-commit hooks installed"
else
    .venv/bin/pip install pre-commit --quiet
    .venv/bin/pre-commit install --install-hooks
    print_success "Pre-commit installed and configured"
fi
echo ""

# Step 8: Check Docker (optional)
print_step "Checking Docker..."
if command -v docker &> /dev/null; then
    if docker ps &> /dev/null; then
        DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
        print_success "Docker $DOCKER_VERSION is running"
    else
        print_warning "Docker installed but not running"
        echo "  Start Docker Desktop to use dev containers"
    fi
else
    print_warning "Docker not installed"
    echo "  Optional: Install Docker Desktop for containerized development"
fi
echo ""

# Step 9: Check VS Code (optional)
print_step "Checking VS Code..."
if command -v code &> /dev/null; then
    CODE_VERSION=$(code --version | head -1)
    print_success "VS Code $CODE_VERSION installed"

    # Check for required extensions
    EXTENSIONS=$(code --list-extensions 2>/dev/null || echo "")
    MISSING_EXTENSIONS=()

    if ! echo "$EXTENSIONS" | grep -q "ms-python.python"; then
        MISSING_EXTENSIONS+=("ms-python.python")
    fi
    if ! echo "$EXTENSIONS" | grep -q "ms-vscode-remote.remote-containers"; then
        MISSING_EXTENSIONS+=("ms-vscode-remote.remote-containers")
    fi

    if [ ${#MISSING_EXTENSIONS[@]} -gt 0 ]; then
        print_warning "Some recommended VS Code extensions are missing:"
        for ext in "${MISSING_EXTENSIONS[@]}"; do
            echo "    - $ext"
        done
        echo ""
        echo "  Install them with:"
        for ext in "${MISSING_EXTENSIONS[@]}"; do
            echo "    code --install-extension $ext"
        done
    else
        print_success "All recommended VS Code extensions installed"
    fi
else
    print_warning "VS Code not installed"
    echo "  Optional: Install VS Code for better development experience"
fi
echo ""

# Step 10: Run a quick test
print_step "Running quick test to verify setup..."
if .venv/bin/pytest tests/parsers/netgear/test_cm600.py::test_fixtures_exist -q &> /dev/null; then
    print_success "Tests can run successfully"
else
    print_warning "Test execution had issues (may need additional setup)"
fi
echo ""

# Step 11: Create .python-version file
if [ ! -f ".python-version" ]; then
    print_step "Creating .python-version file..."
    echo "3.11.0" > .python-version
    print_success "Created .python-version file"
    echo ""
fi

echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo -e "${GREEN}✓ Your development environment is ready!${NC}"
echo ""
echo "What's installed:"
echo "  • Python virtual environment (.venv/)"
echo "  • All development dependencies"
echo "  • Pre-commit hooks"
echo "  • Code formatters and linters"
echo ""
echo "Next steps:"
echo ""
echo "  ${CYAN}1. Run tests:${NC}"
echo "     make test"
echo "     # or: .venv/bin/pytest tests/"
echo ""
echo "  ${CYAN}2. Run code quality checks:${NC}"
echo "     make lint"
echo "     make format"
echo ""
echo "  ${CYAN}3. Start Docker development environment:${NC}"
echo "     make docker-start"
echo "     # Then open http://localhost:8123"
echo ""
echo "  ${CYAN}4. Open in VS Code:${NC}"
echo "     code ."
echo "     # Press F1 → 'Dev Containers: Reopen in Container'"
echo ""
echo "  ${CYAN}5. Verify your setup:${NC}"
echo "     ./scripts/verify-setup.sh"
echo ""
echo "Documentation:"
echo "  • Quick Start:  docs/DEVELOPER_QUICKSTART.md"
echo "  • Contributing: CONTRIBUTING.md"
echo "  • Architecture: docs/ARCHITECTURE_ROADMAP.md"
echo ""
echo "Happy coding! 🚀"
echo ""
