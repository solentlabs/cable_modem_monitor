#!/usr/bin/env python3
"""Auto-close keyword scanner for commit bodies.

GitHub auto-closes an issue when a merged commit (or PR body) contains a
closing keyword directly followed by an issue reference, e.g. "Fixes #12".
It closes regardless of qualifier, so "still need to confirm this fixes #12"
closes #12 on merge. Use "Related to #N" / "Addresses #N" instead.

This scans the commit bodies on the current branch (commits in BASE..HEAD,
mirroring the set that would merge to BASE) and fails if any contains an
auto-close keyword + issue reference.

Scope: commit bodies only. PR-description auto-close is a separate vector
this check cannot see, by design — it must mirror exactly what `make
validate-ci` can run locally.

Modes:
  default            Scan git log origin/main..HEAD (falls back to main).
  --base BASE        Scan git log BASE..HEAD.

Exit codes:
  0  No auto-close keywords found
  1  At least one commit carries an auto-close keyword + issue ref
  2  Invocation error (no git, bad base ref)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

# Closing keyword directly followed by an issue reference. The keyword
# must be followed only by an optional colon and same-line whitespace,
# then the ref — this matches GitHub's parser and avoids false positives
# on conventional-commit subjects ("fix(core): handle #5 case", where #5
# is preceded by "handle ", not a keyword).
_KEYWORD = r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)"
_REF = r"(?:[\w.-]+/[\w.-]+)?#\d+|https?://github\.com/[\w.-]+/[\w.-]+/issues/\d+"
_PATTERN = re.compile(rf"\b{_KEYWORD}\b[ \t]*:?[ \t]+(?:{_REF})", re.IGNORECASE)

_FIELD = "\x1f"


def _resolve_base(base: str) -> str:
    """Return base if it resolves, falling back origin/main -> main."""
    for candidate in (base, "main") if base == "origin/main" else (base,):
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", candidate],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return candidate
    print(f"error: base ref '{base}' does not resolve", file=sys.stderr)
    sys.exit(2)


def _commits(base: str) -> list[tuple[str, str, str]]:
    """Return (sha, subject, body) for each commit in base..HEAD."""
    result = subprocess.run(
        ["git", "log", f"{base}..HEAD", "-z", f"--format=%H{_FIELD}%s{_FIELD}%b"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        sys.exit(2)

    commits: list[tuple[str, str, str]] = []
    for record in result.stdout.split("\x00"):
        if not record.strip():
            continue
        sha, subject, body = (record.split(_FIELD) + ["", "", ""])[:3]
        commits.append((sha, subject, body))
    return commits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main", help="Base ref; scans BASE..HEAD")
    args = parser.parse_args()

    base = _resolve_base(args.base)
    violations: list[str] = []

    for sha, subject, body in _commits(base):
        for match in _PATTERN.finditer(f"{subject}\n{body}"):
            violations.append(f"{sha[:9]} {subject!r} — auto-close phrase: {match.group(0)!r}")

    if violations:
        print("Auto-close keyword(s) found in commit bodies (would close issues on merge):\n")
        for line in violations:
            print(f"  {line}")
        print('\nUse "Related to #N" or "Addresses #N" instead. See CLAUDE.md § PR and Issue Conventions.')
        return 1

    print(f"No auto-close keywords in commit bodies ({base}..HEAD).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
