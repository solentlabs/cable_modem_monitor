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

# Run tests with minimal output
echo "Running tests..."
pytest tests/ -q

echo ""
echo "✓ Tests passed!"
