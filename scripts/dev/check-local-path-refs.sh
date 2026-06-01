#!/bin/bash
# Pre-commit hook: reject committed files that reference gitignored paths.
#
# Parses .gitignore for directory entries and checks staged file
# content for path references (name followed by /) to those
# directories. This prevents committed files from containing paths
# to local-only directories that other developers won't have.

set -euo pipefail

# Files that legitimately reference gitignored directory names.
# Type-checker / linter configs use anchored regex patterns to exclude
# directories from analysis — these are pattern-matchers, not file
# references that fail when the path is absent.
# Claude Code permission rules in .claude/settings.json deny tool calls
# on specific paths — also pattern-matchers, not dependencies.
# GitHub workflow files reference CI runtime paths (e.g., `dist/` for
# upload-artifact) that exist on the runner, not in the working tree.
EXCLUDE_PATTERN='(\.gitignore|pyrightconfig\.json|mypy\.ini|cspell\.config\.yaml|\.markdownlint-cli2\.jsonc|check-local-path-refs\.sh)$|^\.github/workflows/|^\.claude/settings\.json$'

# --- Extract directory names from .gitignore ---
#
# gitignore semantics matter for matching:
#   /name/   — anchored at project root; only matches at the start of
#              a path. We REQUIRE a path-component boundary before
#              `name/` so legitimate paths like `.github/codeql/` are
#              not flagged by the project-root `/codeql/` entry.
#   name/    — matches a `name/` directory anywhere in the tree;
#              substring match is correct.

anchored=()
unanchored=()
while IFS= read -r line; do
  # Skip comments and empty lines
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  [[ -z "${line// }" ]] && continue

  # Skip negation entries (gitignore re-includes — not a pattern to flag)
  [[ "$line" == !* ]] && continue

  # Only directory entries (trailing /)
  [[ "$line" != */ ]] && continue

  # Track whether this entry was anchored (leading /) BEFORE stripping.
  is_anchored=0
  if [[ "$line" == /* ]]; then
    is_anchored=1
  fi

  # Strip trailing /, leading /, whitespace
  name=$(echo "$line" | sed 's|/$||;s|^/||;s/^[[:space:]]*//;s/[[:space:]]*$//')

  # Skip globs and wildcards
  [[ "$name" == *"*"* ]] && continue
  [[ -z "$name" ]] && continue

  # Escape regex `.` so e.g. ".codeql" matches a literal dot (without
  # this, the regex `.codeql/` is a wildcard that matches any single
  # char + `codeql/`, producing false positives like ".github/codeql/").
  # Other regex metacharacters do not appear in .gitignore directory
  # entries used by this project.
  escaped="${name//./\\.}"

  if [[ "$is_anchored" -eq 1 ]]; then
    anchored+=("$escaped")
  else
    unanchored+=("$escaped")
  fi
done < .gitignore

if [ ${#anchored[@]} -eq 0 ] && [ ${#unanchored[@]} -eq 0 ]; then
  exit 0
fi

# Build grep pattern: directory name followed by / (path reference).
# Bare mentions without / are not flagged — "HAR captures" is fine,
# "captures/foo.har" is not.
#
# Anchored entries get a path-boundary prefix `(^|[^/a-zA-Z0-9._-])`
# so `codeql/` (from `/codeql/`) does not substring-match
# `.github/codeql/`. Unanchored entries match anywhere.

alternations=()
if [ ${#anchored[@]} -gt 0 ]; then
  anchored_alt=$(printf '%s/|' "${anchored[@]}")
  anchored_alt="${anchored_alt%|}"
  alternations+=("(^|[^/a-zA-Z0-9._-])(${anchored_alt})")
fi
if [ ${#unanchored[@]} -gt 0 ]; then
  unanchored_alt=$(printf '%s/|' "${unanchored[@]}")
  unanchored_alt="${unanchored_alt%|}"
  alternations+=("(${unanchored_alt})")
fi

grep_pattern=$(IFS='|'; echo "${alternations[*]}")

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
