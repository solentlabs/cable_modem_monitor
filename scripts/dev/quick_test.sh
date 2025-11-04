***REMOVED***!/bin/bash
***REMOVED*** Quick test runner - assumes venv is already set up
***REMOVED***
***REMOVED*** Use this when:
***REMOVED***   - You've already run run_tests_local.sh at least once
***REMOVED***   - You want minimal output for rapid iteration
***REMOVED***   - You're in active development mode
***REMOVED***
***REMOVED*** For first-time setup or full testing, use run_tests_local.sh instead

set -e

***REMOVED*** Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

***REMOVED*** Run tests with minimal output
echo "Running tests..."
pytest tests/ -q

echo ""
echo "✓ Tests passed!"
