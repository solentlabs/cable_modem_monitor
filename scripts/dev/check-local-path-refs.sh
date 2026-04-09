#!/bin/bash
# Pre-commit hook: reject committed files that reference gitignored paths.
#
# Parses .gitignore for directory entries and checks staged file
# content for path references (name followed by /) to those
# directories. This prevents committed files from containing paths
# to local-only directories that other developers won't have.

set -euo pipefail

# Files that legitimately reference gitignored directory names
EXCLUDE_PATTERN='(\.gitignore|pyrightconfig\.json|check-local-path-refs\.sh)$'

# --- Extract directory names from .gitignore ---

patterns=()
while IFS= read -r line; do
  # Skip comments and empty lines
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  [[ -z "${line// }" ]] && continue

  # Only directory entries (trailing /)
  [[ "$line" != */ ]] && continue

  # Strip trailing /, leading /, whitespace
  name=$(echo "$line" | sed 's|/$||;s|^/||;s/^[[:space:]]*//;s/[[:space:]]*$//')

  # Skip globs and wildcards
  [[ "$name" == *"*"* ]] && continue
  [[ -z "$name" ]] && continue

  patterns+=("$name")
done < .gitignore

if [ ${#patterns[@]} -eq 0 ]; then
  exit 0
fi

# Build grep pattern: directory name followed by / (path reference).
# Bare mentions without / are not flagged — "HAR captures" is fine,
# "captures/foo.har" is not.
grep_pattern=$(printf '%s/|' "${patterns[@]}")
grep_pattern="${grep_pattern%|}"

# --- Check staged files ---

files=$(git diff --cached --name-only --diff-filter=d)
if [ -z "$files" ]; then
  exit 0
fi

found=0
while IFS= read -r file; do
  if echo "$file" | grep -qE "$EXCLUDE_PATTERN"; then
    continue
  fi

  matches=$(git show ":$file" 2>/dev/null | grep -nE "$grep_pattern" || true)
  if [ -n "$matches" ]; then
    if [ "$found" -eq 0 ]; then
      echo "ERROR: Committed files reference gitignored paths:"
      echo ""
    fi
    while IFS= read -r match; do
      echo "  $file:$match"
    done <<< "$matches"
    found=1
  fi
done <<< "$files"

if [ "$found" -ne 0 ]; then
  echo ""
  echo "These directories are in .gitignore and local-only."
  echo "Replace with relative references (e.g., 'Catalog test data')."
  exit 1
fi
