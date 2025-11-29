"""Tests for the ARRIS SB8200 parser."""

import os

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.arris.sb8200 import ArrisSB8200Parser
from custom_components.cable_modem_monitor.parsers.base_parser import ModemCapability


@pytest.fixture
def sb8200_html():
    """Load SB8200 HTML fixture (from Tim's fallback capture)."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sb8200", "root.html")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def sb8200_alt_html():
    """Load SB8200 alternative HTML fixture (original)."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sb8200", "cmconnectionstatus.html")
    ***REMOVED*** This fixture uses Windows-1252 encoding (copyright symbol)
    with open(fixture_path, encoding="cp1252") as f:
        return f.read()


class TestSB8200ParserDetection:
    """Test parser detection logic."""

    def test_can_parse_with_model_span(self, sb8200_html):
        """Test detection via model number span."""
        soup = BeautifulSoup(sb8200_html, "html.parser")
        assert ArrisSB8200Parser.can_parse(soup, "http://192.168.100.1/", sb8200_html)

    def test_can_parse_alt_fixture(self, sb8200_alt_html):
        """Test detection on alternative fixture."""
        soup = BeautifulSoup(sb8200_alt_html, "html.parser")
        assert ArrisSB8200Parser.can_parse(soup, "http://192.168.100.1/cmconnectionstatus.html", sb8200_alt_html)

    def test_parser_metadata(self):
        """Test parser metadata is correct."""
        assert ArrisSB8200Parser.name == "ARRIS SB8200"
        assert ArrisSB8200Parser.manufacturer == "ARRIS"
        assert "SB8200" in ArrisSB8200Parser.models
        assert ArrisSB8200Parser.docsis_version == "3.1"
        assert ArrisSB8200Parser.verified is True


class TestSB8200ParserCapabilities:
    """Test parser capabilities declaration."""

    def test_has_downstream_capability(self):
        """Test downstream channels capability."""
        assert ArrisSB8200Parser.has_capability(ModemCapability.DOWNSTREAM_CHANNELS)

    def test_has_upstream_capability(self):
        """Test upstream channels capability."""
        assert ArrisSB8200Parser.has_capability(ModemCapability.UPSTREAM_CHANNELS)

    def test_has_ofdm_downstream_capability(self):
        """Test OFDM downstream capability (DOCSIS 3.1)."""
        assert ArrisSB8200Parser.has_capability(ModemCapability.OFDM_DOWNSTREAM)

    def test_has_ofdm_upstream_capability(self):
        """Test OFDM upstream capability (DOCSIS 3.1)."""
        assert ArrisSB8200Parser.has_capability(ModemCapability.OFDM_UPSTREAM)

    def test_no_restart_capability(self):
        """Test that restart is NOT supported."""
        assert not ArrisSB8200Parser.has_capability(ModemCapability.RESTART)


class TestSB8200DownstreamParsing:
    """Test downstream channel parsing."""

    def test_downstream_channel_count(self, sb8200_html):
        """Test correct number of downstream channels parsed."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        assert "downstream" in data
        ***REMOVED*** SB8200 has 32 downstream channels (31 QAM256 + 1 OFDM)
        assert len(data["downstream"]) == 32

    def test_first_downstream_channel(self, sb8200_html):
        """Test first downstream channel values."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        ***REMOVED*** First channel in Tim's capture is channel 19
        first_ds = data["downstream"][0]
        assert first_ds["channel_id"] == "19"
        assert first_ds["frequency"] == 435000000  ***REMOVED*** 435 MHz
        assert first_ds["modulation"] == "QAM256"
        assert first_ds["power"] == 5.5
        assert first_ds["snr"] == 43.3
        assert first_ds["corrected"] == 158
        assert first_ds["uncorrected"] == 604

    def test_ofdm_downstream_channel(self, sb8200_html):
        """Test OFDM downstream channel (channel 33)."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        ***REMOVED*** Find the OFDM channel (modulation "Other")
        ofdm_channels = [ch for ch in data["downstream"] if ch.get("modulation") == "Other"]
        assert len(ofdm_channels) == 1

        ofdm = ofdm_channels[0]
        assert ofdm["channel_id"] == "33"
        assert ofdm["frequency"] == 524000000  ***REMOVED*** 524 MHz
        assert ofdm.get("is_ofdm") is True
        assert ofdm["power"] == 6.3
        assert ofdm["snr"] == 41.8


class TestSB8200UpstreamParsing:
    """Test upstream channel parsing."""

    def test_upstream_channel_count(self, sb8200_html):
        """Test correct number of upstream channels parsed."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        assert "upstream" in data
        ***REMOVED*** SB8200 has 3 upstream channels (2 SC-QAM + 1 OFDM)
        assert len(data["upstream"]) == 3

    def test_first_upstream_channel(self, sb8200_html):
        """Test first upstream channel values."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        first_us = data["upstream"][0]
        assert first_us["channel_id"] == "4"
        assert first_us["channel_type"] == "SC-QAM Upstream"
        assert first_us["frequency"] == 37000000  ***REMOVED*** 37 MHz
        assert first_us["width"] == 6400000  ***REMOVED*** 6.4 MHz
        assert first_us["power"] == 42.0

    def test_ofdm_upstream_channel(self, sb8200_html):
        """Test OFDM upstream channel."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        ***REMOVED*** Find the OFDM upstream channel
        ofdm_channels = [ch for ch in data["upstream"] if "OFDM" in ch.get("channel_type", "")]
        assert len(ofdm_channels) == 1

        ofdm = ofdm_channels[0]
        assert ofdm["channel_id"] == "1"
        assert ofdm["channel_type"] == "OFDM Upstream"
        assert ofdm["frequency"] == 6025000  ***REMOVED*** 6.025 MHz
        assert ofdm["width"] == 17200000  ***REMOVED*** 17.2 MHz
        assert ofdm.get("is_ofdm") is True


class TestSB8200SystemInfo:
    """Test system info parsing."""

    def test_system_info_exists(self, sb8200_html):
        """Test that system_info is returned."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        assert "system_info" in data
        assert isinstance(data["system_info"], dict)

    def test_current_time_parsed(self, sb8200_html):
        """Test current time is parsed from systime element."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        ***REMOVED*** Check that current_time was parsed (may contain IPv6 placeholder)
        if "current_time" in data["system_info"]:
            assert "2025" in data["system_info"]["current_time"]


class TestSB8200Login:
    """Test login behavior."""

    def test_login_always_succeeds(self):
        """Test that login always returns (True, None) (no auth required)."""
        parser = ArrisSB8200Parser()
        result = parser.login(None, "http://192.168.100.1", None, None)
        assert result == (True, None)


class TestSB8200AlternativeFixture:
    """Test parsing with alternative fixture."""

    def test_downstream_parsing_alt(self, sb8200_alt_html):
        """Test downstream parsing with alternative fixture."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_alt_html, "html.parser")
        data = parser.parse(soup)

        assert "downstream" in data
        assert len(data["downstream"]) == 32

    def test_upstream_parsing_alt(self, sb8200_alt_html):
        """Test upstream parsing with alternative fixture."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_alt_html, "html.parser")
        data = parser.parse(soup)

        assert "upstream" in data
        assert len(data["upstream"]) == 3
