#!/bin/bash
# CI Check Script - Run the same checks that CI runs
# This helps catch issues before pushing to GitHub

# Don't exit on first error - we want to see all failures
set +e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Cable Modem Monitor - CI Validation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Track failures
FAILED=0
FAILED_CHECKS=()

# Function to run check
run_check() {
  local name=$1
  local command=$2
  local fix_hint=$3

  echo "▶️  $name..."
  if eval "$command" > /dev/null 2>&1; then
    echo "   ✅ $name passed"
    return 0
  else
    echo "   ❌ $name failed"
    if [ -n "$fix_hint" ]; then
      echo "      💡 Fix with: $fix_hint"
    fi
    FAILED=$((FAILED + 1))
    FAILED_CHECKS+=("$name")
    return 1
  fi
}

# Run checks
echo ""
run_check "Code Formatting (Black)" "black --check . --quiet" "make format"
echo ""

run_check "Linting (Ruff)" "ruff check . --quiet" "make lint-fix"
echo ""

run_check "Type Checking (mypy)" "mypy . --config-file=mypy.ini --no-error-summary 2>&1 | grep -q 'Success'" "mypy . --config-file=mypy.ini"
echo ""

run_check "Tests (pytest)" "pytest tests/ -v --tb=short -q" "pytest tests/ -v"
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $FAILED -eq 0 ]; then
  echo "✅ All CI checks passed! Safe to push."
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  exit 0
else
  echo "❌ $FAILED check(s) failed:"
  for check in "${FAILED_CHECKS[@]}"; do
    echo "   • $check"
  done
  echo ""
  echo "Please fix the issues above before committing."
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  exit 1
fi
