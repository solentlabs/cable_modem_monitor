"""Tests for JSJsonParser.

Fixture-driven tests with synthesized HTML snippets containing JSON arrays
in JS variable assignments. Each fixture contains an HTML page, a
JSJsonSection config, and expected channel output. No modem-specific references.

Adding a test case = drop a JSON file in fixtures/js_json_parser/valid/
(flat form) or fixtures/js_json_parser/arrays/ (object variable, ``arrays``).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from solentlabs.cable_modem_monitor_core.models.parser_config.js_json import (
    JSJsonSection,
)
from solentlabs.cable_modem_monitor_core.parsers.formats.js_json_parser import JSJsonParser
from solentlabs.cable_modem_monitor_core.parsers.registries import _parse_js_json_channels

from tests._helpers import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "js_json_parser"
VALID_FIXTURES = collect_fixtures(FIXTURES_DIR / "valid")


def _build_resources(html: str | None, resource_key: str) -> dict[str, BeautifulSoup]:
    """Build a resource dict. Returns empty dict if html is None."""
    if html is None:
        return {}
    return {resource_key: BeautifulSoup(html, "html.parser")}


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=[f.stem for f in VALID_FIXTURES],
)
def test_extraction(fixture_path: Path) -> None:
    """Parse JS JSON channels and verify extracted data matches expected."""
    data = load_fixture(fixture_path)

    config = JSJsonSection.model_validate(data["_config"])
    resources = _build_resources(data.get("_html"), config.resource)

    parser = JSJsonParser(config)
    result = parser.parse(resources)
    expected = data["_expected"]

    assert result == expected, (
        f"Mismatch for {fixture_path.stem}:\n" f"  actual:   {result}\n" f"  expected: {expected}"
    )


# The arrays form merges companions and assigns channel_number in the
# registry wrapper (as the table format does), so these fixtures run the
# whole section through it. ``_expected_warning`` is a substring of the
# one WARNING expected, or null when the parse must stay silent.
ARRAYS_FIXTURES = collect_fixtures(FIXTURES_DIR / "arrays")


@pytest.mark.parametrize(
    "fixture_path",
    ARRAYS_FIXTURES,
    ids=[f.stem for f in ARRAYS_FIXTURES],
)
def test_arrays_form_extraction(fixture_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Parse an object variable's arrays, merging companions into primaries."""
    data = load_fixture(fixture_path)

    config = JSJsonSection.model_validate(data["_config"])
    resources = _build_resources(data.get("_html"), config.resource)

    with caplog.at_level(logging.WARNING):
        result, _ = _parse_js_json_channels(config, resources)

    assert result == data["_expected"]
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    expected_warning = data["_expected_warning"]
    if expected_warning is None:
        assert warnings == []
    else:
        assert any(expected_warning in message for message in warnings), warnings
