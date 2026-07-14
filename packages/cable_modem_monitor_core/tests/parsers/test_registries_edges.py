"""Tests for parser registry edge cases.

Covers defensive type guards in channel and system info registry
wrappers, and model validators for JSON and transposed section
form exclusivity.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from solentlabs.cable_modem_monitor_core.models.parser_config.common import (
    TableSelector,
)
from solentlabs.cable_modem_monitor_core.models.parser_config.json_format import (
    JSONSection,
)
from solentlabs.cable_modem_monitor_core.models.parser_config.transposed import (
    HTMLTableTransposedSection,
)
from solentlabs.cable_modem_monitor_core.parsers.registries import (
    _parse_hnap_channels,
    _parse_hnap_sysinfo,
    _parse_html_fields_sysinfo,
    _parse_html_table_channels,
    _parse_js_json_channels,
    _parse_json_channels,
)

# ------------------------------------------------------------------
# Channel parser type guards — non-list returns empty list
# ------------------------------------------------------------------

# ┌───────────────────────────┬────────────────────────┐
# │ parser wrapper             │ expected on non-list   │
# ├───────────────────────────┼────────────────────────┤
# │ _parse_hnap_channels      │ []                     │
# │ _parse_json_channels      │ []                     │
# │ _parse_js_json_channels   │ []                     │
# └───────────────────────────┴────────────────────────┘


class TestChannelTypeGuards:
    """Defensive type guards return empty list for non-list parse results."""

    def test_hnap_non_list_returns_empty(self) -> None:
        """HNAP parser returning dict → empty list."""
        section = MagicMock()
        with patch("solentlabs.cable_modem_monitor_core.parsers.registries.HNAPParser") as mock_cls:
            mock_cls.return_value.parse.return_value = {"not": "a list"}
            result, _ = _parse_hnap_channels(section, {})
        assert result == []

    def test_json_non_list_returns_empty(self) -> None:
        """JSON parser returning None → empty list."""
        section = MagicMock()
        with patch("solentlabs.cable_modem_monitor_core.parsers.registries.JSONParser") as mock_cls:
            mock_cls.return_value.parse.return_value = None
            result, _ = _parse_json_channels(section, {})
        assert result == []

    def test_js_json_non_list_returns_empty(self) -> None:
        """JSJson parser returning string → empty list."""
        section = MagicMock()
        with patch("solentlabs.cable_modem_monitor_core.parsers.registries.JSJsonParser") as mock_cls:
            mock_cls.return_value.parse.return_value = "not a list"
            result, _ = _parse_js_json_channels(section, {})
        assert result == []

    def test_html_table_non_list_skipped(self) -> None:
        """HTMLTable parser returning None skips that table."""
        table_def = MagicMock()
        table_def.merge_by = None

        section = MagicMock()
        section.resource = "/data.htm"
        section.tables = [table_def]

        with patch("solentlabs.cable_modem_monitor_core.parsers.registries.HTMLTableParser") as mock_cls:
            mock_cls.return_value.parse.return_value = None
            result, _ = _parse_html_table_channels(section, {})
        assert result == []


# ------------------------------------------------------------------
# HTML table anchor counting — stub-page detection (UC-19a)
# ------------------------------------------------------------------

# ┌─────────────────────────────────┬──────────┬───────────┐
# │ scenario                        │ expected │ fulfilled │
# ├─────────────────────────────────┼──────────┼───────────┤
# │ resource missing from dict      │ 2        │ 0         │
# │ stub page (no tables in body)   │ 2        │ 0         │
# │ all tables present              │ 2        │ 2         │
# │ one of two tables present       │ 2        │ 1         │
# └─────────────────────────────────┴──────────┴───────────┘

_HTML_STUB = "<html><script>window.location.href='/login.asp'</script></html>"
_HTML_BOTH = (
    "<html><body>"
    '<table id="table1"><tr><td>1</td></tr></table>'
    '<table id="table2"><tr><td>1</td></tr></table>'
    "</body></html>"
)
_HTML_ONE = '<html><body><table id="table1"><tr><td>1</td></tr></table></body></html>'

# fmt: off
_HTML_TABLE_ANCHOR_CASES = [
    # (html,       expected, fulfilled, id)
    (None,         2,        0,         "resource-missing"),
    (_HTML_STUB,   2,        0,         "stub-page"),
    (_HTML_BOTH,   2,        2,         "all-tables"),
    (_HTML_ONE,    2,        1,         "one-of-two"),
]
# fmt: on


@pytest.mark.parametrize(
    "html,expected,fulfilled,_id",
    _HTML_TABLE_ANCHOR_CASES,
    ids=[c[3] for c in _HTML_TABLE_ANCHOR_CASES],
)
def test_html_table_anchor_counting(html: str | None, expected: int, fulfilled: int, _id: str) -> None:
    """HTML table anchor count reflects table presence, not just resource presence."""
    from bs4 import BeautifulSoup
    from solentlabs.cable_modem_monitor_core.models.parser_config.common import ColumnMapping
    from solentlabs.cable_modem_monitor_core.models.parser_config.table import HTMLTableSection, TableDefinition

    col = ColumnMapping(index=0, field="channel_number", type="integer")
    section = HTMLTableSection(
        format="table",
        resource="/data.htm",
        tables=[
            TableDefinition(selector=TableSelector(type="id", match="table1"), columns=[col]),
            TableDefinition(selector=TableSelector(type="id", match="table2"), columns=[col]),
        ],
    )
    resources = {} if html is None else {"/data.htm": BeautifulSoup(html, "html.parser")}
    _, count = _parse_html_table_channels(section, resources)
    assert count.expected == expected
    assert count.fulfilled == fulfilled


# ------------------------------------------------------------------
# System info type guards
# ------------------------------------------------------------------


class TestSysinfoTypeGuards:
    """Defensive type guards return empty dict for non-dict parse results."""

    def test_html_fields_non_dict_returns_empty(self) -> None:
        """HTMLFields parser returning list → empty dict."""
        source = MagicMock()
        with patch("solentlabs.cable_modem_monitor_core.parsers.registries.HTMLFieldsParser") as mock_cls:
            mock_cls.return_value.parse.return_value = ["not", "a", "dict"]
            result, _, _ = _parse_html_fields_sysinfo(source, {})
        assert result == {}

    def test_hnap_sysinfo_non_dict_returns_empty(self) -> None:
        """HNAPFields parser returning None → empty dict."""
        source = MagicMock()
        with patch("solentlabs.cable_modem_monitor_core.parsers.registries.HNAPFieldsParser") as mock_cls:
            mock_cls.return_value.parse.return_value = None
            result, _, _ = _parse_hnap_sysinfo(source, {})
        assert result == {}


# ------------------------------------------------------------------
# Model validators — JSON section form exclusivity
# ------------------------------------------------------------------

# ┌──────────────────────────────────┬────────────────────────────────┐
# │ scenario                         │ expected error                 │
# ├──────────────────────────────────┼────────────────────────────────┤
# │ both flat and multi-array        │ "use either flat form"         │
# │ neither flat nor multi-array     │ "must have either"             │
# │ flat with missing fields         │ "requires both"                │
# │ arrays + section channel_type    │ "must be set per array"        │
# │ arrays + section fixed_fields    │ "must be set per array"        │
# │ arrays + section filter          │ "must be set per array"        │
# └──────────────────────────────────┴────────────────────────────────┘
#
_FLAT_FIELD = {"field": "a", "key": "b", "type": "string"}
_MULTI_FIELD = {"field": "c", "key": "d", "type": "string"}

# fmt: off
JSON_VALIDATOR_CASES = [
    # (kwargs,                                                              error_match,     description)
    ({"format": "json", "resource": "/d", "array_path": "$.x",
      "fields": [_FLAT_FIELD], "arrays": [{"array_path": "$.y", "fields": [_MULTI_FIELD]}]},
     "use either flat form",  "both flat and multi-array"),
    ({"format": "json", "resource": "/d"},
     "must have either",      "neither flat nor multi-array"),
    ({"format": "json", "resource": "/d", "array_path": "$.x"},
     "requires both",         "flat missing fields"),
    ({"format": "json", "resource": "/d", "channel_type": {"fixed": "qam"},
      "arrays": [{"array_path": "$.y", "fields": [_MULTI_FIELD]}]},
     "must be set per array", "arrays with section-level channel_type"),
    ({"format": "json", "resource": "/d", "fixed_fields": {"lock_status": "locked"},
      "arrays": [{"array_path": "$.y", "fields": [_MULTI_FIELD]}]},
     "must be set per array", "arrays with section-level fixed_fields"),
    ({"format": "json", "resource": "/d", "filter": {"modulation": {"not": "QAM_NONE"}},
      "arrays": [{"array_path": "$.y", "fields": [_MULTI_FIELD]}]},
     "must be set per array", "arrays with section-level filter"),
]
# fmt: on


@pytest.mark.parametrize(
    "kwargs,error_match,desc",
    JSON_VALIDATOR_CASES,
    ids=[c[2] for c in JSON_VALIDATOR_CASES],
)
def test_json_section_form_exclusivity(kwargs: dict[str, Any], error_match: str, desc: str) -> None:
    """JSONSection validator rejects invalid form combinations."""
    with pytest.raises(ValidationError, match=error_match):
        JSONSection.model_validate(kwargs)


# ------------------------------------------------------------------
# Model validators — transposed section form exclusivity
# ------------------------------------------------------------------


def test_transposed_flat_missing_rows() -> None:
    """Transposed flat form with selector but no rows is rejected."""
    with pytest.raises(ValidationError, match="requires both"):
        HTMLTableTransposedSection(
            format="table_transposed",
            resource="/data.htm",
            selector=TableSelector.model_validate({"type": "nth", "match": 0}),
        )


# ------------------------------------------------------------------
# Additional channel/sysinfo type guards
# ------------------------------------------------------------------


class TestTransposedChannelSkipsNonList:
    """_parse_transposed_channels skips a table_def whose parse result isn't a list."""

    def test_non_list_table_continued_past(self) -> None:
        from solentlabs.cable_modem_monitor_core.parsers.registries import (
            _parse_transposed_channels,
        )

        # A single-table section: parser returns non-list → continue → primary_channels []
        section = MagicMock()
        section.resource = "/data.htm"
        # Simulate the "tables" list path the function's branch builds
        section.tables = []
        section.selector = MagicMock()
        section.rows = MagicMock()
        section.channel_type = "downstream"

        with patch("solentlabs.cable_modem_monitor_core.parsers.registries.HTMLTableTransposedParser") as mock_cls:
            mock_cls.return_value.parse.return_value = "not a list"
            result, _ = _parse_transposed_channels(section, {})

        assert result == []


class TestJsJsonChannelNumberAssignment:
    """_parse_js_json_channels auto-assigns channel_number when absent."""

    def test_channel_number_assigned_per_position(self) -> None:
        from solentlabs.cable_modem_monitor_core.parsers.registries import (
            _parse_js_json_channels,
        )

        section = MagicMock()
        with patch("solentlabs.cable_modem_monitor_core.parsers.registries.JSJsonParser") as mock_cls:
            mock_cls.return_value.parse.return_value = [
                {"channel_id": 10},
                {"channel_id": 11, "channel_number": 5},  # already mapped
                {"channel_id": 12},
            ]
            result, _ = _parse_js_json_channels(section, {})

        assert result[0]["channel_number"] == 1
        assert result[1]["channel_number"] == 5  # unchanged
        assert result[2]["channel_number"] == 3


class TestXmlChannelParser:
    """_parse_xml_channels: list path + non-list early-out."""

    def test_xml_non_list_returns_empty(self) -> None:
        from solentlabs.cable_modem_monitor_core.parsers.registries import (
            _parse_xml_channels,
        )

        section = MagicMock()
        with patch("solentlabs.cable_modem_monitor_core.parsers.registries.XMLChannelParser") as mock_cls:
            mock_cls.return_value.parse.return_value = None
            result, _ = _parse_xml_channels(section, {})
        assert result == []

    def test_xml_list_assigns_channel_numbers(self) -> None:
        from solentlabs.cable_modem_monitor_core.parsers.registries import (
            _parse_xml_channels,
        )

        section = MagicMock()
        with patch("solentlabs.cable_modem_monitor_core.parsers.registries.XMLChannelParser") as mock_cls:
            mock_cls.return_value.parse.return_value = [
                {"channel_id": 1},
                {"channel_id": 2, "channel_number": 99},  # preserved
            ]
            result, _ = _parse_xml_channels(section, {})

        assert result[0]["channel_number"] == 1
        assert result[1]["channel_number"] == 99


class TestSysinfoTypeGuardsExtra:
    """Type guards for js_vars and xml sysinfo wrappers."""

    def test_js_vars_non_dict_returns_empty(self) -> None:
        from solentlabs.cable_modem_monitor_core.parsers.registries import (
            _parse_js_vars_sysinfo,
        )

        source = MagicMock()
        with patch("solentlabs.cable_modem_monitor_core.parsers.registries.JSVarsParser") as mock_cls:
            mock_cls.return_value.parse.return_value = ["list, not dict"]
            result, _, _ = _parse_js_vars_sysinfo(source, {})
        assert result == {}

    def test_xml_sysinfo_non_dict_returns_empty(self) -> None:
        from solentlabs.cable_modem_monitor_core.parsers.registries import (
            _parse_xml_sysinfo,
        )

        source = MagicMock()
        with patch("solentlabs.cable_modem_monitor_core.parsers.registries.XMLSystemInfoParser") as mock_cls:
            mock_cls.return_value.parse.return_value = None
            result, _, _ = _parse_xml_sysinfo(source, {})
        assert result == {}
