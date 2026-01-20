"""Tests for parser loading optimizations.

These tests validate the parser loading infrastructure works correctly.
They use whatever parsers are available - no hardcoded modem references.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.core.parser_discovery import (
    _find_parser_in_module,
    _sort_parsers,
    clear_parser_caches,
)
from custom_components.cable_modem_monitor.parsers import (
    get_parser_by_name,
    get_parser_dropdown_from_index,
    get_parsers,
)

# ============================================================================
# Test Data Tables
# ============================================================================

# Sort order test cases
# ┌─────────────────┬──────────────────┬──────────────┬─────────────────────────┐
# │ manufacturer    │ name             │ expected_pos │ description             │
# ├─────────────────┼──────────────────┼──────────────┼─────────────────────────┤
# │ "ARRIS"         │ "ARRIS SB8200"   │ 0            │ normal parser (first)   │
# │ "ARRIS"         │ "ARRIS Generic"  │ 1            │ generic goes after      │
# │ "Motorola"      │ "Motorola MB"    │ 2            │ next manufacturer       │
# │ "Unknown"       │ "Unknown Parser" │ 3            │ unknown goes last       │
# └─────────────────┴──────────────────┴──────────────┴─────────────────────────┘
#
# fmt: off
SORT_ORDER_CASES: list[tuple[str, str, int, str]] = [
    # (manufacturer,  name,              expected_pos, description)
    ("ARRIS",         "ARRIS SB8200",    0,            "normal parser first"),
    ("ARRIS",         "ARRIS Generic",   1,            "generic after normal"),
    ("Motorola",      "Motorola MB",     2,            "next manufacturer"),
    ("Unknown",       "Unknown Parser",  3,            "unknown goes last"),
]
# fmt: on

# Invalid parser name test cases
# ┌───────────────────────────┬─────────────────────────────────┐
# │ invalid_name              │ description                     │
# ├───────────────────────────┼─────────────────────────────────┤
# │ "NonExistent Parser"      │ completely made up name         │
# │ ""                        │ empty string                    │
# │ "   "                     │ whitespace only                 │
# │ "ARRIS"                   │ manufacturer only, not model    │
# └───────────────────────────┴─────────────────────────────────┘
#
# fmt: off
INVALID_PARSER_NAMES: list[tuple[str, str]] = [
    # (invalid_name,            description)
    ("NonExistent Parser XYZ",  "completely made up name"),
    ("",                        "empty string"),
    ("   ",                     "whitespace only"),
    ("ARRIS",                   "manufacturer only"),
]
# fmt: on


class TestParserCaching:
    """Test parser caching functionality."""

    def test_get_parsers_caches_results(self):
        """Test that get_parsers caches results on first call."""
        # Clear cache - cache is now in core.parser_discovery
        import custom_components.cable_modem_monitor.core.parser_discovery as discovery_module

        discovery_module._PARSER_CACHE = None

        # First call should populate cache
        parsers1 = get_parsers(use_cache=True)
        assert discovery_module._PARSER_CACHE is not None
        assert len(parsers1) > 0  # type: ignore[unreachable]

        # Second call should return cached results
        parsers2 = get_parsers(use_cache=True)
        assert parsers2 is parsers1  # Same object reference

    def test_get_parsers_bypass_cache(self):
        """Test that get_parsers can bypass cache when requested."""
        # First call with cache
        parsers1 = get_parsers(use_cache=True)

        # Second call bypassing cache should re-discover
        parsers2 = get_parsers(use_cache=False)
        assert len(parsers2) == len(parsers1)
        # Should be different objects (re-discovered)
        assert parsers2 is not parsers1

    def test_get_parsers_discovers_parsers(self):
        """Test that get_parsers discovers available parsers."""
        parsers = get_parsers()

        # Should find multiple parsers
        assert len(parsers) >= 5, "Expected at least 5 parsers to be discovered"

        # All parsers should have required attributes
        for parser in parsers:
            assert hasattr(parser, "name")
            assert hasattr(parser, "manufacturer")
            assert parser.name, f"Parser {parser} has empty name"
            assert parser.manufacturer, f"Parser {parser} has empty manufacturer"

    def test_get_parsers_sorts_alphabetically(self):
        """Test that parsers are sorted alphabetically by manufacturer then name."""
        parsers = get_parsers()

        # Check that manufacturers are in alphabetical order (excluding Unknown which goes last)
        manufacturers = [p.manufacturer for p in parsers]
        non_unknown_manufacturers = [m for m in manufacturers if m != "Unknown"]
        assert non_unknown_manufacturers == sorted(non_unknown_manufacturers)

        # Within each manufacturer, parsers should be sorted by name
        seen_manufacturers = set()
        for parser in parsers:
            if parser.manufacturer not in seen_manufacturers:
                # Get all parsers for this manufacturer
                mfr_parsers = [p for p in parsers if p.manufacturer == parser.manufacturer]
                mfr_names = [p.name for p in mfr_parsers]
                assert mfr_names == sorted(mfr_names), f"Parsers for {parser.manufacturer} not sorted: {mfr_names}"
                seen_manufacturers.add(parser.manufacturer)


def _get_any_parser_name() -> str:
    """Helper to get the name of any available parser for testing."""
    parsers = get_parsers()
    assert len(parsers) > 0, "No parsers available"
    return parsers[0].name


class TestGetParserByName:
    """Test get_parser_by_name functionality."""

    def test_load_parser_by_name(self):
        """Test loading a parser by its name."""
        parser_name = _get_any_parser_name()
        parser_class = get_parser_by_name(parser_name)

        assert parser_class is not None
        assert issubclass(parser_class, ModemParser)
        assert parser_class.name == parser_name

    def test_parser_has_manufacturer(self):
        """Test that loaded parser has manufacturer attribute."""
        parser_name = _get_any_parser_name()
        parser_class = get_parser_by_name(parser_name)

        assert parser_class is not None
        assert parser_class.manufacturer is not None
        assert len(parser_class.manufacturer) > 0

    def test_invalid_name_returns_none(self):
        """Test that invalid parser name returns None."""
        parser_class = get_parser_by_name("[MFG] [Model] Invalid")
        assert parser_class is None

    def test_parser_is_instantiable(self):
        """Test that returned parser class can be instantiated."""
        parser_name = _get_any_parser_name()
        parser_class = get_parser_by_name(parser_name)
        assert parser_class is not None

        # Should be able to create an instance
        parser_instance = parser_class()
        assert isinstance(parser_instance, ModemParser)

    def test_all_discovered_parsers_loadable_by_name(self):
        """Test that every discovered parser can be loaded by name."""
        parsers = get_parsers()

        for parser in parsers:
            loaded = get_parser_by_name(parser.name)
            assert loaded is not None, f"Failed to load parser: {parser.name}"
            assert loaded.name == parser.name


class TestUnverifiedParserSuffix:
    """Test that unverified parser suffix ' *' is handled correctly.

    Unverified parsers are shown with ' *' suffix in the UI, but this suffix
    must be stripped during lookup. See Issue #40.
    """

    def test_get_parser_by_name_strips_asterisk_suffix(self):
        """Test that get_parser_by_name strips ' *' suffix."""
        parser_name = _get_any_parser_name()

        # Add suffix like UI does for unverified parsers
        parser_class = get_parser_by_name(f"{parser_name} *")
        assert parser_class is not None
        assert parser_class.name == parser_name

    def test_get_parser_by_name_works_without_suffix(self):
        """Test that get_parser_by_name works with clean name."""
        parser_name = _get_any_parser_name()

        parser_class = get_parser_by_name(parser_name)
        assert parser_class is not None
        assert parser_class.name == parser_name

    def test_get_parser_by_name_strips_multiple_asterisks(self):
        """Test edge case: multiple asterisks/spaces are stripped."""
        parser_name = _get_any_parser_name()

        parser_class = get_parser_by_name(f"{parser_name}  **")
        assert parser_class is not None
        assert parser_class.name == parser_name

    def test_suffix_stripping_works_for_all_parsers(self):
        """Test that suffix stripping works for every parser."""
        for parser in get_parsers():
            # Try loading with suffix
            loaded = get_parser_by_name(f"{parser.name} *")
            assert loaded is not None, f"Failed to load {parser.name} with suffix"
            assert loaded.name == parser.name


class TestParserLoadingPerformance:
    """Test performance characteristics of parser loading."""

    def test_direct_load_faster_than_discovery(self):
        """Test that direct loading is faster than full discovery."""
        import time

        import custom_components.cable_modem_monitor.core.parser_discovery as discovery_module

        parser_name = _get_any_parser_name()

        # Clear cache to ensure fair comparison
        discovery_module._PARSER_CACHE = None

        # Time full discovery
        start = time.perf_counter()
        get_parsers(use_cache=False)
        discovery_time = time.perf_counter() - start

        # Time direct load
        start = time.perf_counter()
        get_parser_by_name(parser_name)
        direct_time = time.perf_counter() - start

        # Direct load should be significantly faster (at least 2x)
        # In practice, it's often 8x+ faster
        assert direct_time < discovery_time / 2

    def test_cached_load_is_instant(self):
        """Test that cached parser loading is very fast."""
        import time

        # Prime the cache
        get_parsers(use_cache=True)

        # Time cached load
        start = time.perf_counter()
        get_parsers(use_cache=True)
        cached_time = time.perf_counter() - start

        # Cached load should be extremely fast (< 10ms)
        # Note: 1ms was too aggressive and caused flaky tests
        assert cached_time < 0.01


# ============================================================================
# Edge Case Tests (Table-Driven)
# ============================================================================


class TestClearParserCaches:
    """Test cache clearing functionality."""

    def test_clear_parser_caches_clears_all(self):
        """Test that clear_parser_caches clears all cache variables."""
        import custom_components.cable_modem_monitor.core.parser_discovery as discovery

        # Prime all caches
        get_parsers(use_cache=True)
        get_parser_by_name(_get_any_parser_name())

        # Verify caches are populated
        assert discovery._PARSER_CACHE is not None
        assert discovery._MODEM_INDEX is not None

        # Clear caches
        clear_parser_caches()

        # Verify all caches are cleared
        assert discovery._PARSER_CACHE is None
        assert discovery._PARSER_NAME_CACHE is None
        assert discovery._MODEM_INDEX is None
        assert discovery._NAME_TO_PATH is None


class TestSortParsers:
    """Test parser sorting with table-driven cases."""

    @pytest.mark.parametrize(
        "manufacturer,name,expected_pos,desc",
        SORT_ORDER_CASES,
        ids=[c[3] for c in SORT_ORDER_CASES],
    )
    def test_sort_order(self, manufacturer: str, name: str, expected_pos: int, desc: str):
        """Test that parsers are sorted correctly by manufacturer and name."""

        # Create mock parser classes with the test attributes
        def make_mock_parser(mfr: str, parser_name: str) -> type[ModemParser]:
            """Create a mock parser class."""
            mock = MagicMock(spec=type)
            mock.manufacturer = mfr
            mock.name = parser_name
            return mock  # type: ignore[return-value]

        # Build list of all test parsers (unsorted)
        parsers: list[Any] = [make_mock_parser(m, n) for m, n, _, _ in SORT_ORDER_CASES]
        # Shuffle to ensure sort actually works
        import random

        random.shuffle(parsers)

        # Sort
        _sort_parsers(parsers)

        # Find position of parser with this name
        names = [p.name for p in parsers]
        actual_pos = names.index(name)
        assert actual_pos == expected_pos, f"{desc}: expected pos {expected_pos}, got {actual_pos}"


class TestFindParserInModule:
    """Test _find_parser_in_module with real modules."""

    def test_find_parser_in_real_module(self):
        """Test finding a parser in a real parser module."""
        import custom_components.cable_modem_monitor.modems.arris.sb8200.parser as sb8200_module

        result = _find_parser_in_module(sb8200_module)
        assert result is not None
        assert result.name == "ARRIS SB8200"

    def test_find_parser_by_exact_name(self):
        """Test finding a parser by exact name match."""
        import custom_components.cable_modem_monitor.modems.arris.sb8200.parser as sb8200_module

        result = _find_parser_in_module(sb8200_module, expected_name="ARRIS SB8200")
        assert result is not None
        assert result.name == "ARRIS SB8200"

    def test_find_parser_wrong_name_returns_none(self):
        """Test that wrong name returns None."""
        import custom_components.cable_modem_monitor.modems.arris.sb8200.parser as sb8200_module

        result = _find_parser_in_module(sb8200_module, expected_name="WrongName")
        assert result is None

    def test_find_parser_empty_module_returns_none(self):
        """Test that module without parser returns None."""
        import custom_components.cable_modem_monitor.core.parser_discovery as discovery_module

        # parser_discovery itself has no ModemParser subclasses
        result = _find_parser_in_module(discovery_module)
        assert result is None


class TestInvalidParserNames:
    """Test get_parser_by_name with invalid inputs."""

    @pytest.mark.parametrize(
        "invalid_name,desc",
        INVALID_PARSER_NAMES,
        ids=[c[1] for c in INVALID_PARSER_NAMES],
    )
    def test_invalid_names_return_none(self, invalid_name: str, desc: str):
        """Test that invalid parser names return None."""
        result = get_parser_by_name(invalid_name)
        assert result is None, f"{desc}: expected None for '{invalid_name}'"


class TestIndexLoadingErrors:
    """Test error handling when loading modem index."""

    def test_missing_index_file(self):
        """Test handling of missing index.yaml file."""
        import custom_components.cable_modem_monitor.core.parser_discovery as discovery

        clear_parser_caches()

        with patch("builtins.open", side_effect=FileNotFoundError("not found")):
            index = discovery._load_modem_index()

        # Should return empty structure, not raise
        assert index == {"modems": {}}
        assert discovery._NAME_TO_PATH == {}

    def test_corrupted_index_file(self):
        """Test handling of corrupted/invalid YAML in index."""
        import custom_components.cable_modem_monitor.core.parser_discovery as discovery

        clear_parser_caches()

        # Simulate YAML parse error
        with (
            patch("builtins.open"),
            patch("yaml.safe_load", side_effect=Exception("YAML parse error")),
        ):
            index = discovery._load_modem_index()

        # Should return empty structure, not raise
        assert index == {"modems": {}}
        assert discovery._NAME_TO_PATH == {}


class TestDirectLoadErrors:
    """Test error handling in direct parser loading."""

    def test_direct_load_import_error(self):
        """Test handling of import errors during direct load."""
        import custom_components.cable_modem_monitor.core.parser_discovery as discovery

        clear_parser_caches()

        # Set up name lookup to find a path
        discovery._NAME_TO_PATH = {"Test Parser": "test/parser"}
        discovery._MODEM_INDEX = {"modems": {}}

        with patch("importlib.import_module", side_effect=ImportError("no module")):
            result = discovery._load_parser_direct("Test Parser")

        assert result is None

    def test_direct_load_parser_not_in_module(self):
        """Test when module exists but parser class not found."""
        import custom_components.cable_modem_monitor.core.parser_discovery as discovery

        clear_parser_caches()

        # Set up name lookup
        discovery._NAME_TO_PATH = {"Test Parser": "test/parser"}
        discovery._MODEM_INDEX = {"modems": {}}

        # Mock module with no parser classes
        mock_module = MagicMock()
        mock_module.__name__ = "test_module"

        with (
            patch("importlib.import_module", return_value=mock_module),
            patch("builtins.dir", return_value=["SomeOtherClass"]),
        ):
            result = discovery._load_parser_direct("Test Parser")

        assert result is None


class TestFallbackParser:
    """Test fallback parser availability in dropdown and loading."""

    def test_fallback_in_dropdown(self):
        """Test that fallback parser appears in dropdown list."""
        dropdown = get_parser_dropdown_from_index()

        assert "Unknown Modem (Fallback Mode)" in dropdown

    def test_fallback_at_end_of_dropdown(self):
        """Test that fallback parser is at the end of dropdown list."""
        dropdown = get_parser_dropdown_from_index()

        assert dropdown[-1] == "Unknown Modem (Fallback Mode)"

    def test_fallback_loadable_by_name(self):
        """Test that fallback parser can be loaded by name."""
        parser_class = get_parser_by_name("Unknown Modem (Fallback Mode)")

        assert parser_class is not None
        assert parser_class.name == "Unknown Modem (Fallback Mode)"
        assert parser_class.manufacturer == "Unknown"

    def test_fallback_is_instantiable(self):
        """Test that fallback parser class can be instantiated."""
        parser_class = get_parser_by_name("Unknown Modem (Fallback Mode)")
        assert parser_class is not None

        parser_instance = parser_class()
        assert parser_instance is not None
        assert parser_instance.name == "Unknown Modem (Fallback Mode)"
