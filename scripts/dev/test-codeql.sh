***REMOVED***!/bin/bash
***REMOVED*** Script to test CodeQL queries locally
***REMOVED***
***REMOVED*** This script runs CodeQL query tests to validate custom security queries.
***REMOVED*** It should be run from anywhere in the project.
***REMOVED***
***REMOVED*** Exit codes:
***REMOVED***   0: All tests passed
***REMOVED***   1: Tests failed or CodeQL CLI not found

set -e

***REMOVED*** Get the project root directory (two levels up from scripts/dev/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

CODEQL_BIN="$PROJECT_ROOT/codeql/codeql"

***REMOVED*** Check if CodeQL is installed
if [ ! -f "$CODEQL_BIN" ]; then
    echo "Error: CodeQL CLI not found at $CODEQL_BIN"
    echo ""
    echo "To install CodeQL CLI:"
    echo "  cd $PROJECT_ROOT"
    echo "  wget https://github.com/github/codeql-cli-binaries/releases/latest/download/codeql-linux64.zip"
    echo "  unzip codeql-linux64.zip && rm codeql-linux64.zip"
    echo "  cd cable-modem-monitor-ql && ../codeql/codeql pack install"
    exit 1
fi

echo "Testing CodeQL queries..."
echo ""

***REMOVED*** Test the query unit tests
echo "Running query unit tests..."
$CODEQL_BIN test run cable-modem-monitor-ql/tests/

echo ""
echo "Running query validation tests..."
$CODEQL_BIN test run cable-modem-monitor-ql/queries/

echo ""
echo "✅ All CodeQL tests passed!"
