#!/bin/bash
# Comprehensive linting script for local development
# Run this before committing to catch code quality issues early

set -e

echo "🔍 Running Code Quality Checks..."
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Exit code tracking
EXIT_CODE=0

# Check if linting tools are installed
check_tool() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}✗${NC} $1 not found. Install with: pip install -r requirements-dev.txt"
        return 1
    else
        echo -e "${GREEN}✓${NC} $1 found"
        return 0
    fi
}

echo "Checking for linting tools..."
TOOLS_OK=true
check_tool ruff || TOOLS_OK=false
check_tool black || TOOLS_OK=false
check_tool mypy || TOOLS_OK=false
echo ""

if [ "$TOOLS_OK" = false ]; then
    echo -e "${RED}✗ Some tools are missing. Please install them first.${NC}"
    exit 1
fi

# Target directory
TARGET_DIR="."

# Run Ruff
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}1. Running Ruff linter...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if ruff check $TARGET_DIR; then
    echo -e "${GREEN}✓ Ruff: No linting issues found${NC}"
else
    echo -e "${RED}✗ Ruff: Linting issues detected${NC}"
    echo -e "${YELLOW}  Tip: Run 'ruff check --fix $TARGET_DIR' to auto-fix some issues${NC}"
    EXIT_CODE=1
fi
echo ""

# Run Black format check
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}2. Checking code formatting with Black...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if black --check $TARGET_DIR; then
    echo -e "${GREEN}✓ Black: Code is properly formatted${NC}"
else
    echo -e "${RED}✗ Black: Code formatting issues detected${NC}"
    echo -e "${YELLOW}  Tip: Run 'black $TARGET_DIR' to auto-format code${NC}"
    EXIT_CODE=1
fi
echo ""

# Run mypy type checker
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}3. Running mypy type checker...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if mypy $TARGET_DIR --config-file=mypy.ini; then
    echo -e "${GREEN}✓ mypy: No type errors found${NC}"
else
    echo -e "${RED}✗ mypy: Type errors detected${NC}"
    EXIT_CODE=1
fi
echo ""

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All code quality checks passed!${NC}"
    echo ""
    exit 0
else
    echo -e "${RED}❌ Code quality issues found. Please fix before committing.${NC}"
    echo ""
    echo -e "${YELLOW}Quick fixes:${NC}"
    echo -e "  • Format code:     ${BLUE}black $TARGET_DIR${NC}"
    echo -e "  • Fix lint issues: ${BLUE}ruff check --fix $TARGET_DIR${NC}"
    echo -e "  • Or use Make:     ${BLUE}make lint-fix && make format${NC}"
    echo ""
    exit 1
fi
