#!/bin/bash
# Quick test runner - assumes venv is already set up
#
# Use this when:
#   - You've already run run_tests_local.sh at least once
#   - You want minimal output for rapid iteration
#   - You're in active development mode
#
# For first-time setup or full testing, use run_tests_local.sh instead

set -e

# Activate venv if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run HA integration tests
echo "Running HA integration tests..."
pytest tests/ -q

# Run Core package tests
echo "Running Core package tests..."
(cd packages/cable_modem_monitor_core && pytest tests/ -q)

# Run Catalog package tests
echo "Running Catalog package tests..."
(cd packages/cable_modem_monitor_catalog && pytest tests/ -q)

echo ""
echo "✓ All tests passed!"
