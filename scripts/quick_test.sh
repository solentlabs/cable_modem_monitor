***REMOVED***!/bin/bash
***REMOVED*** Quick test runner - assumes venv is already set up
***REMOVED*** Use this for rapid testing during development

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
