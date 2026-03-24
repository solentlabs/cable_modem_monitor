"""Tests for HTMLFieldsParser.

Fixture-driven tests with synthesized HTML snippets for system_info
extraction via label, id, and CSS selectors. No modem-specific references.

Adding a test case = drop a JSON file in fixtures/html_fields/valid/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup
from solentlabs.cable_modem_monitor_core.models.parser_config.system_info import (
    HTMLFieldsSource,
)
from solentlabs.cable_modem_monitor_core.parsers.formats.html_fields import HTMLFieldsParser

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html_fields"
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
    """Parse HTML fields and verify extracted system_info matches expected."""
    data = _load_fixture(fixture_path)

    source = HTMLFieldsSource(**data["_source"])
    resources = _build_resources(data.get("_html"), source.resource)

    parser = HTMLFieldsParser(source)
    result = parser.parse(resources)
    expected = data["_expected"]

    assert result == expected, (
        f"Mismatch for {fixture_path.stem}:\n" f"  actual:   {result}\n" f"  expected: {expected}"
    )
