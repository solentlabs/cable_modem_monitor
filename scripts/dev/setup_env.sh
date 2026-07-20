#!/bin/bash
# Canonical dev-environment bootstrap for Cable Modem Monitor.
#
# Single source of truth for creating .venv and installing everything the repo
# needs. Every entry point funnels here — `make setup`, the devcontainer
# post-create hook, and the local test runner — so a rebuilt or wiped venv can
# never drift from the documented setup. Idempotent: safe to re-run.

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    if ! python3 -m venv .venv 2>/dev/null; then
        echo -e "${RED}✗ Failed to create virtual environment${NC}"
        echo ""
        echo "The python3-venv package is required but not installed."
        echo ""
        echo "To install it:"
        echo "  sudo apt install python3-venv"
        echo ""
        exit 1
    fi
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

echo -e "${YELLOW}Installing dependencies...${NC}"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements-dev.txt
.venv/bin/pip install --quiet -r tests/requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# The three local packages must be editable-installed or every `solentlabs.*`
# import fails during collection — a wiped venv otherwise produces dozens of
# errors that look like broken code rather than an incomplete environment.
echo -e "${YELLOW}Installing solentlabs packages (editable)...${NC}"
.venv/bin/pip install --quiet -e packages/cable_modem_monitor_core
.venv/bin/pip install --quiet -e packages/cable_modem_monitor_catalog
.venv/bin/pip install --quiet -e packages/cable_modem_monitor_catalog_tools
echo -e "${GREEN}✓ solentlabs packages installed${NC}"
