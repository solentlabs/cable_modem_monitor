"""Tests for the Arris CM3500B parser."""

import os

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.arris.cm3500b import ArrisCM3500BParser
from custom_components.cable_modem_monitor.parsers.base_parser import ModemCapability, ParserStatus


@pytest.fixture
def arris_cm3500b_status_html():
    """Load status_cgi.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm3500b", "status_cgi.html")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def arris_cm3500b_vers_html():
    """Load vers_cgi.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm3500b", "vers_cgi.html")
    with open(fixture_path) as f:
        return f.read()


class TestCM3500BParserDetection:
    """Test parser detection logic."""

    def test_parser_detection_by_body_class(self, arris_cm3500b_status_html):
        """Test that the parser detects modem by body class."""
        soup = BeautifulSoup(arris_cm3500b_status_html, "html.parser")
        assert ArrisCM3500BParser.can_parse(soup, "https://192.168.100.1/cgi-bin/status_cgi", arris_cm3500b_status_html)

    def test_parser_detection_by_model_name(self, arris_cm3500b_status_html):
        """Test detection by Hardware Model field."""
        soup = BeautifulSoup(arris_cm3500b_status_html, "html.parser")
        assert ArrisCM3500BParser.can_parse(soup, "https://192.168.100.1/cgi-bin/status_cgi", arris_cm3500b_status_html)

    def test_parser_metadata(self):
        """Test parser metadata is correct."""
        assert ArrisCM3500BParser.name == "ARRIS CM3500B"
        assert ArrisCM3500BParser.manufacturer == "ARRIS"
        assert "CM3500B" in ArrisCM3500BParser.models
        assert ArrisCM3500BParser.docsis_version == "3.1"
        assert ArrisCM3500BParser.status == ParserStatus.AWAITING_VERIFICATION

    def test_can_parse_rejects_non_cm3500b(self):
        """Test that can_parse rejects non-CM3500B modems."""
        html = "<html><body>Some random modem page</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert not ArrisCM3500BParser.can_parse(soup, "http://example.com", html)


class TestCM3500BParserCapabilities:
    """Test parser capabilities declaration."""

    def test_has_downstream_capability(self):
        """Test downstream channels capability."""
        assert ArrisCM3500BParser.has_capability(ModemCapability.DOWNSTREAM_CHANNELS)

    def test_has_upstream_capability(self):
        """Test upstream channels capability."""
        assert ArrisCM3500BParser.has_capability(ModemCapability.UPSTREAM_CHANNELS)

    def test_has_ofdm_downstream_capability(self):
        """Test OFDM downstream capability (DOCSIS 3.1)."""
        assert ArrisCM3500BParser.has_capability(ModemCapability.OFDM_DOWNSTREAM)

    def test_has_ofdm_upstream_capability(self):
        """Test OFDM upstream capability (DOCSIS 3.1)."""
        assert ArrisCM3500BParser.has_capability(ModemCapability.OFDM_UPSTREAM)

    def test_has_uptime_capability(self):
        """Test uptime capability."""
        assert ArrisCM3500BParser.has_capability(ModemCapability.SYSTEM_UPTIME)

    def test_has_current_time_capability(self):
        """Test current time capability."""
        assert ArrisCM3500BParser.has_capability(ModemCapability.CURRENT_TIME)


class TestCM3500BDownstreamQAMParsing:
    """Test downstream QAM channel parsing."""

    def test_parsing_downstream_qam(self, arris_cm3500b_status_html):
        """Test parsing of downstream QAM data."""
        parser = ArrisCM3500BParser()
        soup = BeautifulSoup(arris_cm3500b_status_html, "html.parser")
        data = parser.parse(soup)

        # Verify downstream channels exist (24 QAM + 2 OFDM = 26 total)
        assert "downstream" in data
        assert len(data["downstream"]) == 26

        # Check first QAM downstream channel
        first_ds = data["downstream"][0]
        assert first_ds["channel_id"] == "3"  # DCID
        assert first_ds["frequency"] == 570000000  # 570.00 MHz in Hz
        assert first_ds["power"] == -11.2
        assert first_ds["snr"] == 36.61
        assert first_ds["modulation"] == "256QAM"
        assert first_ds["corrected"] == 9
        assert first_ds["uncorrected"] == 0

    def test_parsing_downstream_frequency_conversion(self, arris_cm3500b_status_html):
        """Test that frequencies are correctly converted to Hz."""
        parser = ArrisCM3500BParser()
        soup = BeautifulSoup(arris_cm3500b_status_html, "html.parser")
        data = parser.parse(soup)

        # Check a few channels for correct frequency conversion
        qam_channels = [ch for ch in data["downstream"] if not ch.get("is_ofdm")]

        # First channel: 570.00 MHz
        assert qam_channels[0]["frequency"] == 570000000

        # Channel with 114.00 MHz (lower frequency band)
        low_freq_ch = next((ch for ch in qam_channels if ch.get("frequency") == 114000000), None)
        assert low_freq_ch is not None


class TestCM3500BDownstreamOFDMParsing:
    """Test downstream OFDM channel parsing."""

    def test_parsing_downstream_ofdm(self, arris_cm3500b_status_html):
        """Test parsing of downstream OFDM data."""
        parser = ArrisCM3500BParser()
        soup = BeautifulSoup(arris_cm3500b_status_html, "html.parser")
        data = parser.parse(soup)

        # Filter OFDM channels
        ofdm_channels = [ch for ch in data["downstream"] if ch.get("is_ofdm")]
        assert len(ofdm_channels) == 2

        # Check first OFDM channel
        first_ofdm = ofdm_channels[0]
        assert first_ofdm["channel_id"] == "OFDM-1"
        assert first_ofdm["is_ofdm"] is True
        assert first_ofdm["fft_type"] == "4K"
        assert first_ofdm["channel_width"] == 190
        assert first_ofdm["active_subcarriers"] == 3800
        assert first_ofdm["snr"] == 43  # MER Data
        assert first_ofdm["modulation"] == "OFDM"


class TestCM3500BUpstreamQAMParsing:
    """Test upstream QAM channel parsing."""

    def test_parsing_upstream_qam(self, arris_cm3500b_status_html):
        """Test parsing of upstream QAM data."""
        parser = ArrisCM3500BParser()
        soup = BeautifulSoup(arris_cm3500b_status_html, "html.parser")
        data = parser.parse(soup)

        # Verify upstream channels exist (4 QAM + 1 OFDMA = 5 total)
        assert "upstream" in data
        assert len(data["upstream"]) == 5

        # Check first upstream QAM channel
        first_us = data["upstream"][0]
        assert first_us["channel_id"] == "10"  # UCID
        assert first_us["frequency"] == 37200000  # 37.20 MHz in Hz
        assert first_us["power"] == 45.25
        assert first_us["channel_type"] == "DOCSIS2.0 (ATDMA)"
        assert first_us["symbol_rate"] == 5120
        assert first_us["modulation"] == "16QAM"


class TestCM3500BUpstreamOFDMParsing:
    """Test upstream OFDM (OFDMA) channel parsing."""

    def test_parsing_upstream_ofdma(self, arris_cm3500b_status_html):
        """Test parsing of upstream OFDMA data.

        Note: CM3500B firmware has a bug where the header has 7 columns but
        data has 9 cells. The parser handles this by detecting the extra columns.
        """
        parser = ArrisCM3500BParser()
        soup = BeautifulSoup(arris_cm3500b_status_html, "html.parser")
        data = parser.parse(soup)

        # Filter OFDMA channels
        ofdma_channels = [ch for ch in data["upstream"] if ch.get("is_ofdm")]
        assert len(ofdma_channels) == 1

        # Check OFDMA channel
        ofdma = ofdma_channels[0]
        assert ofdma["channel_id"] == "OFDMA-0"
        assert ofdma["is_ofdm"] is True
        assert ofdma["fft_type"] == "2K"
        assert ofdma["active_subcarriers"] == 640
        assert ofdma["modulation"] == "OFDMA"
        # Power is in cells[8] due to firmware bug (extra subcarrier index columns)
        assert ofdma["power"] == 45.0
        # Frequencies from cells[6] and cells[7]
        assert ofdma["first_subcarrier_freq"] == 29.8
        assert ofdma["last_subcarrier_freq"] == 64.8


class TestCM3500BSystemInfo:
    """Test system info parsing."""

    def test_parsing_system_info(self, arris_cm3500b_status_html):
        """Test parsing of system info."""
        parser = ArrisCM3500BParser()
        soup = BeautifulSoup(arris_cm3500b_status_html, "html.parser")
        data = parser.parse(soup)

        # Verify system info exists
        assert "system_info" in data
        info = data["system_info"]

        assert info["system_uptime"] == "0 d:  7 h: 40 m"
        assert info["cm_status"] == "OPERATIONAL"
        assert "2025-12-19" in info["current_time"]
        assert info["hardware_version"] == "CM3500B"


class TestCM3500BEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_html_returns_empty_channels(self):
        """Test parsing empty HTML returns empty lists."""
        parser = ArrisCM3500BParser()
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        data = parser.parse(soup)

        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}

    def test_no_downstream_table_returns_empty(self):
        """Test parsing HTML without downstream table returns empty list."""
        parser = ArrisCM3500BParser()
        html = "<html><body><table><tr><td>Some other data</td></tr></table></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        assert data["downstream"] == []

    def test_no_upstream_table_returns_empty(self):
        """Test parsing HTML without upstream table returns empty list."""
        parser = ArrisCM3500BParser()
        html = "<html><body><table><tr><td>Some other data</td></tr></table></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        assert data["upstream"] == []

    def test_malformed_table_handled_gracefully(self):
        """Test that malformed tables don't crash the parser."""
        parser = ArrisCM3500BParser()
        html = """
        <html><body>
        <h4>Downstream QAM</h4>
        <table>
            <tr><td>Downstream 1</td></tr>
        </table>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        # Should return empty list, not crash
        assert data["downstream"] == []

    def test_missing_uptime_handled_gracefully(self):
        """Test that missing uptime doesn't crash the parser."""
        parser = ArrisCM3500BParser()
        html = "<html><body><table><tr><td>No uptime here</td></tr></table></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        system_info = parser._parse_system_info(soup)

        assert system_info == {}

    def test_frequency_parsing_handles_invalid_format(self):
        """Test that invalid frequency format returns None."""
        parser = ArrisCM3500BParser()
        assert parser._parse_frequency_mhz("invalid") is None
        assert parser._parse_frequency_mhz("") is None
        assert parser._parse_frequency_mhz("570.00 MHz") == 570000000


class TestCM3500BFixtures:
    """Test that required fixture files exist."""

    def test_status_fixture_exists(self):
        """Test that status_cgi.html fixture exists."""
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm3500b", "status_cgi.html")
        assert os.path.exists(fixture_path), f"Fixture not found: {fixture_path}"

    def test_vers_fixture_exists(self):
        """Test that vers_cgi.html fixture exists."""
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm3500b", "vers_cgi.html")
        assert os.path.exists(fixture_path), f"Fixture not found: {fixture_path}"

    def test_metadata_exists(self):
        """Test that metadata.yaml fixture exists."""
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm3500b", "metadata.yaml")
        assert os.path.exists(fixture_path), f"Fixture not found: {fixture_path}"
