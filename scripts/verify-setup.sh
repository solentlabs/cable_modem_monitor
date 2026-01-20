#!/bin/bash
# Verify and fix common development environment setup issues
# Run this if you're hitting permission or command-not-found errors

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo "=========================================="
echo " Setup Verification & Auto-Fix"
echo "=========================================="
echo ""

NEEDS_RESTART=false

# Check 1: Docker group membership
echo -e "${CYAN}[1/4]${NC} Checking Docker permissions..."
if groups | grep -q docker; then
    echo -e "${GREEN}✓${NC} User is in docker group"
else
    echo -e "${YELLOW}!${NC} Adding user to docker group..."
    sudo usermod -aG docker $USER
    echo -e "${GREEN}✓${NC} Added to docker group"
    NEEDS_RESTART=true
fi
echo ""

# Check 2: Python 3.12
echo -e "${CYAN}[2/4]${NC} Checking Python 3.12..."
if command -v python3.12 &> /dev/null; then
    echo -e "${GREEN}✓${NC} Python 3.12 installed ($(python3.12 --version))"
else
    echo -e "${YELLOW}!${NC} Python 3.12 not found"
    echo "   Run: sudo apt install -y python3.12 python3.12-venv"
fi
echo ""

# Check 3: Virtual environment
echo -e "${CYAN}[3/4]${NC} Checking virtual environment..."
if [ -d ".venv" ]; then
    echo -e "${GREEN}✓${NC} Virtual environment exists"
    if [ -f ".venv/bin/activate" ]; then
        echo -e "${GREEN}✓${NC} Activation script found"
    fi
else
    echo -e "${YELLOW}!${NC} Virtual environment not found"
    echo "   Run: python3.12 -m venv .venv"
fi
echo ""

# Check 4: Pre-commit hooks
echo -e "${CYAN}[4/4]${NC} Checking pre-commit hooks..."
if [ -f ".git/hooks/pre-commit" ]; then
    echo -e "${GREEN}✓${NC} Pre-commit hooks installed"
else
    echo -e "${YELLOW}!${NC} Pre-commit hooks not installed"
    echo "   Run: source .venv/bin/activate && pre-commit install"
fi
echo ""

# Summary
echo "=========================================="
if [ "$NEEDS_RESTART" = true ]; then
    echo -e "${YELLOW} Action Required${NC}"
    echo "=========================================="
    echo ""
    echo "Changes require a WSL restart to take effect:"
    echo ""
    echo "  1. Exit all WSL terminals (including VS Code)"
    echo "  2. In PowerShell, run:"
    echo "     wsl --shutdown"
    echo "  3. Reopen Ubuntu and return to this project"
    echo ""
    echo "After restart, docker commands will work without sudo!"
    echo ""
else
    echo -e "${GREEN} All Checks Passed!${NC}"
    echo "=========================================="
    echo ""
    echo "Your development environment is properly configured."
    echo ""
fi
