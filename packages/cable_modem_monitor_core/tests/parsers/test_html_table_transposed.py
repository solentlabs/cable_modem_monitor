"""Tests for HTMLTableTransposedParser.

Fixture-driven tests with synthesized HTML snippets. Each fixture contains
HTML, transposed table config, and expected channel output. No modem-specific
references.

Adding a test case = drop a JSON file in fixtures/html_table_transposed/valid/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup
from solentlabs.cable_modem_monitor_core.models.parser_config.transposed import (
    TransposedTableDefinition,
)
from solentlabs.cable_modem_monitor_core.parsers.html_table_transposed import (
    HTMLTableTransposedParser,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html_table_transposed"
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
    """Parse transposed HTML table and verify extracted channels match expected."""
    data = _load_fixture(fixture_path)

    resource_key = data["_resource"]
    # Allow fixtures to specify a different key for the resource dict
    resource_dict_key = data.get("_resource_key", resource_key)
    resources = _build_resources(data.get("_html"), resource_dict_key)

    table_def = TransposedTableDefinition(**data["_config"])
    parser = HTMLTableTransposedParser(resource_key, table_def)

    result = parser.parse(resources)
    expected = data["_expected"]

    assert result == expected, (
        f"Mismatch for {fixture_path.stem}:\n" f"  actual:   {result}\n" f"  expected: {expected}"
    )
