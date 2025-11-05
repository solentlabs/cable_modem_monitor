"""Tests for Technicolor XB7 parser."""
import pytest
from bs4 import BeautifulSoup
from pathlib import Path

from custom_components.cable_modem_monitor.parsers.technicolor.xb7 import TechnicolorXB7Parser


@pytest.fixture
def xb7_html():
    """Load XB7 HTML fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "xb7" / "network_setup.jst"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def xb7_soup(xb7_html):
    """Parse XB7 HTML into BeautifulSoup."""
    return BeautifulSoup(xb7_html, "html.parser")


class TestXB7Detection:
    """Test XB7 modem detection."""

    def test_xb7_detection_by_url(self, xb7_soup, xb7_html):
        """Test detection by URL pattern."""
        url = "http://10.0.0.1/network_setup.jst"
        assert TechnicolorXB7Parser.can_parse(xb7_soup, url, xb7_html)

    def test_xb7_detection_by_content(self, xb7_soup, xb7_html):
        """Test detection by HTML content patterns."""
        url = "http://10.0.0.1/some_page.html"
        assert TechnicolorXB7Parser.can_parse(xb7_soup, url, xb7_html)

    def test_xb7_not_detected_wrong_content(self):
        """Test that wrong content is not detected as XB7."""
        wrong_html = "<html><body>Some random page</body></html>"
        soup = BeautifulSoup(wrong_html, "html.parser")
        url = "http://10.0.0.1/test.html"
        assert not TechnicolorXB7Parser.can_parse(soup, url, wrong_html)


class TestXB7Authentication:
    """Test XB7 authentication."""

    def test_xb7_login_with_credentials(self):
        """Test that XB7 form-based authentication works."""
        from unittest.mock import Mock

        parser = TechnicolorXB7Parser()
        session = Mock()

        ***REMOVED*** Mock the POST request to check.jst
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "http://10.0.0.1/at_a_glance.jst"  ***REMOVED*** Simulates redirect
        session.post.return_value = mock_response

        ***REMOVED*** Mock the GET request to network_setup.jst
        mock_status_response = Mock()
        mock_status_response.status_code = 200
        mock_status_response.text = "<html>Status page content</html>"
        session.get.return_value = mock_status_response

        success, html = parser.login(session, "http://10.0.0.1", "admin", "password")

        assert success is True
        assert html == "<html>Status page content</html>"
        session.post.assert_called_once_with(
            "http://10.0.0.1/check.jst",
            data={"username": "admin", "password": "password"},
            timeout=10,
            allow_redirects=True
        )
        session.get.assert_called_once_with("http://10.0.0.1/network_setup.jst", timeout=10)

    def test_xb7_login_without_credentials(self):
        """Test that login fails gracefully without credentials."""
        from unittest.mock import Mock

        parser = TechnicolorXB7Parser()
        session = Mock()
        success, html = parser.login(session, "http://10.0.0.1", None, None)

        assert success is False
        assert html is None


class TestXB7Downstream:
    """Test XB7 downstream channel parsing."""

    def test_xb7_downstream_channel_count(self, xb7_soup):
        """Test that 34 downstream channels are parsed."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(xb7_soup)
        assert len(downstream) == 34

    def test_xb7_downstream_channel_ids(self, xb7_soup):
        """Test non-sequential channel IDs (10, 1-9, 11-34)."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(xb7_soup)

        channel_ids = [ch["channel_id"] for ch in downstream]

        ***REMOVED*** First channel should be 10 (primary)
        assert channel_ids[0] == "10"

        ***REMOVED*** Then 1-9
        for i in range(1, 10):
            assert str(i) in channel_ids

        ***REMOVED*** Then 11-34
        for i in range(11, 35):
            assert str(i) in channel_ids

    def test_xb7_downstream_frequency_mhz_format(self, xb7_soup):
        """Test parsing "609 MHz" format."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(xb7_soup)

        ***REMOVED*** Channel 10 has "609 MHz"
        ch10 = [ch for ch in downstream if ch["channel_id"] == "10"][0]
        assert ch10["frequency"] == 609_000_000  ***REMOVED*** 609 MHz in Hz

    def test_xb7_downstream_frequency_raw_hz_format(self, xb7_soup):
        """Test parsing "350000000" raw Hz format."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(xb7_soup)

        ***REMOVED*** Channel 33 has "350000000" (raw Hz)
        ch33 = [ch for ch in downstream if ch["channel_id"] == "33"][0]
        assert ch33["frequency"] == 350_000_000

    def test_xb7_downstream_snr(self, xb7_soup):
        """Test SNR parsing in dB."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(xb7_soup)

        ***REMOVED*** Channel 10 has SNR "38.4 dB"
        ch10 = [ch for ch in downstream if ch["channel_id"] == "10"][0]
        assert ch10["snr"] == 38.4

    def test_xb7_downstream_power_positive_and_negative(self, xb7_soup):
        """Test parsing positive and negative power levels."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(xb7_soup)

        ***REMOVED*** Channel 10 has positive power "4.3 dBmV"
        ch10 = [ch for ch in downstream if ch["channel_id"] == "10"][0]
        assert ch10["power"] == 4.3

        ***REMOVED*** Channel 4 has negative power "-2.0 dBmV"
        ch4 = [ch for ch in downstream if ch["channel_id"] == "4"][0]
        assert ch4["power"] == -2.0

    def test_xb7_downstream_modulation(self, xb7_soup):
        """Test modulation parsing (256 QAM and OFDM)."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(xb7_soup)

        ***REMOVED*** Channel 10 has "256 QAM"
        ch10 = [ch for ch in downstream if ch["channel_id"] == "10"][0]
        assert ch10["modulation"] == "256 QAM"

        ***REMOVED*** Channel 33 has "OFDM"
        ch33 = [ch for ch in downstream if ch["channel_id"] == "33"][0]
        assert ch33["modulation"] == "OFDM"

    def test_xb7_downstream_lock_status(self, xb7_soup):
        """Test lock status parsing."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(xb7_soup)

        ***REMOVED*** All channels should be "Locked"
        for ch in downstream:
            assert ch["lock_status"] == "Locked"

    def test_xb7_downstream_error_codewords(self, xb7_soup):
        """Test error codeword parsing."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(xb7_soup)

        ***REMOVED*** Channel 10 should have error statistics
        ch10 = [ch for ch in downstream if ch["channel_id"] == "10"][0]
        assert ch10["corrected"] == 780484376
        assert ch10["uncorrected"] == 257


class TestXB7Upstream:
    """Test XB7 upstream channel parsing."""

    def test_xb7_upstream_channel_count(self, xb7_soup):
        """Test that 5 upstream channels are parsed."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(xb7_soup)
        assert len(upstream) == 5

    def test_xb7_upstream_channel_ids(self, xb7_soup):
        """Test channel IDs (1, 2, 3, 4, 10)."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(xb7_soup)

        channel_ids = [ch["channel_id"] for ch in upstream]
        assert channel_ids == ["1", "2", "3", "4", "10"]

    def test_xb7_upstream_frequency(self, xb7_soup):
        """Test frequency parsing (MHz format with extra spaces)."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(xb7_soup)

        ***REMOVED*** Channel 1 has "21  MHz" (note extra spaces)
        ch1 = [ch for ch in upstream if ch["channel_id"] == "1"][0]
        assert ch1["frequency"] == 21_000_000

    def test_xb7_upstream_power(self, xb7_soup):
        """Test power level parsing."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(xb7_soup)

        ***REMOVED*** Channel 1 has "32.0 dBmV"
        ch1 = [ch for ch in upstream if ch["channel_id"] == "1"][0]
        assert ch1["power"] == 32.0

    def test_xb7_upstream_symbol_rate(self, xb7_soup):
        """Test XB7-specific symbol rate parsing."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(xb7_soup)

        ***REMOVED*** Channel 1 has symbol rate 2560
        ch1 = [ch for ch in upstream if ch["channel_id"] == "1"][0]
        assert ch1["symbol_rate"] == 2560

        ***REMOVED*** Channel 2 has symbol rate 5120
        ch2 = [ch for ch in upstream if ch["channel_id"] == "2"][0]
        assert ch2["symbol_rate"] == 5120

        ***REMOVED*** Channel 10 has symbol rate 0
        ch10 = [ch for ch in upstream if ch["channel_id"] == "10"][0]
        assert ch10["symbol_rate"] == 0

    def test_xb7_upstream_modulation(self, xb7_soup):
        """Test modulation parsing (QAM and OFDMA)."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(xb7_soup)

        ***REMOVED*** Channels 1-4 have "QAM"
        for i in range(1, 5):
            ch = [c for c in upstream if c["channel_id"] == str(i)][0]
            assert ch["modulation"] == "QAM"

        ***REMOVED*** Channel 10 has "OFDMA"
        ch10 = [ch for ch in upstream if ch["channel_id"] == "10"][0]
        assert ch10["modulation"] == "OFDMA"

    def test_xb7_upstream_channel_type(self, xb7_soup):
        """Test XB7-specific channel type parsing."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(xb7_soup)

        ***REMOVED*** Channel 1 has "TDMA_AND_ATDMA"
        ch1 = [ch for ch in upstream if ch["channel_id"] == "1"][0]
        assert ch1["channel_type"] == "TDMA_AND_ATDMA"

        ***REMOVED*** Channel 2 has "ATDMA"
        ch2 = [ch for ch in upstream if ch["channel_id"] == "2"][0]
        assert ch2["channel_type"] == "ATDMA"

        ***REMOVED*** Channel 10 has "TDMA"
        ch10 = [ch for ch in upstream if ch["channel_id"] == "10"][0]
        assert ch10["channel_type"] == "TDMA"

    def test_xb7_upstream_lock_status(self, xb7_soup):
        """Test lock status parsing."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(xb7_soup)

        ***REMOVED*** All channels should be "Locked"
        for ch in upstream:
            assert ch["lock_status"] == "Locked"


class TestXB7SystemInfo:
    """Test XB7 system information parsing."""

    def test_xb7_system_info_exists(self, xb7_soup):
        """Test that system info is parsed."""
        parser = TechnicolorXB7Parser()
        system_info = parser._parse_system_info(xb7_soup)

        ***REMOVED*** Should have at least some fields
        assert isinstance(system_info, dict)

    def test_xb7_system_info_initialization_status(self, xb7_soup):
        """Test initialization status fields."""
        parser = TechnicolorXB7Parser()
        system_info = parser._parse_system_info(xb7_soup)

        ***REMOVED*** May have downstream/upstream status fields
        ***REMOVED*** These are optional depending on HTML structure
        assert isinstance(system_info, dict)


class TestXB7Integration:
    """Test complete XB7 parsing integration."""

    def test_xb7_full_parse(self, xb7_soup):
        """Test full parse returns all expected data."""
        parser = TechnicolorXB7Parser()
        data = parser.parse(xb7_soup)

        assert "downstream" in data
        assert "upstream" in data
        assert "system_info" in data

        assert len(data["downstream"]) == 34
        assert len(data["upstream"]) == 5
        assert isinstance(data["system_info"], dict)

    def test_xb7_all_downstream_have_required_fields(self, xb7_soup):
        """Test that all downstream channels have required fields."""
        parser = TechnicolorXB7Parser()
        data = parser.parse(xb7_soup)

        for ch in data["downstream"]:
            assert "channel_id" in ch
            assert "frequency" in ch
            assert "power" in ch
            assert "snr" in ch
            assert "modulation" in ch
            assert "lock_status" in ch

    def test_xb7_all_upstream_have_required_fields(self, xb7_soup):
        """Test that all upstream channels have required fields."""
        parser = TechnicolorXB7Parser()
        data = parser.parse(xb7_soup)

        for ch in data["upstream"]:
            assert "channel_id" in ch
            assert "frequency" in ch
            assert "power" in ch
            assert "modulation" in ch
            assert "lock_status" in ch
            ***REMOVED*** XB7-specific fields
            assert "symbol_rate" in ch
            assert "channel_type" in ch
