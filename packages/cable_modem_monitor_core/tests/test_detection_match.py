"""Tests for detection.match_page() — the pure page-text matcher.

Table-driven. Names are invented: the matcher knows nothing about any
modem, so the tables prove the rule (whole-word token runs over catalog
names), not a fleet. Contract: DETECTION_SPEC.md § Matching.
"""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_core.catalog_manager import ModemSummary
from solentlabs.cable_modem_monitor_core.detection import Observation, describe_response, match_page


def _summary(
    manufacturer: str,
    model: str,
    *,
    aliases: list[str] | None = None,
    brands: list[str] | None = None,
) -> ModemSummary:
    return ModemSummary(manufacturer=manufacturer, model=model, model_aliases=aliases or [], brands=brands or [])


CATALOG = [
    _summary("Acme", "AB600"),
    _summary("Acme", "AB6000"),
    _summary("ACME", "Widget Pro", brands=["Cosmos"]),
    _summary("Bolt", "F3896LG-VMB", aliases=["Hub 5"], brands=["Cosmos", "Play"]),
]

MATCH_CASES = [
    ("<title>Acme AB600</title>", ["AB600"], ["Acme"], ["Acme", "AB600"], "model-and-maker"),
    ("AB6000 status", ["AB6000"], [], ["AB6000"], "longer-sibling-only"),
    ("AB60000", [], [], [], "digit-run-longer"),
    ("xAB600", [], [], [], "prefix-glued"),
    ("AB600-B", ["AB600"], [], ["AB600"], "suffix-separated"),
    ("AB-600", [], [], [], "split-token"),
    ("Widget   Pro login", ["Widget Pro"], [], ["Widget   Pro"], "multi-word-spaces"),
    ("widget-pro", ["Widget Pro"], [], ["widget-pro"], "multi-word-hyphen"),
    ("Widget Proxy", [], [], [], "multi-word-prefix-only"),
    ("Pro Widget", [], [], [], "multi-word-reordered"),
    ("Widget", [], [], [], "multi-word-half"),
    ("F3896LG VMB", ["F3896LG-VMB"], [], ["F3896LG VMB"], "hyphenated-model"),
    ("Welcome to Hub 5", ["F3896LG-VMB"], [], ["Hub 5"], "alias"),
    ("Hub 50", [], [], [], "alias-longer-number"),
    ("Cosmos broadband", [], ["Cosmos"], ["Cosmos"], "brand-only"),
    ("Acme router", [], ["Acme"], ["Acme"], "maker-only"),
    ("ACME ab600", ["AB600"], ["Acme"], ["ACME", "ab600"], "page-spelling-kept"),
    ("Acme Acme AB600 AB600", ["AB600"], ["Acme"], ["Acme", "AB600"], "repeats-listed-once"),
    ("AB600 then Acme", ["AB600"], ["Acme"], ["AB600", "Acme"], "matched-in-page-order"),
    ("Play", [], ["Play"], ["Play"], "generic-word-brand-hits"),
    ("nothing to see here", [], [], [], "no-hit"),
    ("", [], [], [], "empty-page"),
    ("åB600 ẞB600", [], [], [], "non-ascii-letters-split"),
]


@pytest.mark.parametrize(
    ("text", "models", "buckets", "matched", "case_id"), MATCH_CASES, ids=[c[-1] for c in MATCH_CASES]
)
def test_match_page(text: str, models: list[str], buckets: list[str], matched: list[str], case_id: str) -> None:
    result = match_page(text, CATALOG)

    assert [s.model for s in result.models] == models
    assert result.buckets == buckets
    assert result.matched == matched


def test_buckets_list_each_name_once_in_first_catalog_spelling() -> None:
    """Acme and ACME are one manufacturer name; Cosmos is a brand of two entries."""
    result = match_page("ACME Cosmos", CATALOG)

    assert result.buckets == ["Acme", "Cosmos"]


def test_models_lists_every_matching_entry_in_catalog_order() -> None:
    """No scoring: two entries naming the same alias both come back."""
    catalog = [_summary("One", "X1", aliases=["Shared"]), _summary("Two", "Y2", aliases=["Shared"])]

    result = match_page("Shared", catalog)

    assert [s.model for s in result.models] == ["X1", "Y2"]


def test_models_and_buckets_are_independent() -> None:
    """A page can name a maker and no model, and a model without its maker."""
    assert match_page("Acme", CATALOG).models == []
    assert match_page("AB600", CATALOG).buckets == []


@pytest.mark.parametrize("name", ["", "-", "  "])
def test_name_without_tokens_never_matches(name: str) -> None:
    catalog = [_summary("Acme", "AB600", aliases=[name], brands=[name])]

    result = match_page("anything - at all", catalog)

    assert result.models == []
    assert result.buckets == []
    assert result.matched == []


DESCRIBE_CASES = [
    ("http://h/", {}, b"", Observation("http", 200, "/", None, None, None, False), "\n", "bare"),
    (
        "https://h/a/b.html?x=1",
        {"server": "S"},
        b"<TITLE>\n Hi   there </TITLE>",
        Observation("https", 200, "/a/b.html", "S", "Hi there", None, False),
        "S\n<TITLE>\n Hi   there </TITLE>",
        "path-title-lowercase-header",
    ),
    (
        "http://h/",
        {"WWW-Authenticate": "Basic"},
        b"<input name=p type='password'>",
        Observation("http", 200, "/", None, None, "Basic", True),
        "\n<input name=p type='password'>",
        "challenge-and-password",
    ),
    (
        "http://h/",
        {},
        b"<input type=text name=password>",
        Observation("http", 200, "/", None, None, None, False),
        "\n<input type=text name=password>",
        "password-name-is-not-a-password-field",
    ),
    (
        "http://h",
        {},
        b"\xff\xfeAB600",
        Observation("http", 200, "/", None, None, None, False),
        "\n\ufffd\ufffdAB600",
        "undecodable-bytes-replaced",
    ),
]


@pytest.mark.parametrize(
    ("url", "headers", "body", "observation", "text", "case_id"), DESCRIBE_CASES, ids=[c[-1] for c in DESCRIBE_CASES]
)
def test_describe_response(
    url: str, headers: dict[str, str], body: bytes, observation: Observation, text: str, case_id: str
) -> None:
    assert describe_response(url, 200, headers, body) == (observation, text)


def test_describe_response_cuts_the_body_at_the_cap() -> None:
    _, text = describe_response("http://h/", 200, {}, b"a" * (256 * 1024) + b"tail")

    assert len(text) == 1 + 256 * 1024
    assert "tail" not in text
