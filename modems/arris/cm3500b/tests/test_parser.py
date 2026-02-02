"""Tests for the ARRIS CM3500B parser.

Tests parsing of:
- Downstream QAM channels (24 channels)
- Downstream OFDM channels (2 channels)
- Upstream QAM channels (4 channels)
- Upstream OFDMA channels (1 channel)
- System info (uptime, status, hardware version)
"""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from modems.arris.cm3500b.parser import (
    ArrisCM3500BParser,
)

# Fixture directory is ../fixtures relative to tests/
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def status_html():
    """Load status_cgi.html fixture."""
    fixture_path = FIXTURES_DIR / "cgi-bin" / "status_cgi.html"
    return fixture_path.read_text()


@pytest.fixture
def parser():
    """Create parser instance."""
    return ArrisCM3500BParser()


class TestParserDetection:
    """Test parser detection logic."""

    def test_can_parse_by_body_class(self, status_html):
        """Test that the parser detects modem by body class CM3500."""
        soup = BeautifulSoup(status_html, "html.parser")
        assert ArrisCM3500BParser.can_parse(soup, "https://192.168.100.1/cgi-bin/status_cgi", status_html)

    def test_can_parse_by_model_name(self, status_html):
        """Test detection by Hardware Model field."""
        soup = BeautifulSoup(status_html, "html.parser")
        assert ArrisCM3500BParser.can_parse(soup, "https://192.168.100.1/cgi-bin/status_cgi", status_html)

    def test_rejects_non_cm3500b(self):
        """Test that can_parse rejects non-CM3500B modems."""
        html = "<html><body>Some random modem page</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert not ArrisCM3500BParser.can_parse(soup, "http://example.com", html)


class TestDownstreamQAMParsing:
    """Test downstream QAM channel parsing."""

    def test_parses_all_qam_channels(self, parser, status_html):
        """Test parsing of downstream QAM data."""
        soup = BeautifulSoup(status_html, "html.parser")
        data = parser.parse(soup)

        # 24 QAM + 2 OFDM = 26 total downstream
        assert "downstream" in data
        assert len(data["downstream"]) == 26

        # Filter QAM-only channels
        qam_channels = [ch for ch in data["downstream"] if not ch.get("is_ofdm")]
        assert len(qam_channels) == 24

    def test_first_qam_channel_values(self, parser, status_html):
        """Test first QAM channel has correct values."""
        soup = BeautifulSoup(status_html, "html.parser")
        data = parser.parse(soup)

        first_ds = data["downstream"][0]
        assert first_ds["channel_id"] == "3"  # DCID
        assert first_ds["frequency"] == 570000000  # 570.00 MHz in Hz
        assert first_ds["power"] == -11.2
        assert first_ds["snr"] == 36.61
        assert first_ds["modulation"] == "256QAM"
        assert first_ds["corrected"] == 9
        assert first_ds["uncorrected"] == 0

    def test_frequency_conversion(self, parser, status_html):
        """Test that frequencies are correctly converted to Hz."""
        soup = BeautifulSoup(status_html, "html.parser")
        data = parser.parse(soup)

        qam_channels = [ch for ch in data["downstream"] if not ch.get("is_ofdm")]

        # First channel: 570.00 MHz
        assert qam_channels[0]["frequency"] == 570000000

        # Check lower frequency band channel exists (114 MHz)
        low_freq_ch = next((ch for ch in qam_channels if ch.get("frequency") == 114000000), None)
        assert low_freq_ch is not None


class TestDownstreamOFDMParsing:
    """Test downstream OFDM channel parsing."""

    def test_parses_ofdm_channels(self, parser, status_html):
        """Test parsing of downstream OFDM data."""
        soup = BeautifulSoup(status_html, "html.parser")
        data = parser.parse(soup)

        ofdm_channels = [ch for ch in data["downstream"] if ch.get("is_ofdm")]
        assert len(ofdm_channels) == 2

    def test_first_ofdm_channel_values(self, parser, status_html):
        """Test first OFDM channel has correct values."""
        soup = BeautifulSoup(status_html, "html.parser")
        data = parser.parse(soup)

        ofdm_channels = [ch for ch in data["downstream"] if ch.get("is_ofdm")]
        first_ofdm = ofdm_channels[0]

        assert first_ofdm["channel_id"] == "OFDM-1"
        assert first_ofdm["is_ofdm"] is True
        assert first_ofdm["fft_type"] == "4K"
        assert first_ofdm["channel_width"] == 190
        assert first_ofdm["active_subcarriers"] == 3800
        assert first_ofdm["snr"] == 43  # MER Data
        assert first_ofdm["modulation"] == "OFDM"
        # Note: OFDM downstream doesn't have power on CM3500B


class TestUpstreamQAMParsing:
    """Test upstream QAM channel parsing."""

    def test_parses_all_upstream_channels(self, parser, status_html):
        """Test parsing of upstream data."""
        soup = BeautifulSoup(status_html, "html.parser")
        data = parser.parse(soup)

        # 4 QAM + 1 OFDMA = 5 total upstream
        assert "upstream" in data
        assert len(data["upstream"]) == 5

    def test_first_upstream_channel_values(self, parser, status_html):
        """Test first upstream QAM channel has correct values."""
        soup = BeautifulSoup(status_html, "html.parser")
        data = parser.parse(soup)

        first_us = data["upstream"][0]
        assert first_us["channel_id"] == "10"  # UCID
        assert first_us["frequency"] == 37200000  # 37.20 MHz in Hz
        assert first_us["power"] == 45.25
        assert first_us["channel_type"] == "DOCSIS2.0 (ATDMA)"
        assert first_us["symbol_rate"] == 5120
        assert first_us["modulation"] == "16QAM"


class TestUpstreamOFDMAParsing:
    """Test upstream OFDMA channel parsing."""

    def test_parses_ofdma_channel(self, parser, status_html):
        """Test parsing of upstream OFDMA data.

        Note: CM3500B firmware has a bug where the header has 7 columns but
        data has 9 cells. The parser handles this by detecting the extra columns.
        """
        soup = BeautifulSoup(status_html, "html.parser")
        data = parser.parse(soup)

        ofdma_channels = [ch for ch in data["upstream"] if ch.get("is_ofdm")]
        assert len(ofdma_channels) == 1

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


class TestSystemInfo:
    """Test system info parsing."""

    def test_parses_system_info(self, parser, status_html):
        """Test parsing of system info."""
        soup = BeautifulSoup(status_html, "html.parser")
        data = parser.parse(soup)

        assert "system_info" in data
        info = data["system_info"]

        assert info["system_uptime"] == "0 d:  7 h: 40 m"
        assert info["cm_status"] == "OPERATIONAL"
        assert "2025-12-19" in info["current_time"]
        assert info["hardware_version"] == "CM3500B"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_html_returns_empty_channels(self, parser):
        """Test parsing empty HTML returns empty lists."""
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        data = parser.parse(soup)

        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}

    def test_malformed_table_handled_gracefully(self, parser):
        """Test that malformed tables don't crash the parser."""
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

    def test_frequency_parsing_handles_invalid_format(self, parser):
        """Test that invalid frequency format returns None."""
        assert parser._parse_frequency_mhz("invalid") is None
        assert parser._parse_frequency_mhz("") is None
        assert parser._parse_frequency_mhz("570.00 MHz") == 570000000


class TestFixtures:
    """Test that required fixture files exist."""

    def test_status_fixture_exists(self):
        """Test that status_cgi.html fixture exists."""
        fixture_path = FIXTURES_DIR / "cgi-bin" / "status_cgi.html"
        assert fixture_path.exists(), f"Fixture not found: {fixture_path}"

    def test_vers_fixture_exists(self):
        """Test that vers_cgi.html fixture exists."""
        fixture_path = FIXTURES_DIR / "cgi-bin" / "vers_cgi.html"
        assert fixture_path.exists(), f"Fixture not found: {fixture_path}"

    def test_metadata_exists(self):
        """Test that metadata.yaml fixture exists."""
        fixture_path = FIXTURES_DIR / "metadata.yaml"
        assert fixture_path.exists(), f"Fixture not found: {fixture_path}"
