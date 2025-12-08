"""Tests for parser loading optimizations."""

from __future__ import annotations

from custom_components.cable_modem_monitor.parsers import (
    get_parser_by_name,
    get_parsers,
)
from custom_components.cable_modem_monitor.parsers.base_parser import ModemParser


class TestParserCaching:
    """Test parser caching functionality."""

    def test_get_parsers_caches_results(self):
        """Test that get_parsers caches results on first call."""
        ***REMOVED*** Clear cache
        import custom_components.cable_modem_monitor.parsers as parser_module

        parser_module._PARSER_CACHE = None

        ***REMOVED*** First call should populate cache
        parsers1 = get_parsers(use_cache=True)
        assert parser_module._PARSER_CACHE is not None
        assert len(parsers1) > 0  ***REMOVED*** type: ignore[unreachable]

        ***REMOVED*** Second call should return cached results
        parsers2 = get_parsers(use_cache=True)
        assert parsers2 is parsers1  ***REMOVED*** Same object reference

    def test_get_parsers_bypass_cache(self):
        """Test that get_parsers can bypass cache when requested."""
        ***REMOVED*** First call with cache
        parsers1 = get_parsers(use_cache=True)

        ***REMOVED*** Second call bypassing cache should re-discover
        parsers2 = get_parsers(use_cache=False)
        assert len(parsers2) == len(parsers1)
        ***REMOVED*** Should be different objects (re-discovered)
        assert parsers2 is not parsers1

    def test_get_parsers_returns_all_known_parsers(self):
        """Test that get_parsers finds all expected parsers."""
        parsers = get_parsers()
        parser_names = [p.name for p in parsers]

        ***REMOVED*** Check for known parsers
        assert "ARRIS SB6141" in parser_names
        assert "ARRIS SB6190" in parser_names
        assert "ARRIS SB8200" in parser_names
        assert "Motorola MB7621" in parser_names
        assert "Motorola MB8611" in parser_names
        assert "Technicolor TC4400" in parser_names
        assert "Technicolor XB7" in parser_names

    def test_get_parsers_sorts_alphabetically(self):
        """Test that parsers are sorted alphabetically by manufacturer then name."""
        parsers = get_parsers()

        ***REMOVED*** Check that parsers are grouped by manufacturer
        manufacturers = [p.manufacturer for p in parsers]
        ***REMOVED*** Should have ARRIS, Motorola, Technicolor groups
        assert "ARRIS" in manufacturers
        assert "Motorola" in manufacturers
        assert "Technicolor" in manufacturers

        ***REMOVED*** Check that manufacturers are in alphabetical order (excluding Unknown which goes last)
        non_unknown_manufacturers = [m for m in manufacturers if m != "Unknown"]
        assert non_unknown_manufacturers == sorted(non_unknown_manufacturers)

        ***REMOVED*** Within Motorola, check alphabetical ordering
        motorola_parsers = [p for p in parsers if p.manufacturer == "Motorola"]
        motorola_names = [p.name for p in motorola_parsers]
        ***REMOVED*** Motorola parsers should be in alphabetical order
        assert motorola_names == sorted(motorola_names)


class TestGetParserByName:
    """Test get_parser_by_name functionality."""

    def test_motorola_mb7621(self):
        """Test loading Motorola MB7621 parser by name."""
        parser_class = get_parser_by_name("Motorola MB7621")
        assert parser_class is not None
        assert issubclass(parser_class, ModemParser)
        assert parser_class.name == "Motorola MB7621"
        assert parser_class.manufacturer == "Motorola"

    def test_mb8611(self):
        """Test loading MB8611 parser by name."""
        parser_class = get_parser_by_name("Motorola MB8611")
        assert parser_class is not None
        assert issubclass(parser_class, ModemParser)
        assert parser_class.name == "Motorola MB8611"

    def test_arris_sb6190(self):
        """Test loading ARRIS SB6190 parser by name."""
        parser_class = get_parser_by_name("ARRIS SB6190")
        assert parser_class is not None
        assert issubclass(parser_class, ModemParser)
        assert parser_class.name == "ARRIS SB6190"
        assert parser_class.manufacturer == "ARRIS"

    def test_arris_sb8200(self):
        """Test loading ARRIS SB8200 parser by name."""
        from custom_components.cable_modem_monitor.parsers.base_parser import ParserStatus

        parser_class = get_parser_by_name("ARRIS SB8200")
        assert parser_class is not None
        assert issubclass(parser_class, ModemParser)
        assert parser_class.name == "ARRIS SB8200"
        assert parser_class.manufacturer == "ARRIS"
        ***REMOVED*** SB8200 is verified (Issue ***REMOVED***42)
        assert parser_class.status == ParserStatus.VERIFIED
        ***REMOVED*** Also test the verified property via an instance
        parser = parser_class()
        assert parser.verified is True

    def test_invalid(self):
        """Test that invalid parser name returns None."""
        parser_class = get_parser_by_name("Invalid Parser Name")
        assert parser_class is None

    def test_instantiable(self):
        """Test that returned parser class can be instantiated."""
        parser_class = get_parser_by_name("Motorola MB7621")
        assert parser_class is not None

        ***REMOVED*** Should be able to create an instance
        parser_instance = parser_class()
        assert isinstance(parser_instance, ModemParser)


class TestUnverifiedParserSuffix:
    """Test that unverified parser suffix ' *' is handled correctly.

    Unverified parsers are shown with ' *' suffix in the UI, but this suffix
    must be stripped during lookup. See Issue ***REMOVED***40.
    """

    def test_get_parser_by_name_strips_asterisk_suffix(self):
        """Test that get_parser_by_name strips ' *' suffix from unverified parsers."""
        ***REMOVED*** MB8611 is unverified, so UI shows "Motorola MB8611 *"
        ***REMOVED*** But lookup should still work
        parser_class = get_parser_by_name("Motorola MB8611 *")
        assert parser_class is not None
        assert parser_class.name == "Motorola MB8611"

    def test_get_parser_by_name_works_without_suffix(self):
        """Test that get_parser_by_name works with clean name too."""
        parser_class = get_parser_by_name("Motorola MB8611")
        assert parser_class is not None
        assert parser_class.name == "Motorola MB8611"

    def test_get_parser_by_name_strips_multiple_asterisks(self):
        """Test edge case: multiple asterisks/spaces are stripped."""
        parser_class = get_parser_by_name("Motorola MB8611  **")
        assert parser_class is not None
        assert parser_class.name == "Motorola MB8611"

    def test_verified_parser_works_with_suffix(self):
        """Test that verified parser also works if suffix accidentally added."""
        ***REMOVED*** MB7621 is verified, but should still work with suffix
        parser_class = get_parser_by_name("Motorola MB7621 *")
        assert parser_class is not None
        assert parser_class.name == "Motorola MB7621"


class TestParserLoadingPerformance:
    """Test performance characteristics of parser loading."""

    def test_direct_load_faster_than_discovery(self):
        """Test that direct loading is faster than full discovery."""
        import time

        import custom_components.cable_modem_monitor.parsers as parser_module

        ***REMOVED*** Clear cache to ensure fair comparison
        parser_module._PARSER_CACHE = None

        ***REMOVED*** Time full discovery
        start = time.perf_counter()
        get_parsers(use_cache=False)
        discovery_time = time.perf_counter() - start

        ***REMOVED*** Time direct load
        start = time.perf_counter()
        get_parser_by_name("Motorola MB7621")
        direct_time = time.perf_counter() - start

        ***REMOVED*** Direct load should be significantly faster (at least 2x)
        ***REMOVED*** In practice, it's often 8x+ faster
        assert direct_time < discovery_time / 2

    def test_cached_load_is_instant(self):
        """Test that cached parser loading is very fast."""
        import time

        ***REMOVED*** Prime the cache
        get_parsers(use_cache=True)

        ***REMOVED*** Time cached load
        start = time.perf_counter()
        get_parsers(use_cache=True)
        cached_time = time.perf_counter() - start

        ***REMOVED*** Cached load should be extremely fast (< 10ms)
        ***REMOVED*** Note: 1ms was too aggressive and caused flaky tests
        assert cached_time < 0.01
