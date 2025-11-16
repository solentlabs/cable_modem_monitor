#!/bin/bash
# Cable Modem Monitor - Development Environment Verification Script
# This script checks that your development environment is properly configured

# Don't exit on errors - we're checking for them!
set +e

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASS=0
FAIL=0
WARN=0
OPTIONAL_FAIL=0

echo ""
echo "=========================================="
echo "Cable Modem Monitor - Setup Verification"
echo "=========================================="
echo ""

# Function to print status
print_status() {
    local status=$1
    local message=$2
    local optional=${3:-false}

    if [ "$status" = "pass" ]; then
        echo -e "${GREEN}✓${NC} $message"
        ((PASS++))
    elif [ "$status" = "fail" ]; then
        if [ "$optional" = "true" ]; then
            echo -e "${YELLOW}○${NC} $message (optional)"
            ((OPTIONAL_FAIL++))
        else
            echo -e "${RED}✗${NC} $message"
            ((FAIL++))
        fi
    elif [ "$status" = "warn" ]; then
        echo -e "${YELLOW}⚠${NC} $message"
        ((WARN++))
    else
        echo -e "${BLUE}ℹ${NC} $message"
    fi
}

echo "=== System Requirements ==="
echo ""

# Check Python version
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
        print_status "pass" "Python $PYTHON_VERSION installed (requirement: 3.11+)"
    else
        print_status "fail" "Python $PYTHON_VERSION found, but 3.11+ required"
    fi
else
    print_status "fail" "Python 3 not found in PATH"
fi

# Check for python3-venv
if python3 -c "import venv" 2> /dev/null; then
    print_status "pass" "python3-venv module available"
else
    print_status "fail" "python3-venv module not installed (run: sudo apt install python3-venv)"
fi

# Check Docker
if command -v docker &> /dev/null; then
    if docker ps &> /dev/null; then
        DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
        print_status "pass" "Docker $DOCKER_VERSION installed and running"
    else
        print_status "fail" "Docker installed but not running (start Docker Desktop)"
    fi
else
    print_status "fail" "Docker not found in PATH"
fi

# Check Git
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | awk '{print $3}')
    print_status "pass" "Git $GIT_VERSION installed"

    # Check Git config
    if git config user.name &> /dev/null && git config user.email &> /dev/null; then
        GIT_NAME=$(git config user.name)
        GIT_EMAIL=$(git config user.email)
        print_status "pass" "Git configured ($GIT_NAME <$GIT_EMAIL>)"
    else
        print_status "warn" "Git not configured (run: git config --global user.name/email)"
    fi
else
    print_status "fail" "Git not found in PATH"
fi

echo ""
echo "=== Project Environment ==="
echo ""

# Check if we're in the right directory
if [ -f "custom_components/cable_modem_monitor/__init__.py" ]; then
    print_status "pass" "Running from project root directory"
else
    print_status "fail" "Not in project root directory (run from cable_modem_monitor/)"
    echo ""
    echo "Please cd to the cable_modem_monitor directory first"
    exit 1
fi

# Check for .venv
if [ -d ".venv" ]; then
    print_status "pass" "Virtual environment '.venv/' exists"

    # Check if .venv has dependencies
    if [ -f ".venv/bin/pytest" ]; then
        print_status "pass" "pytest installed in .venv"
    else
        print_status "fail" "pytest not found in .venv (run: .venv/bin/pip install -r tests/requirements.txt)"
    fi

    if [ -f ".venv/bin/black" ]; then
        print_status "pass" "black formatter installed in .venv"
    else
        print_status "fail" "black not found in .venv (run: .venv/bin/pip install -r requirements-dev.txt)"
    fi

    if [ -f ".venv/bin/ruff" ]; then
        print_status "pass" "ruff linter installed in .venv"
    else
        print_status "fail" "ruff not found in .venv (run: .venv/bin/pip install -r requirements-dev.txt)"
    fi
else
    print_status "fail" "Virtual environment '.venv/' not found (run: python3 -m venv .venv)"
fi

# Check for venv (potential confusion)
if [ -d "venv" ]; then
    print_status "warn" "Both .venv/ and venv/ exist - consider removing venv/ to avoid confusion"
fi

# Check pre-commit
if [ -d ".git/hooks" ]; then
    if [ -f ".git/hooks/pre-commit" ] && grep -q "pre-commit" ".git/hooks/pre-commit" 2>/dev/null; then
        print_status "pass" "Pre-commit hooks installed"
    else
        print_status "warn" "Pre-commit hooks not installed (run: pre-commit install)"
    fi
else
    print_status "fail" "Not a git repository"
fi

echo ""
echo "=== VS Code Configuration ==="
echo ""

# Check VS Code
if command -v code &> /dev/null; then
    CODE_VERSION=$(code --version | head -1)
    print_status "pass" "VS Code installed ($CODE_VERSION)"

    # Check for required extensions
    EXTENSIONS=$(code --list-extensions 2>/dev/null || echo "")

    if echo "$EXTENSIONS" | grep -q "ms-python.python"; then
        print_status "pass" "Python extension installed"
    else
        print_status "fail" "Python extension not installed (install: ms-python.python)" "true"
    fi

    if echo "$EXTENSIONS" | grep -q "ms-python.vscode-pylance"; then
        print_status "pass" "Pylance extension installed"
    else
        print_status "fail" "Pylance extension not installed (install: ms-python.vscode-pylance)" "true"
    fi

    if echo "$EXTENSIONS" | grep -q "ms-vscode-remote.remote-containers"; then
        print_status "pass" "Dev Containers extension installed"
    else
        print_status "fail" "Dev Containers extension not installed (install: ms-vscode-remote.remote-containers)" "true"
    fi

    if echo "$EXTENSIONS" | grep -q "charliermarsh.ruff"; then
        print_status "pass" "Ruff extension installed"
    else
        print_status "fail" "Ruff extension not installed (install: charliermarsh.ruff)" "true"
    fi
else
    print_status "fail" "VS Code not found in PATH" "true"
fi

# Check VS Code settings
if [ -f ".vscode/settings.json" ]; then
    print_status "pass" ".vscode/settings.json exists"

    if grep -q ".venv/bin/python" ".vscode/settings.json"; then
        print_status "pass" "VS Code configured to use .venv/bin/python"
    else
        print_status "warn" "VS Code may not be using correct Python interpreter"
    fi
else
    print_status "fail" ".vscode/settings.json not found"
fi

echo ""
echo "=== Functional Tests ==="
echo ""

# Test if pytest can run
if [ -f ".venv/bin/pytest" ]; then
    if .venv/bin/pytest --collect-only tests/ &> /dev/null; then
        TEST_COUNT=$(.venv/bin/pytest --collect-only tests/ 2>/dev/null | grep "test session starts" -A 1 | tail -1 | awk '{print $2}')
        print_status "pass" "pytest can discover tests ($TEST_COUNT items)"
    else
        print_status "fail" "pytest cannot collect tests (check dependencies)"
    fi
else
    print_status "fail" "Cannot run pytest - not installed in .venv"
fi

# Test if a simple test passes
if [ -f ".venv/bin/pytest" ]; then
    echo -n "  Running quick test... "
    if .venv/bin/pytest tests/parsers/netgear/test_cm600.py::test_fixtures_exist -q &> /dev/null; then
        echo -e "${GREEN}✓ Tests can run${NC}"
        ((PASS++))
    else
        echo -e "${RED}✗ Test execution failed${NC}"
        ((FAIL++))
    fi
fi

# Test if Make commands work
if command -v make &> /dev/null; then
    print_status "pass" "Make utility available"
else
    print_status "warn" "Make not installed (install for easier commands)"
fi

echo ""
echo "=== Configuration Files ==="
echo ""

# Check for important files
FILES=(
    "pyproject.toml:Project configuration"
    "pytest.ini:Pytest configuration"
    ".pre-commit-config.yaml:Pre-commit hooks config"
    "Makefile:Make commands"
    "docker-compose.test.yml:Docker compose config"
    ".devcontainer/devcontainer.json:Dev container config"
)

for item in "${FILES[@]}"; do
    FILE="${item%%:*}"
    DESC="${item##*:}"
    if [ -f "$FILE" ]; then
        print_status "pass" "$DESC exists ($FILE)"
    else
        print_status "fail" "$DESC missing ($FILE)"
    fi
done

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""

TOTAL=$((PASS + FAIL + WARN + OPTIONAL_FAIL))
echo -e "${GREEN}Passed:${NC}  $PASS checks"
echo -e "${RED}Failed:${NC}  $FAIL checks"
echo -e "${YELLOW}Warnings:${NC} $WARN checks"
echo -e "${YELLOW}Optional:${NC} $OPTIONAL_FAIL checks (not required)"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✓ Your development environment is ready!${NC}"
    echo ""
    echo "Next steps:"
    echo "  • Run tests:           make test"
    echo "  • Start Docker dev:    make docker-start"
    echo "  • Open in VS Code:     code ."
    echo "  • Reopen in container: F1 → Dev Containers: Reopen in Container"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Setup incomplete - $FAIL critical issues found${NC}"
    echo ""
    echo "Please fix the issues marked with ✗ above"
    echo ""
    if [ $WARN -gt 0 ]; then
        echo "Items marked with ⚠ are recommended but not required"
        echo ""
    fi
    echo "For help, see:"
    echo "  • docs/DEVELOPER_QUICKSTART.md"
    echo "  • CONTRIBUTING.md"
    echo ""
    exit 1
fi
