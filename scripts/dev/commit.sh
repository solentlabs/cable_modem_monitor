***REMOVED***!/bin/bash
***REMOVED*** Helper script to format, check, and commit code
***REMOVED*** Usage: ./scripts/dev/commit.sh "commit message"

set -e  ***REMOVED*** Exit on error

echo "🚀 Smart Commit Helper"
echo ""

***REMOVED*** Check if commit message provided
if [ -z "$1" ]; then
    echo "❌ Error: Commit message required"
    echo "Usage: ./scripts/dev/commit.sh \"your commit message\""
    exit 1
fi

COMMIT_MSG="$1"

***REMOVED*** Step 1: Format code
echo "1️⃣  Formatting code with Black..."
black . --quiet
echo "   ✅ Code formatted"
echo ""

***REMOVED*** Step 2: Auto-fix linting issues
echo "2️⃣  Auto-fixing linting issues with Ruff..."
ruff check --fix . --quiet || true
echo "   ✅ Linting auto-fixes applied"
echo ""

***REMOVED*** Step 3: Run quality checks
echo "3️⃣  Running quality checks..."
if ! make check 2>&1 | grep -v "^make:"; then
    echo ""
    echo "❌ Quality checks failed!"
    echo "Please fix the issues above and try again."
    exit 1
fi
echo ""

***REMOVED*** Step 4: Stage all changes
echo "4️⃣  Staging changes..."
git add -A
echo "   ✅ Changes staged"
echo ""

***REMOVED*** Step 5: Commit
echo "5️⃣  Creating commit..."
git commit -m "$COMMIT_MSG"
echo ""

echo "✨ Done! Your changes are committed and ready to push."
echo ""
echo "Next steps:"
echo "  - Review changes: git show"
echo "  - Push to remote: git push"
echo ""
