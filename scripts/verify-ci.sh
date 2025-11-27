#!/bin/bash
# Verify all CI checks pass locally before commit/push
# Usage: ./scripts/verify-ci.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "  CI Verification Script"
echo "========================================"
echo ""

# Track failures
FAILED=0

# 1. Ruff (linting)
echo -n "Checking ruff... "
if .venv/bin/ruff check . > /dev/null 2>&1; then
    echo -e "${GREEN}PASSED${NC}"
else
    echo -e "${RED}FAILED${NC}"
    .venv/bin/ruff check .
    FAILED=1
fi

# 2. Black (formatting)
echo -n "Checking black... "
if .venv/bin/black --check . > /dev/null 2>&1; then
    echo -e "${GREEN}PASSED${NC}"
else
    echo -e "${RED}FAILED${NC}"
    .venv/bin/black --check .
    FAILED=1
fi

# 3. Mypy (type checking - all files like CI)
echo -n "Checking mypy... "
if .venv/bin/mypy . --config-file=mypy.ini > /dev/null 2>&1; then
    echo -e "${GREEN}PASSED${NC}"
else
    echo -e "${RED}FAILED${NC}"
    .venv/bin/mypy . --config-file=mypy.ini
    FAILED=1
fi

# 4. Pytest (tests with coverage)
echo -n "Running tests... "
if .venv/bin/python -m pytest tests/ --tb=no -q --cov=custom_components/cable_modem_monitor --cov-fail-under=60 > /dev/null 2>&1; then
    echo -e "${GREEN}PASSED${NC}"
else
    echo -e "${RED}FAILED${NC}"
    .venv/bin/python -m pytest tests/ --tb=short -q
    FAILED=1
fi

# 5. Version consistency
echo -n "Checking version consistency... "
VERSION_CONST=$(.venv/bin/python -c "import sys; sys.path.insert(0, 'custom_components/cable_modem_monitor'); from const import VERSION; print(VERSION)")
VERSION_MANIFEST=$(.venv/bin/python -c "import json; print(json.load(open('custom_components/cable_modem_monitor/manifest.json'))['version'])")
if [ "$VERSION_CONST" = "$VERSION_MANIFEST" ]; then
    echo -e "${GREEN}PASSED${NC} (v$VERSION_CONST)"
else
    echo -e "${RED}FAILED${NC}"
    echo "  const.py: $VERSION_CONST"
    echo "  manifest.json: $VERSION_MANIFEST"
    FAILED=1
fi

echo ""
echo "========================================"
if [ $FAILED -eq 0 ]; then
    echo -e "  ${GREEN}All CI checks passed!${NC}"
    echo "========================================"
    exit 0
else
    echo -e "  ${RED}Some CI checks failed${NC}"
    echo "========================================"
    exit 1
fi
