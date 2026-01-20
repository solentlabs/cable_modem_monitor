"""Tests for core/parser_utils.py."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from custom_components.cable_modem_monitor.core.base_parser import ParserStatus
from custom_components.cable_modem_monitor.core.parser_utils import (
    create_title,
    get_parser_display_name,
    select_parser_for_validation,
    sort_parsers_for_dropdown,
)

# =============================================================================
# PARSER DISPLAY NAME TEST CASES
# =============================================================================
# Tests get_parser_display_name() which adds status indicators to parser names.
# Non-verified parsers get " *" suffix to warn users in the dropdown.
#
# ┌───────────────┬───────────────────────┬───────────────┬─────────────────┐
# │ test_id       │ status                │ input_name    │ expected_output │
# ├───────────────┼───────────────────────┼───────────────┼─────────────────┤
# │ verified      │ VERIFIED              │ Arris SB8200  │ Arris SB8200    │
# │ awaiting      │ AWAITING_VERIFICATION │ New Parser    │ New Parser *    │
# │ in_progress   │ IN_PROGRESS           │ Dev Parser    │ Dev Parser *    │
# └───────────────┴───────────────────────┴───────────────┴─────────────────┘
#
# fmt: off
PARSER_DISPLAY_NAME_CASES: list[tuple[str, ParserStatus, str, str]] = [
    # (test_id,     status,                            name,           expected)
    ("verified",    ParserStatus.VERIFIED,             "Arris SB8200", "Arris SB8200"),
    ("awaiting",    ParserStatus.AWAITING_VERIFICATION,"New Parser",   "New Parser *"),
    ("in_progress", ParserStatus.IN_PROGRESS,          "Dev Parser",   "Dev Parser *"),
]
# fmt: on


# =============================================================================
# CREATE TITLE TEST CASES
# =============================================================================
# Tests create_title() which formats the config entry title from detection info.
# Handles manufacturer deduplication and missing fields gracefully.
#
# ┌─────────────────┬───────────────┬───────────────┬────────────────────────────┐
# │ test_id         │ modem_name    │ manufacturer  │ expected_title             │
# ├─────────────────┼───────────────┼───────────────┼────────────────────────────┤
# │ with_mfg        │ SB8200        │ Arris         │ Arris SB8200 (10.0.0.1)    │
# │ no_dup_mfg      │ Arris SB8200  │ Arris         │ Arris SB8200 (10.0.0.1)    │
# │ unknown_mfg     │ Generic Modem │ Unknown       │ Generic Modem (10.0.0.1)   │
# │ empty_mfg       │ Some Modem    │ (empty)       │ Some Modem (10.0.0.1)      │
# │ missing_modem   │ (missing)     │ Arris         │ Arris Cable Modem (10.0.0.1)│
# │ empty_info      │ (missing)     │ (missing)     │ Cable Modem (10.0.0.1)     │
# └─────────────────┴───────────────┴───────────────┴────────────────────────────┘
#
# fmt: off
_H = "10.0.0.1"  # Host IP for all test cases
CREATE_TITLE_CASES: list[tuple[str, dict, str, str]] = [
    # (test_id,       detection_info,                                             host, expected)
    ("with_mfg",      {"modem_name": "SB8200", "manufacturer": "Arris"},          _H,   f"Arris SB8200 ({_H})"),
    ("no_dup_mfg",    {"modem_name": "Arris SB8200", "manufacturer": "Arris"},    _H,   f"Arris SB8200 ({_H})"),
    ("unknown_mfg",   {"modem_name": "Generic Modem", "manufacturer": "Unknown"}, _H,   f"Generic Modem ({_H})"),
    ("empty_mfg",     {"modem_name": "Some Modem", "manufacturer": ""},           _H,   f"Some Modem ({_H})"),
    ("missing_modem", {"manufacturer": "Arris"},                                  _H,   f"Arris Cable Modem ({_H})"),
    ("empty_info",    {},                                                         _H,   f"Cable Modem ({_H})"),
]
# fmt: on


class TestSortParsersForDropdown:
    """Tests for sort_parsers_for_dropdown function."""

    def _make_parser(self, name: str, manufacturer: str) -> Mock:
        """Create a mock parser with name and manufacturer."""
        parser = Mock()
        parser.name = name
        parser.manufacturer = manufacturer
        return parser

    def test_sorts_alphabetically_by_manufacturer(self):
        """Test parsers are sorted by manufacturer first."""
        parsers = [
            self._make_parser("Model Z", "Zebra"),
            self._make_parser("Model A", "Apple"),
            self._make_parser("Model M", "Mango"),
        ]

        result = sort_parsers_for_dropdown(parsers)

        assert [p.manufacturer for p in result] == ["Apple", "Mango", "Zebra"]

    def test_sorts_by_name_within_manufacturer(self):
        """Test parsers are sorted by name within same manufacturer."""
        parsers = [
            self._make_parser("Model C", "Arris"),
            self._make_parser("Model A", "Arris"),
            self._make_parser("Model B", "Arris"),
        ]

        result = sort_parsers_for_dropdown(parsers)

        assert [p.name for p in result] == ["Model A", "Model B", "Model C"]

    def test_generic_parsers_sorted_last_within_manufacturer(self):
        """Test Generic parsers appear last within their manufacturer group."""
        parsers = [
            self._make_parser("Generic Model", "Arris"),
            self._make_parser("SB8200", "Arris"),
            self._make_parser("SB6190", "Arris"),
        ]

        result = sort_parsers_for_dropdown(parsers)

        assert result[-1].name == "Generic Model"
        assert [p.name for p in result] == ["SB6190", "SB8200", "Generic Model"]

    def test_unknown_manufacturer_sorted_last(self):
        """Test Unknown manufacturer appears at the very end."""
        parsers = [
            self._make_parser("Fallback", "Unknown"),
            self._make_parser("Model A", "Arris"),
            self._make_parser("Model B", "Netgear"),
        ]

        result = sort_parsers_for_dropdown(parsers)

        assert result[-1].manufacturer == "Unknown"
        assert [p.manufacturer for p in result] == ["Arris", "Netgear", "Unknown"]

    def test_empty_list(self):
        """Test empty list returns empty list."""
        result = sort_parsers_for_dropdown([])
        assert result == []


class TestGetParserDisplayName:
    """Tests for get_parser_display_name function."""

    @pytest.mark.parametrize(
        "test_id,status,name,expected",
        PARSER_DISPLAY_NAME_CASES,
        ids=[c[0] for c in PARSER_DISPLAY_NAME_CASES],
    )
    def test_display_name_suffix(self, test_id: str, status: ParserStatus, name: str, expected: str):
        """Test parser display name includes correct suffix based on status."""
        parser = Mock()
        parser.name = name
        parser.status = status

        result = get_parser_display_name(parser)

        assert result == expected, f"{test_id}: expected '{expected}', got '{result}'"


class TestSelectParserForValidation:
    """Tests for select_parser_for_validation function."""

    def _make_parser(self, name: str) -> Mock:
        """Create a mock parser with name."""
        parser = Mock()
        parser.name = name
        return parser

    def test_auto_mode_returns_none_parser(self):
        """Test auto mode returns None for parser class."""
        parsers = [self._make_parser("Parser A")]

        result, hint = select_parser_for_validation(parsers, "auto", None)

        assert result is None
        assert hint is None

    def test_auto_mode_with_cached_parser(self):
        """Test auto mode returns cached parser name as hint."""
        parsers = [self._make_parser("Parser A")]

        result, hint = select_parser_for_validation(parsers, "auto", "Cached Parser")

        assert result is None
        assert hint == "Cached Parser"

    def test_none_modem_choice_uses_auto(self):
        """Test None modem_choice treated as auto."""
        parsers = [self._make_parser("Parser A")]

        result, hint = select_parser_for_validation(parsers, None, "Cached")

        assert result is None
        assert hint == "Cached"

    def test_explicit_selection_returns_parser_class(self):
        """Test explicit parser selection returns the parser class."""
        parser_a = self._make_parser("Parser A")
        parser_b = self._make_parser("Parser B")
        parsers = [parser_a, parser_b]

        result, hint = select_parser_for_validation(parsers, "Parser B", None)

        assert result is parser_b
        assert hint is None

    def test_explicit_selection_strips_asterisk_suffix(self):
        """Test explicit selection strips ' *' suffix from choice."""
        parser = self._make_parser("Unverified Parser")
        parsers = [parser]

        result, hint = select_parser_for_validation(parsers, "Unverified Parser *", None)

        assert result is parser

    def test_unknown_parser_returns_none(self):
        """Test unknown parser name returns None."""
        parsers = [self._make_parser("Known Parser")]

        result, hint = select_parser_for_validation(parsers, "Unknown Parser", None)

        assert result is None
        assert hint is None


class TestCreateTitle:
    """Tests for create_title function."""

    @pytest.mark.parametrize(
        "test_id,detection_info,host,expected",
        CREATE_TITLE_CASES,
        ids=[c[0] for c in CREATE_TITLE_CASES],
    )
    def test_create_title(self, test_id: str, detection_info: dict, host: str, expected: str):
        """Test create_title formats title correctly based on detection info."""
        result = create_title(detection_info, host)

        assert result == expected, f"{test_id}: expected '{expected}', got '{result}'"
