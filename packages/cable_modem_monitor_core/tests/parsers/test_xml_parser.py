"""Tests for XMLChannelParser.

Fixture-driven tests with synthesized XML data. Each fixture contains
an XML string, an XMLSection config, and expected channel output.

Adding a test case = drop a JSON file in fixtures/xml_parser/valid/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import defusedxml.ElementTree as DefusedET
import pytest
from solentlabs.cable_modem_monitor_core.models.parser_config.xml_format import (
    XMLSection,
)
from solentlabs.cable_modem_monitor_core.parsers.formats.xml_parser import (
    XMLChannelParser,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "xml_parser"
VALID_FIXTURES = sorted((FIXTURES_DIR / "valid").glob("*.json"))


def _load_fixture(path: Path) -> dict[str, Any]:
    """Load a JSON fixture file."""
    return dict(json.loads(path.read_text()))


def _build_resources(
    xml_str: str | None,
    resource_key: str,
) -> dict[str, Any]:
    """Build a resource dict with parsed XML Element."""
    if xml_str is None:
        return {}
    return {resource_key: DefusedET.fromstring(xml_str)}


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=[f.stem for f in VALID_FIXTURES],
)
def test_extraction(fixture_path: Path) -> None:
    """Parse XML data and verify extracted channels match expected."""
    data = _load_fixture(fixture_path)
    config = XMLSection.model_validate(data["_config"])
    resources = _build_resources(data["_xml"], data["_resource"])
    expected = data["_expected"]

    parser = XMLChannelParser(config)
    result = parser.parse(resources)

    assert result == expected
