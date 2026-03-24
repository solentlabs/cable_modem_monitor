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
            result = _parse_hnap_channels(section, {})
        assert result == []

    def test_json_non_list_returns_empty(self) -> None:
        """JSON parser returning None → empty list."""
        section = MagicMock()
        with patch("solentlabs.cable_modem_monitor_core.parsers.registries.JSONParser") as mock_cls:
            mock_cls.return_value.parse.return_value = None
            result = _parse_json_channels(section, {})
        assert result == []

    def test_js_json_non_list_returns_empty(self) -> None:
        """JSJson parser returning string → empty list."""
        section = MagicMock()
        with patch("solentlabs.cable_modem_monitor_core.parsers.registries.JSJsonParser") as mock_cls:
            mock_cls.return_value.parse.return_value = "not a list"
            result = _parse_js_json_channels(section, {})
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
            result = _parse_html_table_channels(section, {})
        assert result == []


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
            result = _parse_html_fields_sysinfo(source, {})
        assert result == {}

    def test_hnap_sysinfo_non_dict_returns_empty(self) -> None:
        """HNAPFields parser returning None → empty dict."""
        source = MagicMock()
        with patch("solentlabs.cable_modem_monitor_core.parsers.registries.HNAPFieldsParser") as mock_cls:
            mock_cls.return_value.parse.return_value = None
            result = _parse_hnap_sysinfo(source, {})
        assert result == {}


# ------------------------------------------------------------------
# Model validators — JSON section form exclusivity
# ------------------------------------------------------------------

# ┌──────────────────────────────┬────────────────────────────────┐
# │ scenario                     │ expected error                 │
# ├──────────────────────────────┼────────────────────────────────┤
# │ both flat and multi-array    │ "use either flat form"         │
# │ neither flat nor multi-array │ "must have either"             │
# │ flat with missing fields     │ "requires both"                │
# └──────────────────────────────┴────────────────────────────────┘
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
        JSONSection(**kwargs)


# ------------------------------------------------------------------
# Model validators — transposed section form exclusivity
# ------------------------------------------------------------------


def test_transposed_flat_missing_rows() -> None:
    """Transposed flat form with selector but no rows is rejected."""
    with pytest.raises(ValidationError, match="requires both"):
        HTMLTableTransposedSection(
            format="table_transposed",
            resource="/data.htm",
            selector={"type": "nth", "match": 0},
        )
