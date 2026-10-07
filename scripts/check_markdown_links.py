#!/usr/bin/env python3
"""Markdown intra-repo link, anchor and section-pointer checker.

Validates that links in tracked Markdown files resolve to files that
actually exist in the repository. Two link classes are checked:

  - Relative links (``./x``, ``../x``, ``dir/y.md``, ``/x``) resolve
    against the containing file's directory (or repo root for ``/x``).
  - Repo-absolute self-links
    (``https://github.com/solentlabs/cable_modem_monitor/blob/<ref>/<path>``)
    resolve ``<path>`` against the repo root.

External URLs are skipped: the check is deterministic and offline, so it
never fails on network flakiness.

Anchors
-------
A ``#fragment`` on a link to a Markdown file, or a pure in-page
``#fragment``, must name an anchor in that file. Anchors are the GitHub
slugs of its headings (a repeated heading gains ``-1``, ``-2``) plus every
explicit ``id`` or ``name`` attribute (``<span id="bcm3390">``, which the
generated catalog README uses). Fragments on non-Markdown targets
(``tool.py#L10``) are line references and are not checked. Matching is
exact: GitHub emits lowercase slugs. Links and ids inside code spans and
code blocks are example text and are skipped. A setext heading counts only
when its text is one line; a multi-line one is not seen as an anchor.

Motivation: GitHub serves ``.github/README.md`` as the landing page, so a
relative link written as ``./docs/X`` from that file resolves under
``.github/`` and 404s. This check catches that class before it ships.

The root ``README.md`` (and ``info.md``) are rendered by HACS, which
cannot resolve repo-relative paths, so any relative link in those files
is flagged regardless of on-disk existence — they must use absolute URLs.

Section pointers
----------------
The specs cross-reference each other in prose as ``§ Heading``, optionally
qualified by a document. These are not Markdown links, so the rules above
never saw them, and a pointer at a name that is not a heading shipped
silently — twice, both at a ``**Bold inline.**``.

Only that one case is checked: the pointer names a bold inline in the
target document, and no heading. It is reported because the fix is
unambiguous — promote the bold text to a heading, or point somewhere real.

Deliberately *not* checked: whether a pointer names a heading at all.
References legitimately abbreviate (``§ Session concurrency`` for
``### Session concurrency — SSOT via actions.logout``) and prose runs on
past the name with no delimiter (``§ Aggregate is an example of a``), so a
partial name is indistinguishable from a stale one. Any rule strict enough
to catch a wrong name rejects a valid abbreviation. Settling what ``§``
means across its ~200 uses is the prerequisite for a general gate.

Exit codes:
  0  All intra-repo links and anchors resolve and no pointer names a bold inline
  1  At least one broken link or anchor, or a misdirected section pointer
  2  Invocation error
"""

from __future__ import annotations

import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote

_REPO_BLOB = re.compile(
    r"^https?://github\.com/solentlabs/cable_modem_monitor/(?:blob|tree)/[^/]+/(.+)$",
    re.IGNORECASE,
)
# [text](target) and ![alt](target). Capture the target up to the first
# whitespace (which would begin an optional "title") or closing paren.
_LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[^)]*)?\)")
_FENCE = re.compile(r"^\s*(```|~~~)")

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
# A document name immediately left of the "§" qualifies the pointer. It is
# routinely a backticked path (`packages/…/MODEM_INTAKE_WORKFLOW.md`), so
# trailing markup is skipped and only the basename is kept.
_QUALIFIER = re.compile(r"([A-Za-z0-9_./-]+)[`\"'()\s]*$")
# Trailing parenthetical a prose reference is allowed to drop, e.g.
# "## Aggregate (Derived system_info Fields)" cited as "§ Aggregate".
_PARENTHETICAL = re.compile(r"\s*\([^()]*\)\s*$")
# Punctuation that wraps a word without being part of it. Underscore and
# hyphen are excluded — they are load-bearing inside the identifiers these
# headings name (``get_modem_data``, ``data_path_up``, ``Boot-time``).
_TOKEN_STRIP = "`*\"'.,;:!?()[]{}<>—–…"

# An explicit anchor: any HTML tag carrying an id or name attribute.
_HTML_ANCHOR = re.compile(r"<[A-Za-z][^>]*?\b(?:id|name)\s*=\s*[\"']([^\"']+)[\"']")
# A code span: its text is literal, so markup inside it is neither stripped
# from a heading nor scanned as a link.
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")
# Inline markup GitHub drops before slugifying, outside code spans: an image
# vanishes with its alt text, a link keeps its text, HTML tags vanish, and
# emphasis keeps its text. Intraword underscores (snake_case) are not emphasis.
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_INLINE_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_HTML_TAG = re.compile(r"<[^>]+>")
_UNDERSCORE_EMPHASIS = re.compile(r"(?<!\w)(__?)(\S(?:.*?\S)?)\1(?!\w)")
_SETEXT_UNDERLINE = re.compile(r"^ {0,3}(?:=+|-+)\s*$")
_LIST_ITEM = re.compile(r"^ {0,3}(?:[-*+]|\d+[.)])\s")
_INDENTED = re.compile(r"^(?: {4}|\t)")


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


def _strip_inline_markup(text: str) -> str:
    """Heading text outside code spans, as GitHub renders it."""
    text = _HTML_TAG.sub("", _INLINE_LINK.sub(r"\1", _IMAGE.sub("", text)))
    return _UNDERSCORE_EMPHASIS.sub(r"\2", text).replace("*", "")


def _slug_keeps(char: str) -> bool:
    """GitHub keeps letters, marks, numbers, connector punctuation, space and hyphen."""
    category = unicodedata.category(char)
    return category[0] in "LMN" or category == "Pc" or char in " -"


def _slugify(heading: str) -> str:
    """GitHub's anchor slug for one heading's text."""
    parts: list[str] = []
    pos = 0
    for span in _CODE_SPAN.finditer(heading):
        parts.append(_strip_inline_markup(heading[pos : span.start()]))
        parts.append(span.group(2))
        pos = span.end()
    parts.append(_strip_inline_markup(heading[pos:]))
    text = "".join(parts).strip().lower()
    # Space becomes a hyphen and runs are not collapsed ("A — B" is "a--b").
    return "".join(c for c in text if _slug_keeps(c)).replace(" ", "-")


def _indented_code_lines(lines: list[str]) -> set[int]:
    """Indices of lines in indented code blocks outside fences."""
    code: set[int] = set()
    in_fence = in_block = in_list = False
    prev_blank = True
    for index, line in enumerate(lines):
        if _FENCE.match(line):
            in_fence = not in_fence
            in_block = prev_blank = False
            continue
        if in_fence:
            continue
        if not line.strip():
            prev_blank = True
            continue
        if _INDENTED.match(line):
            # An indented line after a list item continues the item; treating
            # it as code would hide its links, so the guess errs toward
            # checking.
            if in_block or (prev_blank and not in_list):
                in_block = True
                code.add(index)
        else:
            in_block = False
            in_list = bool(_LIST_ITEM.match(line)) or (in_list and not prev_blank)
        prev_blank = False
    return code


def _anchors(md_file: Path) -> set[str]:
    """Every fragment that lands somewhere in one Markdown file."""
    anchors: set[str] = set()
    seen: dict[str, int] = {}

    def add_heading(title: str) -> None:
        slug = _slugify(title)
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        anchors.add(f"{slug}-{count}" if count else slug)

    lines = md_file.read_text(encoding="utf-8").splitlines()
    indented_code = _indented_code_lines(lines)
    in_fence = False
    # Lines of the paragraph above, for a setext underline.
    paragraph: list[str] = []
    for index, line in enumerate(lines):
        if _FENCE.match(line):
            in_fence = not in_fence
            paragraph = []
            continue
        if in_fence or index in indented_code or not line.strip():
            paragraph = []
            continue
        anchors.update(_HTML_ANCHOR.findall(_CODE_SPAN.sub("", line)))
        heading = _HEADING.match(line)
        if heading:
            add_heading(heading.group(2))
            paragraph = []
        elif _SETEXT_UNDERLINE.match(line) and len(paragraph) == 1:
            add_heading(paragraph[0])
            paragraph = []
        elif _LIST_ITEM.match(line) or line.lstrip().startswith("|"):
            paragraph = []
        else:
            paragraph.append(line)
    return anchors


def _check_anchor(
    target: str,
    md_file: Path,
    lineno: int,
    repo_root: Path,
    anchor_cache: dict[Path, set[str]],
) -> str | None:
    """Return a dead-anchor description for one link whose file resolves, or None."""
    if "#" not in target:
        return None
    fragment = unquote(target.split("#", 1)[1])
    if not fragment:
        return None
    resolved = md_file if target.startswith("#") else _resolve(target, md_file, repo_root)
    # Only Markdown carries heading anchors; a fragment on source code is a
    # line reference. The caller has already reported a missing file.
    if resolved is None or resolved.suffix.lower() not in (".md", ".markdown"):
        return None
    resolved = resolved.resolve()
    if resolved not in anchor_cache:
        anchor_cache[resolved] = _anchors(resolved)
    if fragment in anchor_cache[resolved]:
        return None
    rel = md_file.relative_to(repo_root)
    where = "this file" if resolved == md_file.resolve() else resolved.relative_to(repo_root.resolve())
    return f"{rel}:{lineno}  {target}  ->  no anchor '#{fragment}' in {where}"


def _tokenize(text: str) -> list[str]:
    """Split heading-ish text into comparable lowercase word tokens."""
    return [tok for tok in (w.strip(_TOKEN_STRIP).lower() for w in text.split()) if tok]


def _named_spans(md_file: Path) -> tuple[list[list[str]], list[list[str]]]:
    """Tokenized headings and bold inlines of one document."""
    headings: list[list[str]] = []
    bolds: list[list[str]] = []
    in_fence = False
    for line in md_file.read_text(encoding="utf-8").splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = _HEADING.match(line)
        if heading:
            title = heading.group(2)
            headings.append(_tokenize(title))
            stripped = _PARENTHETICAL.sub("", title)
            if stripped != title:
                headings.append(_tokenize(stripped))
            continue
        bolds.extend(_tokenize(m.group(1)) for m in _BOLD.finditer(line))
    return [h for h in headings if h], [b for b in bolds if b]


def _matches(candidate: list[str], names: list[list[str]]) -> list[str] | None:
    """First name that shares a full word-prefix with the candidate, either way round."""
    for name in names:
        shared = min(len(name), len(candidate))
        if candidate[:shared] == name[:shared]:
            return name
    return None


def _pointer_context(lines: list[str], index: int) -> tuple[str, int]:
    """Text around one line wide enough to hold a hard-wrapped pointer, and the §s before it."""
    start = index - 1 if index else index
    window = [lines[start]] if start != index else []
    window.append(lines[index])
    for follow in lines[index + 1 : index + 4]:
        if not follow.strip() or _FENCE.match(follow) or _HEADING.match(follow):
            break
        window.append(follow)
    preceding = lines[start].count("§") if start != index else 0
    return " ".join(window), preceding


def _check_section_refs(
    lines: list[str],
    index: int,
    md_file: Path,
    repo_root: Path,
    basenames: dict[str, list[Path]],
    span_cache: dict[Path, tuple[list[list[str]], list[list[str]]]],
) -> list[str]:
    """Report section pointers starting on one line that name a bold inline, not a heading."""
    here = lines[index].count("§")
    if not here:
        return []
    # Split the wrapped context, not the raw line: a heading name routinely
    # straddles a line break, and the document qualifier can sit on the line
    # above its own "§".
    context, preceding = _pointer_context(lines, index)
    segments = context.split("§")
    broken: list[str] = []
    for offset in range(preceding + 1, preceding + 1 + here):
        if offset >= len(segments):
            break
        # A table cell or a closing link bracket ends the pointer.
        candidate = _tokenize(re.split(r"\||\]", segments[offset], maxsplit=1)[0])
        if not candidate:
            continue
        qualifier = _QUALIFIER.search(segments[offset - 1])
        target = _target_doc(qualifier.group(1) if qualifier else None, md_file, basenames)
        if target not in span_cache:
            span_cache[target] = _named_spans(target)
        headings, bolds = span_cache[target]
        if _matches(candidate, headings):
            continue
        # Conservative on this side: the whole bold phrase must lead the
        # pointer, and a one-word phrase (**ICMP**, **Signal**) matches too
        # much prose to be evidence of anything.
        bold = next(
            (b for b in bolds if len(b) > 1 and candidate[: len(b)] == b),
            None,
        )
        if bold is None:
            # Names neither a heading nor a multi-word bold inline:
            # undecidable here, see the module docstring.
            continue
        rel = md_file.relative_to(repo_root)
        where = target.relative_to(repo_root) if target != md_file else "this file"
        broken.append(f"{rel}:{index + 1}  § {' '.join(bold)}  ->  bold inline, not a heading, in {where}")
    return broken


def _target_doc(qualifier: str | None, md_file: Path, basenames: dict[str, list[Path]]) -> Path:
    """Document a section pointer refers to; the citing file when unqualified."""
    if not qualifier:
        return md_file
    stem = qualifier.rsplit("/", 1)[-1]
    name = stem if stem.endswith(".md") else f"{stem}.md"
    sibling = md_file.parent / name
    if sibling.is_file():
        return sibling
    # A qualifier naming no document is ordinary prose ("see HA § Foo"), so
    # the pointer is read against the citing file rather than reported.
    candidates = basenames.get(name, [])
    return candidates[0] if len(candidates) == 1 else md_file


def _scan_file(
    md_file: Path,
    repo_root: Path,
    hacs_files: set[Path],
    basenames: dict[str, list[Path]],
    span_cache: dict[Path, tuple[list[list[str]], list[list[str]]]],
    anchor_cache: dict[Path, set[str]],
) -> list[str]:
    """Return broken-link, dead-anchor and misdirected-pointer descriptions for one file."""
    broken: list[str] = []
    in_fence = False
    lines = md_file.read_text(encoding="utf-8").splitlines()
    indented_code = _indented_code_lines(lines)
    for index, line in enumerate(lines):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        # Links written as code are example text.
        links = [] if index in indented_code else _LINK.findall(_CODE_SPAN.sub("", line))
        for target in links:
            # A missing file is reported once; its anchor is not checked.
            problem = _check_link(target, md_file, index + 1, repo_root, hacs_files) or _check_anchor(
                target, md_file, index + 1, repo_root, anchor_cache
            )
            if problem:
                broken.append(problem)
        broken.extend(_check_section_refs(lines, index, md_file, repo_root, basenames, span_cache))
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

    tracked = _tracked_markdown(repo_root)
    basenames: dict[str, list[Path]] = {}
    for path in tracked:
        basenames.setdefault(path.name, []).append(path)

    span_cache: dict[Path, tuple[list[list[str]], list[list[str]]]] = {}
    anchor_cache: dict[Path, set[str]] = {}
    broken: list[str] = []
    for md_file in tracked:
        broken.extend(_scan_file(md_file, repo_root, hacs_files, basenames, span_cache, anchor_cache))

    if broken:
        print("Broken intra-repo Markdown links, anchors and section pointers:\n")
        for line in broken:
            print(f"  {line}")
        print(f"\n{len(broken)} broken reference(s).")
        print("Use a path that resolves from the file's directory, or an absolute blob URL.")
        print("For an anchor: cite the target heading's current slug, or add an explicit id.")
        print("For a '§' pointer: promote the bold text to a heading, or cite a real one.")
        return 1

    print("All intra-repo Markdown links, anchors and section pointers resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
