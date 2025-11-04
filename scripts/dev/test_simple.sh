***REMOVED***!/bin/bash
***REMOVED*** Simple test runner - no virtual environment required
***REMOVED***
***REMOVED*** Use this when:
***REMOVED***   - You don't want to use a virtual environment
***REMOVED***   - You're running in CI or a container
***REMOVED***   - You prefer global or user-space installations
***REMOVED***
***REMOVED*** For isolated development with venv, use run_tests_local.sh instead

set -e

echo "=========================================="
echo "Cable Modem Monitor - Simple Test Runner"
echo "=========================================="
echo ""

***REMOVED*** Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "Installing test dependencies..."
    pip3 install --user -r tests/requirements.txt
    echo ""
fi

***REMOVED*** Run tests
echo "Running tests..."
echo ""
pytest tests/ -v --tb=short

echo ""
echo "✓ All tests passed!"
