"""Tests for JSJsonParser.

Fixture-driven tests with synthesized HTML snippets containing JSON arrays
in JS variable assignments. Each fixture contains an HTML page, a
JSJsonSection config, and expected channel output. No modem-specific references.

Adding a test case = drop a JSON file in fixtures/js_json_parser/valid/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup
from solentlabs.cable_modem_monitor_core.models.parser_config.js_json import (
    JSJsonSection,
)
from solentlabs.cable_modem_monitor_core.parsers.formats.js_json_parser import JSJsonParser

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "js_json_parser"
VALID_FIXTURES = sorted((FIXTURES_DIR / "valid").glob("*.json"))


def _load_fixture(path: Path) -> dict[str, Any]:
    """Load a JSON fixture file."""
    return dict(json.loads(path.read_text()))


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
    data = _load_fixture(fixture_path)

    config = JSJsonSection(**data["_config"])
    resources = _build_resources(data.get("_html"), config.resource)

    parser = JSJsonParser(config)
    result = parser.parse(resources)
    expected = data["_expected"]

    assert result == expected, (
        f"Mismatch for {fixture_path.stem}:\n" f"  actual:   {result}\n" f"  expected: {expected}"
    )
