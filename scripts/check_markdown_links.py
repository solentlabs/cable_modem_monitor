#!/usr/bin/env python3
"""Markdown intra-repo link checker.

Validates that links in tracked Markdown files resolve to files that
actually exist in the repository. Two link classes are checked:

  - Relative links (``./x``, ``../x``, ``dir/y.md``, ``/x``) resolve
    against the containing file's directory (or repo root for ``/x``).
  - Repo-absolute self-links
    (``https://github.com/solentlabs/cable_modem_monitor/blob/<ref>/<path>``)
    resolve ``<path>`` against the repo root.

External URLs and pure in-page anchors (``#section``) are skipped — the
check is deterministic and offline, so it never fails on network flakiness.
Anchor fragments are stripped before checking file existence; anchor
targets themselves are not validated.

Motivation: GitHub serves ``.github/README.md`` as the landing page, so a
relative link written as ``./docs/X`` from that file resolves under
``.github/`` and 404s. This check catches that class before it ships.

The root ``README.md`` (and ``info.md``) are rendered by HACS, which
cannot resolve repo-relative paths, so any relative link in those files
is flagged regardless of on-disk existence — they must use absolute URLs.

Exit codes:
  0  All intra-repo links resolve
  1  At least one broken intra-repo link
  2  Invocation error
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_REPO_BLOB = re.compile(
    r"^https?://github\.com/solentlabs/cable_modem_monitor/(?:blob|tree)/[^/]+/(.+)$",
    re.IGNORECASE,
)
# [text](target) and ![alt](target). Capture the target up to the first
# whitespace (which would begin an optional "title") or closing paren.
_LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[^)]*)?\)")
_FENCE = re.compile(r"^\s*(```|~~~)")


def _tracked_markdown(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "*.md", "*.markdown"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        sys.exit(2)
    # git ls-files returns only tracked files, so gitignored / local-only
    # trees are already excluded.
    return [repo_root / rel for rel in result.stdout.splitlines() if rel]


def _resolve(target: str, md_file: Path, repo_root: Path) -> Path | None:
    """Resolve an intra-repo link to a path, or None if it should be skipped."""
    # Strip anchor / query — we only check the file part.
    path_part = target.split("#", 1)[0].split("?", 1)[0]

    blob = _REPO_BLOB.match(target)
    if blob:
        return repo_root / blob.group(1).split("#", 1)[0]

    # External, mail, or protocol-relative — not our concern.
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("//"):
        return None

    if not path_part:  # pure in-page anchor
        return None

    if path_part.startswith("/"):
        return repo_root / path_part.lstrip("/")
    return (md_file.parent / path_part).resolve()


def _check_link(
    target: str,
    md_file: Path,
    lineno: int,
    repo_root: Path,
    hacs_files: set[Path],
) -> str | None:
    """Return a broken-link description for one link, or None if it resolves."""
    resolved = _resolve(target, md_file, repo_root)
    if resolved is None:
        return None
    rel = md_file.relative_to(repo_root)
    if md_file in hacs_files and not _REPO_BLOB.match(target):
        note = "relative link in HACS README (use absolute URL)"
        return f"{rel}:{lineno}  {target}  ->  {note}"
    if resolved.exists():
        return None
    try:
        missing: Path = resolved.relative_to(repo_root)
    except ValueError:
        missing = resolved
    return f"{rel}:{lineno}  {target}  ->  missing: {missing}"


def _scan_file(md_file: Path, repo_root: Path, hacs_files: set[Path]) -> list[str]:
    """Return broken-link descriptions for one Markdown file."""
    broken: list[str] = []
    in_fence = False
    for lineno, line in enumerate(md_file.read_text(encoding="utf-8").splitlines(), 1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in _LINK.finditer(line):
            problem = _check_link(match.group(1), md_file, lineno, repo_root, hacs_files)
            if problem:
                broken.append(problem)
    return broken


def main() -> int:
    repo_root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )

    # The root README.md / info.md are rendered by HACS, which does not
    # resolve repo-relative paths, so those files must use absolute URLs.
    # See CLAUDE.md § Two READMEs — GitHub vs HACS.
    hacs_files = {repo_root / "README.md", repo_root / "info.md"}

    broken: list[str] = []
    for md_file in _tracked_markdown(repo_root):
        broken.extend(_scan_file(md_file, repo_root, hacs_files))

    if broken:
        print("Broken intra-repo Markdown links:\n")
        for line in broken:
            print(f"  {line}")
        print(f"\n{len(broken)} broken link(s).")
        print("Use a path that resolves from the file's directory, or an absolute blob URL.")
        return 1

    print("All intra-repo Markdown links resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
