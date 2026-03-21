"""Tests for JSEmbeddedParser.

Fixture-driven tests with synthesized HTML snippets. Each fixture contains
an HTML page with JS functions, a JSFunction config, and expected channel
output. No modem-specific references.

Adding a test case = drop a JSON file in fixtures/js_embedded/valid/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup
from solentlabs.cable_modem_monitor_core.models.parser_config.javascript import (
    JSFunction,
)
from solentlabs.cable_modem_monitor_core.parsers.js_embedded import (
    JSEmbeddedParser,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "js_embedded"
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
    """Parse JS-embedded data and verify extracted channels match expected."""
    data = _load_fixture(fixture_path)

    resource_key = data["_resource"]
    resources = _build_resources(data.get("_html"), resource_key)

    func_config = JSFunction(**data["_function"])
    parser = JSEmbeddedParser(resource_key, func_config)

    result = parser.parse(resources)
    expected = data["_expected"]

    assert result == expected, (
        f"Mismatch for {fixture_path.stem}:\n" f"  actual:   {result}\n" f"  expected: {expected}"
    )
