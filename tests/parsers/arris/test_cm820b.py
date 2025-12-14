"""Tests for the Arris CM820B parser."""

import os

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.arris.cm820b import ArrisCM820BParser
from custom_components.cable_modem_monitor.parsers.base_parser import ModemCapability


@pytest.fixture
def arris_cm820b_status_html():
    """Load cm820b_status.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm820b", "cm820b_status.html")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def arris_cm820b_info_html():
    """Load cm820b_info.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm820b", "cm820b_info.html")
    with open(fixture_path) as f:
        return f.read()


class TestCM820BParserDetection:
    """Test parser detection logic."""

    def test_parser_detection(self, arris_cm820b_info_html):
        """Test that the Arris CM820B parser detects the modem."""
        soup = BeautifulSoup(arris_cm820b_info_html, "html.parser")
        assert ArrisCM820BParser.can_parse(soup, "http://192.168.100.1/cgi-bin/vers_cgi", arris_cm820b_info_html)

    def test_parser_metadata(self):
        """Test parser metadata is correct."""
        assert ArrisCM820BParser.name == "ARRIS CM820B"
        assert ArrisCM820BParser.manufacturer == "ARRIS"
        assert "CM820B" in ArrisCM820BParser.models
        assert ArrisCM820BParser.docsis_version == "3.0"
        assert ArrisCM820BParser().verified is True  ***REMOVED*** Verified by @dimkalinux (PR ***REMOVED***57)


class TestCM820BParserCapabilities:
    """Test parser capabilities declaration."""

    def test_has_downstream_capability(self):
        """Test downstream channels capability."""
        assert ArrisCM820BParser.has_capability(ModemCapability.DOWNSTREAM_CHANNELS)

    def test_has_upstream_capability(self):
        """Test upstream channels capability."""
        assert ArrisCM820BParser.has_capability(ModemCapability.UPSTREAM_CHANNELS)

    def test_has_uptime_capability(self):
        """Test uptime capability (from cmswinfo.html)."""
        assert ArrisCM820BParser.has_capability(ModemCapability.SYSTEM_UPTIME)


class TestCM820BDownstreamParsing:
    """Test downstream channel parsing."""

    def test_parsing_downstream(self, arris_cm820b_status_html):
        """Test parsing of Arris CM820B downstream data."""
        parser = ArrisCM820BParser()
        soup = BeautifulSoup(arris_cm820b_status_html, "html.parser")
        data = parser.parse(soup)

        ***REMOVED*** Verify downstream channels (8 channels in fixture)
        assert "downstream" in data
        assert len(data["downstream"]) == 8

        ***REMOVED*** Check first downstream channel
        first_ds = data["downstream"][0]
        assert first_ds["channel_id"] == "73"
        assert first_ds["frequency"] == 178000000
        assert first_ds["snr"] == 34.48
        assert first_ds["power"] == 3.82
        assert first_ds["corrected"] == 33958022
        assert first_ds["uncorrected"] == 445244
        assert first_ds["modulation"] == "256QAM"

        ***REMOVED*** Check second channel to verify parsing
        second_ds = data["downstream"][1]
        assert second_ds["channel_id"] == "74"
        assert second_ds["frequency"] == 186000000
        assert second_ds["modulation"] == "256QAM"


class TestCM820BUpstreamParsing:
    """Test upstream channel parsing."""

    def test_parsing_upstream(self, arris_cm820b_status_html):
        """Test parsing of Arris CM820B upstream data."""
        parser = ArrisCM820BParser()
        soup = BeautifulSoup(arris_cm820b_status_html, "html.parser")
        data = parser.parse(soup)

        ***REMOVED*** Verify upstream channels (4 channels expected)
        assert "upstream" in data
        assert len(data["upstream"]) == 4

        ***REMOVED*** Check first upstream channel
        first_us = data["upstream"][0]
        assert first_us["channel_id"] == "6"
        assert first_us["frequency"] == 47000000
        assert first_us["power"] == 46.25
        assert first_us["modulation"] == "32QAM"
        assert first_us["symbol_rate"] == 5120


class TestCM820BSystemInfo:
    """Test system info parsing."""

    def test_parsing_system_info(self, arris_cm820b_status_html):
        """Test parsing of Arris CM820B system info."""
        parser = ArrisCM820BParser()
        soup = BeautifulSoup(arris_cm820b_status_html, "html.parser")
        data = parser.parse(soup)

        ***REMOVED*** Verify system info exists
        assert "system_info" in data
        assert isinstance(data["system_info"], dict)
        assert data["system_info"]["system_uptime"] == "6 d:  2 h: 33  m"


class TestCM820BEdgeCases:
    """Test edge cases and error handling."""

    def test_login_returns_success(self):
        """Test that login always succeeds (no auth required)."""
        parser = ArrisCM820BParser()
        success, error = parser.login(None, None, None, None)
        assert success is True
        assert error is None

    def test_empty_html_returns_empty_channels(self):
        """Test parsing empty HTML returns empty lists."""
        parser = ArrisCM820BParser()
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        data = parser.parse(soup)

        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}

    def test_no_downstream_table_returns_empty(self):
        """Test parsing HTML without downstream table returns empty list."""
        parser = ArrisCM820BParser()
        html = "<html><body><table><tr><td>Some other data</td></tr></table></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        assert data["downstream"] == []

    def test_no_upstream_table_returns_empty(self):
        """Test parsing HTML without upstream table returns empty list."""
        parser = ArrisCM820BParser()
        html = "<html><body><table><tr><td>Some other data</td></tr></table></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        assert data["upstream"] == []

    def test_malformed_table_handled_gracefully(self):
        """Test that malformed tables don't crash the parser."""
        parser = ArrisCM820BParser()
        ***REMOVED*** Table with Downstream 1 but incomplete rows
        html = """
        <html><body>
        <table>
            <tr><td>Downstream 1</td></tr>
        </table>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        ***REMOVED*** Should return empty list, not crash
        assert data["downstream"] == []

    def test_missing_uptime_handled_gracefully(self):
        """Test that missing uptime doesn't crash the parser."""
        parser = ArrisCM820BParser()
        html = "<html><body><table><tr><td>No uptime here</td></tr></table></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        system_info = parser._parse_system_info(soup)

        assert system_info == {}

    def test_can_parse_rejects_non_cm820b(self):
        """Test that can_parse rejects non-CM820B modems."""
        html = "<html><body>Some random modem page</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert not ArrisCM820BParser.can_parse(soup, "http://example.com", html)
