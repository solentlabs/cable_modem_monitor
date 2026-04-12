"""Tests for post-analysis JS endpoint discovery.

Table-driven tests for the pure extraction function.
Fixture-driven tests for the end-to-end detection.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.mcp.analysis.js_endpoints import (
    detect_uncaptured_endpoints,
    extract_endpoints_from_js,
)

from tests.conftest import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "js_endpoints"
FIXTURES = collect_fixtures(FIXTURES_DIR)


# =====================================================================
# extract_endpoints_from_js — table-driven
# =====================================================================

# fmt: off
_EXTRACTION_CASES = [
    # (js_source, expected_endpoints, description)
    (
        '$.ajax({type:"POST",url:"php/getData.php",dataType:"json"})',
        ["php/getData.php"],
        "jQuery ajax with url in options",
    ),
    (
        '$.ajax({url: "php/getData.php"})',
        ["php/getData.php"],
        "jQuery ajax minimal",
    ),
    (
        "$.ajax({url: 'php/getData.php'})",
        ["php/getData.php"],
        "jQuery ajax single quotes",
    ),
    (
        '$.post("api/logout", data)',
        ["api/logout"],
        "jQuery post shorthand",
    ),
    (
        '$.get("api/status")',
        ["api/status"],
        "jQuery get shorthand",
    ),
    (
        'createServerRecord("php/ajaxSet_Password.php", data, null)',
        ["php/ajaxSet_Password.php"],
        "Arris createServerRecord",
    ),
    (
        'fetch("/api/status")',
        ["/api/status"],
        "fetch API",
    ),
    (
        '.open("POST", "../../../php/ajaxSet_Session.php")',
        ["../../../php/ajaxSet_Session.php"],
        "XMLHttpRequest open",
    ),
    (
        'var x = "hello world"',
        [],
        "plain string assignment",
    ),
    (
        "$.ajax({url: iconPath})",
        [],
        "variable reference not string literal",
    ),
    (
        '$.cachedScript("skins/vod/js/base.js")',
        [],
        "static JS resource not an endpoint",
    ),
    (
        '$.get("php/" + modbase + "_data.php")',
        [],
        "directory prefix from string concatenation",
    ),
    (
        'url: "styles/global.css"',
        [],
        "CSS resource not an endpoint",
    ),
    (
        '$.ajax({url:"php/first.php"}); $.post("php/second.php")',
        ["php/first.php", "php/second.php"],
        "multiple endpoints in one source",
    ),
    # --- Resilience: nested objects before url property ---
    (
        '$.ajax({beforeSend: function(xhr) { xhr.set("X", "v"); }, url: "php/data.php"})',
        ["php/data.php"],
        "nested callback before url property",
    ),
    (
        '$.ajax({\n  success: function(msg) {\n    if (msg.ok) { update(); }\n  },\n  url: "php/status.php"\n})',
        ["php/status.php"],
        "multiline nested function before url",
    ),
    # --- Resilience: jQuery.ajax and $.getJSON variants ---
    (
        'jQuery.ajax({url: "php/getData.php"})',
        ["php/getData.php"],
        "jQuery.ajax full name",
    ),
    (
        '$.getJSON("api/channels.json")',
        ["api/channels.json"],
        "jQuery getJSON shorthand",
    ),
    (
        'jQuery.post("php/save.php")',
        ["php/save.php"],
        "jQuery.post full name",
    ),
    # --- Resilience: commented-out code ---
    (
        '// $.ajax({url: "php/old.php"})\n$.ajax({url: "php/real.php"})',
        ["php/real.php"],
        "line comment ignored",
    ),
    (
        '/* $.ajax({url: "php/old.php"}) */\n$.ajax({url: "php/real.php"})',
        ["php/real.php"],
        "block comment ignored",
    ),
    (
        '// Old: createServerRecord("php/removed.php", null)',
        [],
        "entire line commented out",
    ),
]
# fmt: on


@pytest.mark.parametrize(
    "js_source,expected,desc",
    _EXTRACTION_CASES,
    ids=[c[2] for c in _EXTRACTION_CASES],
)
def test_extract_endpoints_from_js(
    js_source: str,
    expected: list[str],
    desc: str,
) -> None:
    """Extraction function returns expected endpoints for each pattern."""
    result = extract_endpoints_from_js(js_source)
    assert sorted(result) == sorted(expected)


# =====================================================================
# detect_uncaptured_endpoints — fixture-driven
# =====================================================================


@pytest.mark.parametrize(
    "fixture_path",
    FIXTURES,
    ids=[f.stem for f in FIXTURES],
)
def test_detect_uncaptured_endpoints(fixture_path: Path) -> None:
    """Uncaptured endpoints produce expected warnings."""
    data = load_fixture(fixture_path)
    warnings: list[str] = []
    detect_uncaptured_endpoints(data["_entries"], warnings)

    expected = data["_expected_warnings"]
    if not expected:
        assert not warnings, f"Expected no warnings, got {warnings}"
    else:
        for keyword in expected:
            assert any(keyword in w for w in warnings), f"Expected warning containing {keyword!r}, got {warnings}"


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in FIXTURES if load_fixture(f)["_expected_warnings"]],
    ids=[f.stem for f in FIXTURES if load_fixture(f)["_expected_warnings"]],
)
def test_warning_count_matches_expected(fixture_path: Path) -> None:
    """Number of warnings matches number of expected uncaptured endpoints."""
    data = load_fixture(fixture_path)
    warnings: list[str] = []
    detect_uncaptured_endpoints(data["_entries"], warnings)
    assert len(warnings) == len(data["_expected_warnings"])
