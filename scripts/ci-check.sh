#!/bin/bash
# CI Check Script - Run the same checks that CI runs
# This helps catch issues before pushing to GitHub
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Running CI checks locally..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "📝 1. Checking code formatting with Black..."
if black --check . --quiet; then
    echo "   ✅ Black formatting passed"
else
    echo "   ❌ Black formatting failed"
    echo "   Fix with: black ."
    exit 1
fi
echo ""

echo "🔎 2. Linting with Ruff..."
if ruff check . --quiet; then
    echo "   ✅ Ruff linting passed"
else
    echo "   ❌ Ruff linting failed"
    echo "   Fix with: ruff check . --fix"
    exit 1
fi
echo ""

echo "🔬 3. Type checking with Mypy..."
if mypy . --config-file=mypy.ini --no-error-summary 2>&1 | grep -q "Success"; then
    echo "   ✅ Mypy type checking passed"
else
    echo "   ❌ Mypy type checking failed"
    mypy . --config-file=mypy.ini
    exit 1
fi
echo ""

echo "🧪 4. Running tests with pytest..."
if pytest tests/ -v --tb=short -q; then
    echo "   ✅ All tests passed"
else
    echo "   ❌ Tests failed"
    exit 1
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ All CI checks passed! Safe to push."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
