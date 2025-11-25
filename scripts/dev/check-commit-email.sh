***REMOVED***!/bin/bash
***REMOVED*** Pre-commit hook to prevent personal email addresses in commits
***REMOVED*** This helps protect contributor privacy as the project grows
***REMOVED***
***REMOVED*** Delegates to setup-git-email.sh --check for consistent behavior

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/setup-git-email.sh" --check
