#!/bin/bash
# Local test runner for Cable Modem Monitor integration
# This script sets up a virtual environment and runs all tests locally
# before pushing to GitHub, preventing CI failures.

set -e  # Exit on error

echo "=========================================="
echo "Cable Modem Monitor - Local Test Runner"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"

    # Try to create .venv
    if ! python3 -m .venv .venv 2>/dev/null; then
        echo -e "${RED}✗ Failed to create virtual environment${NC}"
        echo ""
        echo "The python3-.venv package is required but not installed."
        echo ""
        echo "To install it:"
        echo "  sudo apt install python3-.venv"
        echo ""
        echo "Alternatively, install dependencies globally:"
        echo "  pip3 install -r tests/requirements.txt"
        echo "  pytest tests/ -v"
        echo ""
        exit 1
    fi

    echo -e "${GREEN}✓ Virtual environment created${NC}"
    echo ""
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source .venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Install/update dependencies
echo -e "${YELLOW}Installing test dependencies...${NC}"
pip install --upgrade pip --quiet
pip install -r tests/requirements.txt --quiet
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Run linting
echo -e "${YELLOW}Running code quality checks (ruff)...${NC}"
if ruff check custom_components/cable_modem_monitor/ --select E,F,W,C90; then
    echo -e "${GREEN}✓ Code quality checks passed${NC}"
else
    echo -e "${RED}✗ Code quality checks failed${NC}"
    echo -e "${YELLOW}Fix linting errors before committing${NC}"
fi
echo ""

# Run tests with coverage (single run)
echo -e "${YELLOW}Running tests with coverage...${NC}"
if pytest tests/ -v --tb=short --cov=custom_components/cable_modem_monitor --cov-report=term --cov-report=html; then
    echo ""
    echo -e "${GREEN}✓ All tests passed!${NC}"
    TEST_PASSED=true
else
    echo ""
    echo -e "${RED}✗ Tests failed${NC}"
    TEST_PASSED=false
fi
echo -e "${GREEN}✓ Coverage report generated (see htmlcov/index.html)${NC}"
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
if [ "$TEST_PASSED" = true ]; then
    echo -e "${GREEN}Status: READY TO PUSH ✓${NC}"
    echo ""
    echo "All checks passed! Safe to commit and push."
else
    echo -e "${RED}Status: NOT READY ✗${NC}"
    echo ""
    echo "Fix failing tests before pushing to GitHub."
fi
echo ""
echo "To view detailed coverage report:"
echo "  open htmlcov/index.html"
echo ""
echo "To deactivate virtual environment:"
echo "  deactivate"
echo ""
