"""Test parser against Paul's actual modem HTML from HAR capture.

This validates the parser works with the real HTML structure from
issue #93 (Paul's SB6190 with firmware 9.1.103AA65L).

Fixture extracted from: RAW_DATA/v3.13.0/arris-sb6190-paul/modem_20260127_paul.har
"""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.modems.arris.sb6190.parser import (
    ArrisSB6190Parser,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


class TestPaulHARParsing:
    """Test parser with Paul's real modem HTML."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return ArrisSB6190Parser()

    @pytest.fixture
    def paul_html(self):
        """Load Paul's status page HTML from HAR.

        Location: modems/arris/sb6190/fixtures/status-firmware-9.1.103.html
        Source: RAW_DATA/v3.13.0/arris-sb6190-paul/modem_20260127_paul.har
        """
        # Fixture is in modems/ directory, not custom_components/
        fixture_path = FIXTURES_DIR / "status-firmware-9.1.103.html"

        if not fixture_path.exists():
            pytest.skip(f"Paul's HAR fixture not found: {fixture_path}")

        with open(fixture_path) as f:
            return f.read()

    @pytest.fixture
    def paul_soup(self, paul_html):
        """Parse Paul's HTML with BeautifulSoup."""
        return BeautifulSoup(paul_html, "html.parser")

    def test_paul_fixture_structure(self, paul_html):
        """Verify Paul's HTML has expected structure."""
        assert "Downstream Bonded Channels" in paul_html
        assert "Upstream Bonded Channels" in paul_html
        assert 'colspan="9"' in paul_html
        assert "SB6190" in paul_html

    def test_paul_parse_returns_data(self, parser, paul_soup):
        """Parser MUST return channel data from Paul's HTML."""
        result = parser.parse(paul_soup)

        # CRITICAL: Parser must extract channels
        assert isinstance(result, dict), "Parser should return dict"
        assert "downstream" in result
        assert "upstream" in result

        # THIS IS THE KEY TEST: Parser must find channels in Paul's HTML
        downstream = result["downstream"]
        upstream = result["upstream"]

        print(f"\n{'='*60}")
        print("PAUL'S MODEM PARSING RESULTS:")
        print(f"  Downstream channels: {len(downstream)}")
        print(f"  Upstream channels: {len(upstream)}")

        if downstream:
            print(f"  First downstream channel: {downstream[0]}")
        else:
            print("  ❌ NO DOWNSTREAM CHANNELS PARSED")

        if upstream:
            print(f"  First upstream channel: {upstream[0]}")
        else:
            print("  ❌ NO UPSTREAM CHANNELS PARSED")
        print(f"{'='*60}\n")

        # FAIL if no channels parsed
        assert len(downstream) > 0, (
            "PARSER FAILURE: No downstream channels parsed from Paul's HTML! " "This reproduces the issue #93 bug."
        )

        assert len(upstream) > 0, "PARSER FAILURE: No upstream channels parsed from Paul's HTML!"

    def test_paul_expected_channel_count(self, parser, paul_soup):
        """Paul's modem should have 24 downstream, 4 upstream channels."""
        result = parser.parse(paul_soup)

        # Paul's diagnostics showed 24 downstream channels in the HTML
        # This validates we parse all of them
        assert len(result["downstream"]) == 24, f"Expected 24 downstream channels, got {len(result['downstream'])}"

        # Typical DOCSIS 3.0 setup
        assert len(result["upstream"]) >= 4, f"Expected at least 4 upstream channels, got {len(result['upstream'])}"

    def test_paul_channel_data_complete(self, parser, paul_soup):
        """All parsed channels should have complete data."""
        result = parser.parse(paul_soup)

        for i, ch in enumerate(result["downstream"]):
            assert ch.get("channel_id"), f"Channel {i} missing channel_id"
            assert ch.get("frequency") is not None, f"Channel {i} missing frequency"
            assert ch.get("power") is not None, f"Channel {i} missing power"
            assert ch.get("snr") is not None, f"Channel {i} missing SNR"
            # Errors can be None (not available) but keys should exist
            assert "corrected" in ch, f"Channel {i} missing corrected key"
            assert "uncorrected" in ch, f"Channel {i} missing uncorrected key"

    def test_paul_first_channel_values(self, parser, paul_soup):
        """Verify first channel matches expected values from HAR."""
        result = parser.parse(paul_soup)
        first = result["downstream"][0]

        # From Paul's HAR: Channel 1, 405.00 MHz, 3.50 dBmV, 40.95 dB, 76 corrected
        assert first["channel_id"] == "4", f"First channel ID should be '4', got {first['channel_id']}"
        assert first["frequency"] == 405_000_000, f"Frequency should be 405 MHz, got {first['frequency']}"
        assert first["power"] == pytest.approx(3.5, abs=0.1), f"Power should be ~3.5 dBmV, got {first['power']}"
        assert first["snr"] == pytest.approx(40.95, abs=0.1), f"SNR should be ~40.95 dB, got {first['snr']}"

    def test_paul_parse_resources_with_various_keys(self, parser, paul_soup):
        """Parser should work regardless of resource dict key."""
        # Test with "/" key (common default)
        result1 = parser.parse_resources({"/": paul_soup})
        assert len(result1["downstream"]) == 24

        # Test with actual path key
        result2 = parser.parse_resources({"/cgi-bin/status": paul_soup})
        assert len(result2["downstream"]) == 24

        # Test with mixed keys (should use first BeautifulSoup object found)
        result3 = parser.parse_resources(
            {
                "/some/other/path": "not a soup object",
                "/cgi-bin/status": paul_soup,
            }
        )
        assert len(result3["downstream"]) == 24

    def test_issue_93_wrong_html_in_slash_key(self, parser, paul_soup):
        """Test Issue #93 bug: auth response on '/' key, status page on explicit key.

        Bug: orchestrator adds 341 byte auth response to "/" key instead of status page.
        Parser tried "/" first and got "Url:/cgi-bin/status" text instead of channel data.

        Fix: Parser now tries explicit path first (/cgi-bin/status) before "/" fallback.
        """
        # Simulate auth response (341 bytes, just redirect text)
        auth_response_html = "Url:/cgi-bin/status"
        auth_soup = BeautifulSoup(auth_response_html, "html.parser")

        # Simulate the EXACT resources dict that production had (from debug logs)
        resources = {
            "/": auth_soup,  # ← WRONG HTML (341 bytes from auth POST)
            "/cgi-bin/status": paul_soup,  # ← CORRECT HTML (15,119 bytes with channels)
        }

        # Parser MUST use the correct key and return channels
        result = parser.parse_resources(resources)

        assert len(result["downstream"]) == 24, (
            "Issue #93 NOT FIXED: Parser still using '/' key with auth response "
            "instead of '/cgi-bin/status' with actual status page. "
            f"Got {len(result['downstream'])} channels instead of 24."
        )

        assert len(result["upstream"]) >= 4, f"Issue #93 NOT FIXED: Got {len(result['upstream'])} upstream channels"
