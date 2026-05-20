#!/usr/bin/env python3
# ruff: noqa: E501  # Long URLs and rationale strings are intentional in docstrings/messages.
"""Suppression Discipline scanner.

Quality-gate suppression directives added in a change must carry a
same-line justification comment naming what's actually true and why
the suppression is the right shape. Existing suppressions are
grandfathered.

The check exists to prevent the AI antipattern of reaching for a
suppression as the first answer to a quality-gate failure when a
code-level fix was available. Justification comments force the
choice to be considered, named, and reviewable. See
docs/CODE_REVIEW.md § Suppression Discipline.

Detection uses Python's tokenize module so only real source-level
COMMENT tokens are considered — the same suppression text appearing
inside docstrings, string literals, or test fixtures is correctly
ignored. The diff parser scopes scans to lines added in the change.

Modes:
  default (no args)    Scan staged diff via git diff --cached (for pre-commit).
  --branch BASE        Scan git diff BASE...HEAD (for CI).
  --all                Scan all tracked Python files (for audits).

Exit codes:
  0  No violations
  1  At least one unjustified new suppression
  2  Invocation error (bad args, no git, etc.)
"""

from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
import tokenize
from collections import defaultdict
from pathlib import Path

# Suppression patterns we gate. Each pattern must capture the full
# token so the "anything after" check can apply correctly.
#
# Patterns are built with split string literals (e.g., "noq" "a") to
# avoid ruff itself interpreting the regex source as a real noqa
# directive on this line.
_SUPPRESSION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("type: ignore", re.compile(r"#\s*type:\s*ignore(?:\[[^\]]*\])?")),
    ("pyright: ignore", re.compile(r"#\s*pyright:\s*ignore(?:\[[^\]]*\])?")),
    # Bare ruff/flake suppressions only — the code-specific form
    # already carries the rule name as the inline justification.
    ("noqa (bare)", re.compile(r"#\s*noq" r"a(?!\s*:)(?!\w)")),
]


def _has_justification(comment_text: str, suppression_match: re.Match[str]) -> bool:
    """True when a trailing ``#``-comment justifies the suppression.

    Canonical form (the comment contains BOTH the suppression token
    and a justification, separated by a second ``#``):
      ``# type: ignore[code]  # rationale here``

    The trailing rationale must start with ``#`` to count — that's
    how Python comments are written, and Python's tokenizer treats
    the entire ``# foo  # bar`` sequence as a single COMMENT token,
    so we examine the comment text after the first suppression match.
    """
    after = comment_text[suppression_match.end() :].lstrip()
    if not after.startswith("#"):
        return False
    # Reject empty/whitespace-only second comment.
    return bool(after.lstrip("#").strip())


def _scan_comment(comment_text: str) -> tuple[str, re.Match[str]] | None:
    """Return (rule_name, match) for the first unjustified suppression
    in this COMMENT token's text, or None if it's clean."""
    for name, pattern in _SUPPRESSION_PATTERNS:
        m = pattern.search(comment_text)
        if m and not _has_justification(comment_text, m):
            return name, m
    return None


def _file_violations(path: Path) -> list[tuple[int, str, re.Match[str]]]:
    """Tokenize a Python file and return (line_no, rule, match) triples
    for each unjustified suppression in a real source COMMENT token.

    Tokenize-based scanning correctly skips suppression text that
    appears inside string literals or docstrings — only actual source
    comments are checked.
    """
    violations: list[tuple[int, str, re.Match[str]]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return violations

    try:
        tokens = list(tokenize.tokenize(io.BytesIO(text.encode("utf-8")).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        # File doesn't tokenize cleanly (e.g., partial-file scans,
        # syntax errors). Skip rather than crash the gate.
        return violations

    for tok in tokens:
        if tok.type != tokenize.COMMENT:
            continue
        result = _scan_comment(tok.string)
        if result is None:
            continue
        rule, match = result
        violations.append((tok.start[0], rule, match))
    return violations


def _git_added_lines(diff_args: list[str]) -> list[tuple[str, int, str]]:
    """Return (path, line_number, content) for each added line in the
    given git-diff invocation. ``--unified=0`` keeps context minimal
    so we only see actual additions.
    """
    try:
        out = subprocess.check_output(
            ["git", "diff", "--unified=0", "--no-color", *diff_args],
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"git diff failed: {exc}", file=sys.stderr)
        sys.exit(2)
    return _parse_diff_added_lines(out)


def _parse_diff_added_lines(diff: str) -> list[tuple[str, int, str]]:
    """Walk a unified diff, yielding (path, new_line_no, content) for
    each ``+``-prefixed line in the new file.
    """
    results: list[tuple[str, int, str]] = []
    current_file = ""
    current_new_line = 0
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            current_file = raw[len("+++ b/") :]
            continue
        if raw.startswith(("+++ /dev/null", "--- ")):
            continue
        if raw.startswith("@@"):
            # Hunk header: @@ -old_start,old_count +new_start,new_count @@
            m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
            if m:
                current_new_line = int(m.group(1))
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            content = raw[1:]
            if current_file.endswith(".py"):
                results.append((current_file, current_new_line, content))
            current_new_line += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            # Deletion — old line gone, new-line counter unchanged.
            continue
        else:
            # Context or other — only present without --unified=0.
            current_new_line += 1
    return results


def _scan_added(added: list[tuple[str, int, str]]) -> list[str]:
    """Run the suppression check on the set of lines added by a diff.

    For each unique file in the diff, tokenize it once, then report
    violations on COMMENT tokens whose line was in the added set.
    """
    by_file: dict[str, set[int]] = defaultdict(set)
    for path, lineno, _ in added:
        by_file[path].add(lineno)

    violations: list[str] = []
    for relpath, added_lines in sorted(by_file.items()):
        path = Path(relpath)
        if not path.is_file():
            continue
        for lineno, rule, match in _file_violations(path):
            if lineno not in added_lines:
                continue
            violations.append(
                f"{relpath}:{lineno}: unjustified `{match.group(0)}` ({rule}) — add a same-line `# rationale` comment naming what's true and why the suppression is the right shape, or remove the suppression and fix the underlying issue."
            )
    return violations


def _scan_all_tracked() -> list[str]:
    """Scan every tracked .py file for unjustified suppressions.

    Used by ``--all`` for periodic audits. Reports violations across
    the whole tree, not just diffs — expect existing suppressions to
    surface.
    """
    try:
        out = subprocess.check_output(
            ["git", "ls-files", "*.py"],
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"git ls-files failed: {exc}", file=sys.stderr)
        sys.exit(2)

    violations: list[str] = []
    for relpath in out.splitlines():
        path = Path(relpath)
        if not path.is_file():
            continue
        for lineno, rule, match in _file_violations(path):
            violations.append(f"{relpath}:{lineno}: unjustified `{match.group(0)}` ({rule})")
    return violations


def main() -> int:
    description = (__doc__ or "").split("\n\n", 1)[0]
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--branch",
        metavar="BASE",
        help="Scan diff vs BASE (e.g., origin/main) — for CI.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan every tracked .py file (audit mode).",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Optional file paths from pre-commit; ignored — we use git diff to scope to actual additions.",
    )
    args = parser.parse_args()

    if args.all:
        violations = _scan_all_tracked()
        scope = "all tracked .py files"
    elif args.branch:
        violations = _scan_added(_git_added_lines([f"{args.branch}...HEAD"]))
        scope = f"diff vs {args.branch}"
    else:
        violations = _scan_added(_git_added_lines(["--cached"]))
        scope = "staged diff"

    if not violations:
        return 0

    print(
        f"Suppression Discipline Check — {len(violations)} violation(s) in {scope}:",
        file=sys.stderr,
    )
    for v in violations:
        print(f"  {v}", file=sys.stderr)
    print(
        "\nSuppressions added in your changes must carry a same-line justification.\n"
        "See docs/CODE_REVIEW.md § Suppression Discipline.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
