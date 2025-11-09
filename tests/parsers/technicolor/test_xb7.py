"""Tests for Technicolor XB7 parser."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.technicolor.xb7 import TechnicolorXB7Parser


@pytest.fixture
def network_setup_html():
    """Load network_setup.jst HTML fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "xb7" / "network_setup.jst"
    with open(fixture_path, encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def soup(network_setup_html):
    """Parse HTML into BeautifulSoup."""
    return BeautifulSoup(network_setup_html, "html.parser")


class TestDetection:
    """Test modem detection."""

    def test_by_url(self, soup, network_setup_html):
        """Test detection by URL pattern."""
        url = "http://10.0.0.1/network_setup.jst"
        assert TechnicolorXB7Parser.can_parse(soup, url, network_setup_html)

    def test_by_content(self, soup, network_setup_html):
        """Test detection by HTML content patterns."""
        url = "http://10.0.0.1/some_page.html"
        assert TechnicolorXB7Parser.can_parse(soup, url, network_setup_html)

    def test_rejects_wrong_content(self):
        """Test that wrong content is not detected."""
        wrong_html = "<html><body>Some random page</body></html>"
        soup = BeautifulSoup(wrong_html, "html.parser")
        url = "http://10.0.0.1/test.html"
        assert not TechnicolorXB7Parser.can_parse(soup, url, wrong_html)


class TestAuthentication:
    """Test authentication."""

    def test_login_with_credentials(self):
        """Test that form-based authentication works."""
        from unittest.mock import Mock

        parser = TechnicolorXB7Parser()
        session = Mock()

        # Mock the POST request to check.jst
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "http://10.0.0.1/at_a_glance.jst"  # Simulates redirect
        session.post.return_value = mock_response

        # Mock the GET request to network_setup.jst
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
            allow_redirects=True,
        )
        session.get.assert_called_once_with("http://10.0.0.1/network_setup.jst", timeout=10)

    def test_login_without_credentials(self):
        """Test that login fails gracefully without credentials."""
        from unittest.mock import Mock

        parser = TechnicolorXB7Parser()
        session = Mock()
        success, html = parser.login(session, "http://10.0.0.1", None, None)

        assert success is False
        assert html is None


class TestDownstream:
    """Test downstream channel parsing."""

    def test_channel_count(self, soup):
        """Test that 34 downstream channels are parsed."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(soup)
        assert len(downstream) == 34

    def test_channel_ids(self, soup):
        """Test non-sequential channel IDs (10, 1-9, 11-34)."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(soup)

        channel_ids = [ch["channel_id"] for ch in downstream]

        # First channel should be 10 (primary)
        assert channel_ids[0] == "10"

        # Then 1-9
        for i in range(1, 10):
            assert str(i) in channel_ids

        # Then 11-34
        for i in range(11, 35):
            assert str(i) in channel_ids

    def test_frequency_mhz_format(self, soup):
        """Test parsing "609 MHz" format."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(soup)

        # Channel 10 has "609 MHz"
        ch10 = [ch for ch in downstream if ch["channel_id"] == "10"][0]
        assert ch10["frequency"] == 609_000_000  # 609 MHz in Hz

    def test_frequency_raw_hz_format(self, soup):
        """Test parsing "350000000" raw Hz format."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(soup)

        # Channel 33 has "350000000" (raw Hz)
        ch33 = [ch for ch in downstream if ch["channel_id"] == "33"][0]
        assert ch33["frequency"] == 350_000_000

    def test_snr(self, soup):
        """Test SNR parsing in dB."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(soup)

        # Channel 10 has SNR "38.4 dB"
        ch10 = [ch for ch in downstream if ch["channel_id"] == "10"][0]
        assert ch10["snr"] == 38.4

    def test_power_positive_and_negative(self, soup):
        """Test parsing positive and negative power levels."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(soup)

        # Channel 10 has positive power "4.3 dBmV"
        ch10 = [ch for ch in downstream if ch["channel_id"] == "10"][0]
        assert ch10["power"] == 4.3

        # Channel 4 has negative power "-2.0 dBmV"
        ch4 = [ch for ch in downstream if ch["channel_id"] == "4"][0]
        assert ch4["power"] == -2.0

    def test_modulation(self, soup):
        """Test modulation parsing (256 QAM and OFDM)."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(soup)

        # Channel 10 has "256 QAM"
        ch10 = [ch for ch in downstream if ch["channel_id"] == "10"][0]
        assert ch10["modulation"] == "256 QAM"

        # Channel 33 has "OFDM"
        ch33 = [ch for ch in downstream if ch["channel_id"] == "33"][0]
        assert ch33["modulation"] == "OFDM"

    def test_lock_status(self, soup):
        """Test lock status parsing."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(soup)

        # All channels should be "Locked"
        for ch in downstream:
            assert ch["lock_status"] == "Locked"

    def test_error_codewords(self, soup):
        """Test error codeword parsing."""
        parser = TechnicolorXB7Parser()
        downstream = parser._parse_downstream(soup)

        # Channel 10 should have error statistics
        ch10 = [ch for ch in downstream if ch["channel_id"] == "10"][0]
        assert ch10["corrected"] == 780484376
        assert ch10["uncorrected"] == 257


class TestUpstream:
    """Test upstream channel parsing."""

    def test_channel_count(self, soup):
        """Test that 5 upstream channels are parsed."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(soup)
        assert len(upstream) == 5

    def test_channel_ids(self, soup):
        """Test channel IDs (1, 2, 3, 4, 10)."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(soup)

        channel_ids = [ch["channel_id"] for ch in upstream]
        assert channel_ids == ["1", "2", "3", "4", "10"]

    def test_frequency(self, soup):
        """Test frequency parsing (MHz format with extra spaces)."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(soup)

        # Channel 1 has "21  MHz" (note extra spaces)
        ch1 = [ch for ch in upstream if ch["channel_id"] == "1"][0]
        assert ch1["frequency"] == 21_000_000

    def test_power(self, soup):
        """Test power level parsing."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(soup)

        # Channel 1 has "32.0 dBmV"
        ch1 = [ch for ch in upstream if ch["channel_id"] == "1"][0]
        assert ch1["power"] == 32.0

    def test_symbol_rate(self, soup):
        """Test symbol rate parsing."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(soup)

        # Channel 1 has symbol rate 2560
        ch1 = [ch for ch in upstream if ch["channel_id"] == "1"][0]
        assert ch1["symbol_rate"] == 2560

        # Channel 2 has symbol rate 5120
        ch2 = [ch for ch in upstream if ch["channel_id"] == "2"][0]
        assert ch2["symbol_rate"] == 5120

        # Channel 10 has symbol rate 0
        ch10 = [ch for ch in upstream if ch["channel_id"] == "10"][0]
        assert ch10["symbol_rate"] == 0

    def test_modulation(self, soup):
        """Test modulation parsing (QAM and OFDMA)."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(soup)

        # Channels 1-4 have "QAM"
        for i in range(1, 5):
            ch = [c for c in upstream if c["channel_id"] == str(i)][0]
            assert ch["modulation"] == "QAM"

        # Channel 10 has "OFDMA"
        ch10 = [ch for ch in upstream if ch["channel_id"] == "10"][0]
        assert ch10["modulation"] == "OFDMA"

    def test_channel_type(self, soup):
        """Test channel type parsing."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(soup)

        # Channel 1 has "TDMA_AND_ATDMA"
        ch1 = [ch for ch in upstream if ch["channel_id"] == "1"][0]
        assert ch1["channel_type"] == "TDMA_AND_ATDMA"

        # Channel 2 has "ATDMA"
        ch2 = [ch for ch in upstream if ch["channel_id"] == "2"][0]
        assert ch2["channel_type"] == "ATDMA"

        # Channel 10 has "TDMA"
        ch10 = [ch for ch in upstream if ch["channel_id"] == "10"][0]
        assert ch10["channel_type"] == "TDMA"

    def test_lock_status(self, soup):
        """Test lock status parsing."""
        parser = TechnicolorXB7Parser()
        upstream = parser._parse_upstream(soup)

        # All channels should be "Locked"
        for ch in upstream:
            assert ch["lock_status"] == "Locked"


class TestSystemInfo:
    """Test system information parsing."""

    def test_exists(self, soup):
        """Test that system info is parsed."""
        parser = TechnicolorXB7Parser()
        system_info = parser._parse_system_info(soup)

        # Should have at least some fields
        assert isinstance(system_info, dict)

    def test_initialization_status(self, soup):
        """Test initialization status fields."""
        parser = TechnicolorXB7Parser()
        system_info = parser._parse_system_info(soup)

        # May have downstream/upstream status fields
        # These are optional depending on HTML structure
        assert isinstance(system_info, dict)

    def test_uptime(self, soup):
        """Test parsing system uptime."""
        parser = TechnicolorXB7Parser()
        system_info = parser._parse_system_info(soup)

        assert "system_uptime" in system_info
        assert system_info["system_uptime"] == "21 days 15h: 20m: 33s"

    def test_software_version(self, soup):
        """Test parsing Download Version as software_version."""
        parser = TechnicolorXB7Parser()
        system_info = parser._parse_system_info(soup)

        assert "software_version" in system_info
        assert system_info["software_version"] == "Prod_23.2_231009 & Prod_23.2_231009"

    def test_last_boot_time(self, soup):
        """Test that last_boot_time is calculated from uptime."""
        parser = TechnicolorXB7Parser()
        system_info = parser._parse_system_info(soup)

        assert "last_boot_time" in system_info
        assert system_info["last_boot_time"] is not None

        # Verify boot time is approximately 21 days, 15h, 20m, 33s ago
        boot_time = datetime.fromisoformat(system_info["last_boot_time"])
        expected_uptime = timedelta(days=21, hours=15, minutes=20, seconds=33)
        actual_uptime = datetime.now() - boot_time

        # Allow 1 minute tolerance for test execution time
        assert abs((actual_uptime - expected_uptime).total_seconds()) < 60

    def test_primary_channel(self, soup):
        """Test parsing primary downstream channel."""
        parser = TechnicolorXB7Parser()
        primary_channel = parser._parse_primary_channel(soup)

        assert primary_channel == "10"


class TestIntegration:
    """Test complete parsing integration."""

    def test_full_parse(self, soup):
        """Test full parse returns all expected data."""
        parser = TechnicolorXB7Parser()
        data = parser.parse(soup)

        assert "downstream" in data
        assert "upstream" in data
        assert "system_info" in data

        assert len(data["downstream"]) == 34
        assert len(data["upstream"]) == 5
        assert isinstance(data["system_info"], dict)

    def test_all_downstream_have_required_fields(self, soup):
        """Test that all downstream channels have required fields."""
        parser = TechnicolorXB7Parser()
        data = parser.parse(soup)

        for ch in data["downstream"]:
            assert "channel_id" in ch
            assert "frequency" in ch
            assert "power" in ch
            assert "snr" in ch
            assert "modulation" in ch
            assert "lock_status" in ch

    def test_all_upstream_have_required_fields(self, soup):
        """Test that all upstream channels have required fields."""
        parser = TechnicolorXB7Parser()
        data = parser.parse(soup)

        for ch in data["upstream"]:
            assert "channel_id" in ch
            assert "frequency" in ch
            assert "power" in ch
            assert "modulation" in ch
            assert "lock_status" in ch
            # XB7-specific fields
            assert "symbol_rate" in ch
            assert "channel_type" in ch

    def test_system_info_includes_new_fields(self, soup):
        """Test that full parse includes system uptime, software version, and primary channel."""
        parser = TechnicolorXB7Parser()
        data = parser.parse(soup)

        system_info = data["system_info"]
        assert "system_uptime" in system_info
        assert "software_version" in system_info
        assert "last_boot_time" in system_info
        assert "primary_downstream_channel" in system_info
        assert system_info["primary_downstream_channel"] == "10"
