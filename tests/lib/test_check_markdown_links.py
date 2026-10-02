"""Tests for scripts/check_markdown_links.py.

The link checker gates ``make link-check``. Like every gate, its failure
mode is silence: a resolver that returns None too eagerly reports "all
links resolve" over a broken tree, and nothing downstream notices.

Coverage breakdown per docs/CODE_REVIEW.md § Test File Standards:
- ``_resolve`` link classification — table-driven inline.
- ``_check_link``, ``_named_spans`` and the § pointer rules —
  behavioural, over small Markdown trees built in ``tmp_path``.
- ``_slugify`` — table-driven inline; anchor fragments — behavioural.
- Guard cases (external URLs, fenced content, one-word bold inlines,
  HACS blob URLs, explicit anchors, non-Markdown targets) are each
  paired with a live counterpart asserting the same rule still fires
  outside the guard, per § Gate Scripts Require Tests.

Deliberately not tested: whether a pointer names a heading at all. The
module docstring excludes it by design (a partial name is
indistinguishable from a stale one), so a test asserting it would pin
behavior the script never claims.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fixture_helpers import load_script

_mod = load_script("scripts/check_markdown_links.py")

_BLOB = "https://github.com/solentlabs/cable_modem_monitor/blob/main"


# ---------------------------------------------------------------------------
# _resolve — link classification
# ---------------------------------------------------------------------------

# fmt: off
SKIPPED = [
    pytest.param("https://example.com/page",       id="external-https"),
    pytest.param("http://example.com/page",        id="external-http"),
    pytest.param("mailto:someone@example.com",     id="mailto"),
    pytest.param("//cdn.example.com/x.js",         id="protocol-relative"),
    pytest.param("#in-page-anchor",                id="pure-anchor"),
]

RESOLVED = [
    pytest.param("./sibling.md",        "docs/sibling.md",     id="dot-relative"),
    pytest.param("sibling.md",          "docs/sibling.md",     id="bare-relative"),
    pytest.param("../root.md",          "root.md",             id="parent-relative"),
    pytest.param("/root.md",            "root.md",             id="repo-absolute"),
    pytest.param("nested/deep.md",      "docs/nested/deep.md", id="subdirectory"),
    pytest.param("sibling.md#heading",  "docs/sibling.md",     id="anchor-stripped"),
    pytest.param("sibling.md?raw=1",    "docs/sibling.md",     id="query-stripped"),
    pytest.param(f"{_BLOB}/root.md",    "root.md",             id="repo-blob-url"),
    pytest.param(f"{_BLOB}/root.md#x",  "root.md",             id="repo-blob-url-anchor"),
]
# fmt: on


@pytest.mark.parametrize("target", SKIPPED)
def test_external_targets_are_skipped(target: str, tmp_path: Path) -> None:
    """External and in-page targets are not this checker's concern."""
    assert _mod._resolve(target, tmp_path / "docs" / "a.md", tmp_path) is None


@pytest.mark.parametrize(("target", "expected"), RESOLVED)
def test_intra_repo_target_resolves(target: str, expected: str, tmp_path: Path) -> None:
    """Every intra-repo link class resolves to the right path."""
    resolved = _mod._resolve(target, tmp_path / "docs" / "a.md", tmp_path)
    assert resolved is not None
    assert Path(resolved).resolve() == (tmp_path / expected).resolve()


def test_skip_guard_does_not_swallow_a_relative_link() -> None:
    """Live counterpart to the external-URL guard.

    The guard matches a leading ``scheme:``. A filename merely containing
    a colon must still resolve rather than being waved through.
    """
    assert _mod._resolve("notes.md", Path("/repo/docs/a.md"), Path("/repo")) is not None


# ---------------------------------------------------------------------------
# _check_link — reporting
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Minimal repo: docs/a.md plus an existing docs/sibling.md."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "sibling.md").write_text("# Sibling\n", encoding="utf-8")
    (tmp_path / "docs" / "a.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Root\n", encoding="utf-8")
    return tmp_path


def test_missing_target_is_reported(repo: Path) -> None:
    problem = _mod._check_link("./gone.md", repo / "docs" / "a.md", 7, repo, set())
    assert problem is not None
    assert "missing:" in problem
    assert "docs/a.md:7" in problem


def test_existing_target_is_not_reported(repo: Path) -> None:
    assert _mod._check_link("./sibling.md", repo / "docs" / "a.md", 7, repo, set()) is None


def test_relative_link_in_hacs_readme_is_reported_even_when_it_exists(repo: Path) -> None:
    """HACS cannot resolve repo-relative paths, so existence is irrelevant."""
    problem = _mod._check_link("./docs/sibling.md", repo / "README.md", 3, repo, {repo / "README.md"})
    assert problem is not None
    assert "HACS README" in problem


def test_hacs_rule_does_not_fire_on_an_absolute_blob_url(repo: Path) -> None:
    """Live counterpart: the absolute form HACS requires is accepted."""
    assert _mod._check_link(f"{_BLOB}/docs/sibling.md", repo / "README.md", 3, repo, {repo / "README.md"}) is None


def test_hacs_rule_is_scoped_to_hacs_files(repo: Path) -> None:
    """Live counterpart: the same relative link elsewhere is fine."""
    assert _mod._check_link("./sibling.md", repo / "docs" / "a.md", 3, repo, {repo / "README.md"}) is None


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------

# fmt: off
TOKENS = [
    pytest.param("Session concurrency",        ["session", "concurrency"],   id="plain"),
    pytest.param("**Bold inline.**",           ["bold", "inline"],           id="markup-stripped"),
    pytest.param("`get_modem_data` path",      ["get_modem_data", "path"],   id="underscore-kept"),
    pytest.param("Boot-time checks",           ["boot-time", "checks"],      id="hyphen-kept"),
    pytest.param("Aggregate — derived",        ["aggregate", "derived"],     id="em-dash-dropped"),
]
# fmt: on


@pytest.mark.parametrize(("text", "expected"), TOKENS)
def test_tokenize(text: str, expected: list[str]) -> None:
    """Underscores and hyphens are load-bearing inside identifiers; other punctuation is not."""
    assert _mod._tokenize(text) == expected


# ---------------------------------------------------------------------------
# _named_spans — headings vs bold inlines
# ---------------------------------------------------------------------------


def test_named_spans_collects_headings_and_bolds(tmp_path: Path) -> None:
    doc = tmp_path / "d.md"
    doc.write_text(
        "# Title\n\n## Aggregate (Derived Fields)\n\nSome **bold inline** here.\n",
        encoding="utf-8",
    )
    headings, bolds = _mod._named_spans(doc)
    assert ["title"] in headings
    assert ["aggregate", "derived", "fields"] in headings
    # The parenthetical-stripped variant is registered too, so a prose
    # reference may cite the shorter form.
    assert ["aggregate"] in headings
    assert ["bold", "inline"] in bolds


def test_named_spans_ignores_fenced_content(tmp_path: Path) -> None:
    doc = tmp_path / "d.md"
    doc.write_text("# Real\n\n```\n## Fenced Heading\n**fenced bold**\n```\n", encoding="utf-8")
    headings, bolds = _mod._named_spans(doc)
    assert ["fenced", "heading"] not in headings
    assert ["fenced", "bold"] not in bolds


def test_fence_guard_does_not_swallow_unfenced_names(tmp_path: Path) -> None:
    """Live counterpart: identical content outside a fence is collected."""
    doc = tmp_path / "d.md"
    doc.write_text("## Fenced Heading\n\n**fenced bold**\n", encoding="utf-8")
    headings, bolds = _mod._named_spans(doc)
    assert ["fenced", "heading"] in headings
    assert ["fenced", "bold"] in bolds


# ---------------------------------------------------------------------------
# _matches — prefix comparison
# ---------------------------------------------------------------------------


def test_matches_accepts_an_abbreviated_reference() -> None:
    """A pointer may cite a shorter prefix of a longer heading."""
    assert _mod._matches(["session", "concurrency"], [["session", "concurrency", "ssot"]]) is not None


def test_matches_accepts_prose_running_past_the_name() -> None:
    """...and the citing prose may run on past the heading name."""
    assert _mod._matches(["aggregate", "is", "an", "example"], [["aggregate"]]) is not None


def test_matches_rejects_a_different_name() -> None:
    """Live counterpart: prefix comparison is not a wildcard."""
    assert _mod._matches(["session", "concurrency"], [["transport", "selection"]]) is None


# ---------------------------------------------------------------------------
# Section pointers — the bold-inline rule
# ---------------------------------------------------------------------------


def _scan(repo_root: Path, md_file: Path) -> list[str]:
    basenames: dict[str, list[Path]] = {}
    for path in repo_root.rglob("*.md"):
        basenames.setdefault(path.name, []).append(path)
    problems: list[str] = _mod._scan_file(md_file, repo_root, set(), basenames, {}, {})
    return problems


def test_pointer_at_a_bold_inline_is_reported(tmp_path: Path) -> None:
    doc = tmp_path / "d.md"
    doc.write_text(
        "# Doc\n\n**Structured cookies arrays.** Explanation here.\n\nSee § Structured cookies arrays for detail.\n",
        encoding="utf-8",
    )
    problems = _scan(tmp_path, doc)
    assert any("bold inline, not a heading" in p for p in problems)


def test_pointer_at_a_real_heading_is_not_reported(tmp_path: Path) -> None:
    """Live counterpart: the rule does not fire on a valid pointer."""
    doc = tmp_path / "d.md"
    doc.write_text(
        "# Doc\n\n## Structured cookies arrays\n\nSee § Structured cookies arrays for detail.\n",
        encoding="utf-8",
    )
    assert _scan(tmp_path, doc) == []


def test_single_word_bold_is_not_reported(tmp_path: Path) -> None:
    """A one-word bold (**ICMP**) matches too much prose to be evidence."""
    doc = tmp_path / "d.md"
    doc.write_text("# Doc\n\n**ICMP** is used here.\n\nSee § ICMP handling for detail.\n", encoding="utf-8")
    assert _scan(tmp_path, doc) == []


def test_multi_word_bold_guard_still_fires(tmp_path: Path) -> None:
    """Live counterpart to the one-word guard: two words is evidence."""
    doc = tmp_path / "d.md"
    doc.write_text("# Doc\n\n**ICMP handling** is here.\n\nSee § ICMP handling for detail.\n", encoding="utf-8")
    assert any("bold inline" in p for p in _scan(tmp_path, doc))


def test_qualified_pointer_resolves_against_the_named_document(tmp_path: Path) -> None:
    """`OTHER.md § Name` is read against OTHER.md, not the citing file."""
    (tmp_path / "OTHER.md").write_text("# Other\n\n**Retry budget policy.** Text.\n", encoding="utf-8")
    doc = tmp_path / "d.md"
    doc.write_text("# Doc\n\nSee `OTHER.md` § Retry budget policy for detail.\n", encoding="utf-8")
    problems = _scan(tmp_path, doc)
    assert any("OTHER.md" in p for p in problems)


def test_broken_link_and_pointer_are_both_collected(tmp_path: Path) -> None:
    """_scan_file reports both classes, not just whichever runs first."""
    doc = tmp_path / "d.md"
    doc.write_text(
        "# Doc\n\n**Retry budget policy.** Text.\n\n[gone](./missing.md)\n\nSee § Retry budget policy.\n",
        encoding="utf-8",
    )
    problems = _scan(tmp_path, doc)
    assert any("missing:" in p for p in problems)
    assert any("bold inline" in p for p in problems)


def test_links_inside_a_fence_are_not_checked(tmp_path: Path) -> None:
    doc = tmp_path / "d.md"
    doc.write_text("# Doc\n\n```markdown\n[example](./nowhere.md)\n```\n", encoding="utf-8")
    assert _scan(tmp_path, doc) == []


def test_fence_guard_does_not_swallow_unfenced_links(tmp_path: Path) -> None:
    """Live counterpart: the same link outside a fence is reported."""
    doc = tmp_path / "d.md"
    doc.write_text("# Doc\n\n[example](./nowhere.md)\n", encoding="utf-8")
    assert any("missing:" in p for p in _scan(tmp_path, doc))


# ---------------------------------------------------------------------------
# _slugify — GitHub heading anchors
# ---------------------------------------------------------------------------

# fmt: off
SLUGS = [
    pytest.param("Available Sensors",                "available-sensors",              id="plain"),
    pytest.param("Step 2 — Review for PII",          "step-2--review-for-pii",         id="em-dash-double-hyphen"),
    pytest.param("`get_modem_data` path",            "get_modem_data-path",            id="code-span-underscore-kept"),
    pytest.param("**Bold** and *em*",                "bold-and-em",                    id="emphasis-stripped"),
    pytest.param("See [the spec](./SPEC.md) here",   "see-the-spec-here",              id="link-text-kept"),
    pytest.param("What's new? (v3.14)",              "whats-new-v314",                 id="punctuation-dropped"),
    pytest.param("Boot-time checks",                 "boot-time-checks",               id="hyphen-kept"),
    pytest.param("Café Überblick",                   "café-überblick",                 id="unicode-letters-kept"),
    pytest.param("Absent in `<script>` tag",         "absent-in-script-tag",           id="html-in-code-span-kept"),
    pytest.param("Html <b>bold</b> tag",             "html-bold-tag",                  id="html-outside-code-dropped"),
    pytest.param("\u26a0\ufe0f Breaking change",      "\ufe0f-breaking-change",          id="combining-mark-kept"),
    pytest.param("Image ![alt](i.png) here",         "image--here",                    id="image-alt-dropped"),
    pytest.param("Under_score __bold__",             "under_score-bold",               id="underscore-bold-stripped"),
    pytest.param("_em_ text",                        "em-text",                        id="underscore-em-stripped"),
]
# fmt: on


@pytest.mark.parametrize(("heading", "expected"), SLUGS)
def test_slugify(heading: str, expected: str) -> None:
    """Heading text slugifies the way GitHub renders its anchor."""
    assert _mod._slugify(heading) == expected


# ---------------------------------------------------------------------------
# Anchor fragments
# ---------------------------------------------------------------------------

_TARGET_DOC = (
    "# Target\n\n"
    "## Available Sensors\n\n"
    "## Setup\n\n"
    "## Setup\n\n"
    '<span id="bcm3390"></span>\n\n'
    '<a name="legacy-name"></a>\n\n'
    '`<span id="in-code-span">`\n\n'
    '    <span id="in-indented-block"></span>\n\n'
    "Setext Title\n============\n\n"
    "Setext Two\n----------\n\n"
    "Plain paragraph\n\n---\n\n"
    "```markdown\n## Fenced Heading\n```\n"
)


@pytest.fixture
def anchor_repo(tmp_path: Path) -> Path:
    """docs/target.md with headings, a duplicate, explicit ids and a fenced heading."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "target.md").write_text(_TARGET_DOC, encoding="utf-8")
    (tmp_path / "docs" / "tool.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def _scan_link(repo_root: Path, target: str) -> list[str]:
    """Scan a docs/a.md that holds one link to target."""
    doc = repo_root / "docs" / "a.md"
    doc.write_text(f"# A\n\n## Local Heading\n\n[x]({target})\n", encoding="utf-8")
    return _scan(repo_root, doc)


# fmt: off
LIVE_ANCHORS = [
    pytest.param("./target.md#available-sensors",          id="heading"),
    pytest.param("./target.md#setup",                      id="first-duplicate"),
    pytest.param("./target.md#setup-1",                    id="second-duplicate"),
    pytest.param("./target.md#bcm3390",                    id="span-id"),
    pytest.param("./target.md#legacy-name",                id="a-name"),
    pytest.param("./target.md#setext-title",               id="setext-h1"),
    pytest.param("./target.md#setext-two",                 id="setext-h2"),
    pytest.param("#local-heading",                         id="in-page"),
    pytest.param(f"{_BLOB}/docs/target.md#setup",          id="blob-url"),
    pytest.param("./target.md#available%2Dsensors",        id="percent-encoded"),
    pytest.param("./tool.py#L1",                           id="non-markdown-target"),
    pytest.param("./target.md",                            id="no-fragment"),
]

DEAD_ANCHORS = [
    pytest.param("./target.md#available-sensor",           id="heading-renamed"),
    pytest.param("./target.md#setup-2",                    id="duplicate-past-last"),
    pytest.param("./target.md#fenced-heading",             id="fenced-heading"),
    pytest.param("#no-such-heading",                       id="in-page"),
    pytest.param(f"{_BLOB}/docs/target.md#gone",           id="blob-url"),
    pytest.param("./target.md#Available-Sensors",          id="case-differs"),
    pytest.param("./target.md#in-code-span",               id="id-in-code-span"),
    pytest.param("./target.md#in-indented-block",          id="id-in-indented-block"),
    pytest.param("./target.md#plain-paragraph",            id="paragraph-before-rule"),
]
# fmt: on


@pytest.mark.parametrize("target", LIVE_ANCHORS)
def test_live_anchor_is_not_reported(target: str, anchor_repo: Path) -> None:
    """Headings, duplicate suffixes and explicit ids all count as anchors."""
    assert _scan_link(anchor_repo, target) == []


@pytest.mark.parametrize("target", DEAD_ANCHORS)
def test_dead_anchor_is_reported(target: str, anchor_repo: Path) -> None:
    """Live counterpart to every guard above: a fragment naming nothing fires."""
    problems = _scan_link(anchor_repo, target)
    assert len(problems) == 1
    assert "no anchor" in problems[0]
    assert "docs/a.md:5" in problems[0]


# fmt: off
CODE_GUARDS = [
    pytest.param("`[x](#gone)`\n",                     id="inline-code-span"),
    pytest.param("Para.\n\n    [x](#gone)\n",          id="indented-code-block"),
]

CODE_GUARD_COUNTERPARTS = [
    pytest.param("[x](#gone)\n",                       id="outside-code-span"),
    pytest.param("[`code`](#gone)\n",                  id="code-span-as-link-text"),
    pytest.param("- item\n\n    [x](#gone)\n",         id="list-continuation"),
]
# fmt: on


@pytest.mark.parametrize("body", CODE_GUARDS)
def test_link_inside_code_is_not_checked(body: str, tmp_path: Path) -> None:
    """A link written as code is example text, not a link."""
    doc = tmp_path / "a.md"
    doc.write_text(f"# A\n\n{body}", encoding="utf-8")
    assert _scan(tmp_path, doc) == []


@pytest.mark.parametrize("body", CODE_GUARD_COUNTERPARTS)
def test_code_guard_does_not_swallow_real_links(body: str, tmp_path: Path) -> None:
    """Live counterpart: the same link outside code, or indented under a list item, fires."""
    doc = tmp_path / "a.md"
    doc.write_text(f"# A\n\n{body}", encoding="utf-8")
    assert any("no anchor" in p for p in _scan(tmp_path, doc))


def test_explicit_id_guard_is_specific(anchor_repo: Path) -> None:
    """Live counterpart to the explicit-id guard: only the declared id is accepted."""
    assert _scan_link(anchor_repo, "./target.md#bcm3391") != []


def test_non_markdown_guard_still_checks_markdown(anchor_repo: Path) -> None:
    """Live counterpart to the non-Markdown guard: the same fragment on a .md fires."""
    assert any("no anchor" in p for p in _scan_link(anchor_repo, "./target.md#L1"))


def test_missing_file_is_not_also_an_anchor_report(anchor_repo: Path) -> None:
    """A link to a missing file reports the file once, not a second anchor line."""
    problems = _scan_link(anchor_repo, "./gone.md#setup")
    assert len(problems) == 1
    assert "missing:" in problems[0]


def test_fenced_link_anchor_is_not_checked(anchor_repo: Path) -> None:
    """A dead anchor inside a fence is example text, not a link."""
    doc = anchor_repo / "docs" / "a.md"
    doc.write_text("# A\n\n```markdown\n[x](./target.md#gone)\n```\n", encoding="utf-8")
    assert _scan(anchor_repo, doc) == []


# ---------------------------------------------------------------------------
# Real-repo regression
# ---------------------------------------------------------------------------


def test_repo_markdown_links_all_resolve() -> None:
    """The committed tree must stay clean — this is what make link-check runs."""
    assert _mod.main() == 0
