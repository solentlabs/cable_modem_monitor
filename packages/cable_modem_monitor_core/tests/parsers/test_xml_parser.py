"""Tests for XMLChannelParser.

Fixture-driven tests with synthesized XML data. Each fixture contains
an XML string, an XMLSection config, and expected channel output.

Adding a test case = drop a JSON file in fixtures/xml_parser/valid/.
"""

from __future__ import annotations

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

from tests._helpers import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "xml_parser"
VALID_FIXTURES = collect_fixtures(FIXTURES_DIR / "valid")


def _build_resources(data: dict[str, Any]) -> dict[str, Any]:
    """Build a resource dict with parsed XML Elements.

    Supports two fixture formats:
    - ``_resources``: dict of resource_key -> XML string (multi-table)
    - ``_xml`` + ``_resource``: single XML string with key (single-table)
    """
    if "_resources" in data:
        return {
            key: DefusedET.fromstring(xml_str) for key, xml_str in data["_resources"].items() if xml_str is not None
        }
    xml_str = data.get("_xml")
    if xml_str is None:
        return {}
    return {data["_resource"]: DefusedET.fromstring(xml_str)}


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=[f.stem for f in VALID_FIXTURES],
)
def test_extraction(fixture_path: Path) -> None:
    """Parse XML data and verify extracted channels match expected."""
    data = load_fixture(fixture_path)
    config = XMLSection.model_validate(data["_config"])
    resources = _build_resources(data)
    expected = data["_expected"]

    parser = XMLChannelParser(config)
    result = parser.parse(resources)

    assert result == expected


# -----------------------------------------------------------------------
# Defensive edge cases — inline behavioral tests
# -----------------------------------------------------------------------

_CONFIG_BASIC: dict[str, Any] = {
    "format": "xml",
    "tables": [
        {
            "resource": "10",
            "root_element": "downstream_table",
            "child_element": "downstream",
            "columns": [
                {"source": "chid", "field": "channel_id", "type": "integer"},
            ],
        }
    ],
}


def test_resource_not_an_element_returns_empty() -> None:
    """Resource that's not an XML Element (e.g., dict) yields no channels."""
    config = XMLSection.model_validate(_CONFIG_BASIC)
    parser = XMLChannelParser(config)
    # Pass a dict where an Element is expected.
    result = parser.parse({"10": {"not": "an element"}})
    assert result == []


def test_root_element_matches_document_root() -> None:
    """When the document root tag IS the table.root_element, parse continues."""
    # Document root is "downstream_table" itself (no wrapper)
    xml_str = (
        "<downstream_table>"
        "<downstream><chid>7</chid></downstream>"
        "<downstream><chid>8</chid></downstream>"
        "</downstream_table>"
    )
    config = XMLSection.model_validate(_CONFIG_BASIC)
    parser = XMLChannelParser(config)
    result = parser.parse({"10": DefusedET.fromstring(xml_str)})

    assert result == [{"channel_id": 7}, {"channel_id": 8}]


def test_root_element_not_found_anywhere_returns_empty() -> None:
    """Document root differs AND find() returns None → empty list."""
    # Root tag is "wrong" and there's no nested "downstream_table"
    xml_str = "<wrong><downstream><chid>1</chid></downstream></wrong>"
    config = XMLSection.model_validate(_CONFIG_BASIC)
    parser = XMLChannelParser(config)
    result = parser.parse({"10": DefusedET.fromstring(xml_str)})

    assert result == []


def test_extract_column_handles_missing_subelement() -> None:
    """Column whose source sub-element is missing yields None (channel dropped)."""
    # Two channels: one complete, one missing chid → produces empty dict, filtered.
    xml_str = (
        "<root><downstream_table>"
        "<downstream><chid>5</chid></downstream>"
        "<downstream><other>x</other></downstream>"
        "</downstream_table></root>"
    )
    config = XMLSection.model_validate(_CONFIG_BASIC)
    parser = XMLChannelParser(config)
    result = parser.parse({"10": DefusedET.fromstring(xml_str)})

    # Empty channel dict (no fields extracted) is falsy and dropped by the
    # `if channel and passes_filter(...)` guard in _parse_table.
    assert result == [{"channel_id": 5}]


def test_apply_channel_type_map_assigns_mapped_value() -> None:
    """ChannelTypeMap maps a source field's value into channel_type."""
    config_dict: dict[str, Any] = {
        "format": "xml",
        "tables": [
            {
                "resource": "10",
                "root_element": "downstream_table",
                "child_element": "downstream",
                "columns": [
                    {"source": "kind", "field": "raw_kind", "type": "string"},
                ],
                "channel_type": {
                    "field": "raw_kind",
                    "map": {"O": "ofdm", "S": "sc-qam"},
                },
            }
        ],
    }
    xml_str = (
        "<root><downstream_table>"
        "<downstream><kind>O</kind></downstream>"
        "<downstream><kind>S</kind></downstream>"
        "<downstream><kind>UNKNOWN</kind></downstream>"
        "</downstream_table></root>"
    )
    config = XMLSection.model_validate(config_dict)
    parser = XMLChannelParser(config)
    result = parser.parse({"10": DefusedET.fromstring(xml_str)})

    assert result[0]["channel_type"] == "ofdm"
    assert result[1]["channel_type"] == "sc-qam"
    # Unknown source value: no mapping, channel_type left unset
    assert "channel_type" not in result[2]


# -----------------------------------------------------------------------
# Companion tables (merge_by): FORMAT_XML_SPEC.md § Table-Level Properties
# -----------------------------------------------------------------------

# A firmware that serves codeword counters from a separate call keyed by
# the channel id (CBN fun=19 signal_table, keyed by dsid = fun=10 chid).
_PRIMARY_TABLE: dict[str, Any] = {
    "resource": "10",
    "root_element": "downstream_table",
    "child_element": "downstream",
    "columns": [
        {"source": "chid", "field": "channel_id", "type": "integer"},
        {"source": "pow", "field": "power", "type": "float"},
    ],
}
_COMPANION_TABLE: dict[str, Any] = {
    "resource": "19",
    "root_element": "signal_table",
    "child_element": "signal",
    "merge_by": ["channel_id"],
    "columns": [
        {"source": "dsid", "field": "channel_id", "type": "integer"},
        {"source": "pow", "field": "power", "type": "float"},
        {"source": "correctable", "field": "corrected", "type": "integer"},
        {"source": "uncorrectable", "field": "uncorrected", "type": "integer"},
    ],
}
_PRIMARY_XML = (
    "<downstream_table>"
    "<downstream><chid>2</chid><pow>8.1</pow></downstream>"
    "<downstream><chid>1</chid><pow>8.3</pow></downstream>"
    "<downstream><chid>3</chid><pow>8.5</pow></downstream>"
    "</downstream_table>"
)
_COMPANION_XML = (
    "<signal_table>"
    "<signal><dsid>1</dsid><pow>0</pow><correctable>11</correctable><uncorrectable>1</uncorrectable></signal>"
    "<signal><dsid>2</dsid><pow>0</pow><correctable>22</correctable><uncorrectable>2</uncorrectable></signal>"
    "<signal><dsid>99</dsid><correctable>9</correctable><uncorrectable>9</uncorrectable></signal>"
    "</signal_table>"
)


def test_companion_table_merges_into_primaries() -> None:
    """Companion rows join primaries by key; primary wins; unmatched rows add no channel."""
    from solentlabs.cable_modem_monitor_core.parsers.registries import _parse_xml_channels

    section = XMLSection.model_validate({"format": "xml", "tables": [_COMPANION_TABLE, _PRIMARY_TABLE]})
    resources = {"10": DefusedET.fromstring(_PRIMARY_XML), "19": DefusedET.fromstring(_COMPANION_XML)}

    channels, _ = _parse_xml_channels(section, resources)

    assert channels == [
        {"channel_id": 2, "power": 8.1, "corrected": 22, "uncorrected": 2, "channel_number": 1},
        {"channel_id": 1, "power": 8.3, "corrected": 11, "uncorrected": 1, "channel_number": 2},
        {"channel_id": 3, "power": 8.5, "channel_number": 3},
    ]


def test_all_companion_section_is_rejected() -> None:
    """A section needs a primary table for companions to join."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="at least one primary table"):
        XMLSection.model_validate({"format": "xml", "tables": [_COMPANION_TABLE]})
