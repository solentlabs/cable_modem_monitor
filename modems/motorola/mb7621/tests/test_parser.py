"""Tests for the Motorola MB7621 parser."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher
from modems.motorola.mb7621.parser import (
    _DEFAULT_RESTART_WINDOW_SECONDS,
    MotorolaMB7621Parser,
)
from tests.fixtures import load_fixture


@pytest.fixture
def login_html():
    """Load login.html fixture."""
    return load_fixture("motorola", "mb7621", "login.html")


@pytest.fixture
def connection_html():
    """Load MotoConnection.asp fixture."""
    return load_fixture("motorola", "mb7621", "MotoConnection.asp")


@pytest.fixture
def home_html():
    """Load MotoHome.asp fixture."""
    return load_fixture("motorola", "mb7621", "MotoHome.asp")


@pytest.fixture
def security_html():
    """Load MotoSecurity.asp fixture."""
    return load_fixture("motorola", "mb7621", "MotoSecurity.asp")


# Note: TestRestart class removed - restart functionality moved to action layer
# See tests/core/actions/test_html.py for restart action tests


class TestParsing:
    """Test data parsing."""

    def test_downstream_channels(self, connection_html, home_html):
        """Test parsing of downstream channels.

        Note: Channel ID is the DOCSIS Channel ID (col 3), not the display row number (col 0).
        From the fixture, the first row has: Channel=1, Channel ID=21
        """
        parser = MotorolaMB7621Parser()
        soup_conn = BeautifulSoup(connection_html, "html.parser")
        soup_home = BeautifulSoup(home_html, "html.parser")

        # Parse connection page
        data = parser.parse(soup_conn)

        # Parse home page for software version
        home_info = parser._parse_system_info(soup_home)
        data["system_info"].update(home_info)

        # Verify downstream channels
        assert "downstream" in data
        assert len(data["downstream"]) > 0
        # First row: Channel=1, Channel ID=21 (col 3 is the actual DOCSIS channel ID)
        assert data["downstream"][0]["channel_id"] == "21"
        assert data["downstream"][0]["frequency"] == 237000000
        assert data["downstream"][0]["power"] == 0.5
        assert data["downstream"][0]["snr"] == 41.4
        assert data["downstream"][0]["corrected"] == 42
        assert data["downstream"][0]["uncorrected"] == 0
        assert data["downstream"][0]["modulation"] == "QAM256"

    def test_upstream_channels(self, connection_html, home_html):
        """Test parsing of upstream channels.

        Note: Channel ID is the DOCSIS Channel ID (col 3), not the display row number (col 0).
        From the fixture, the first row has: Channel=1, Channel ID=2
        """
        parser = MotorolaMB7621Parser()
        soup_conn = BeautifulSoup(connection_html, "html.parser")
        soup_home = BeautifulSoup(home_html, "html.parser")

        # Parse connection page
        data = parser.parse(soup_conn)

        # Parse home page for software version
        home_info = parser._parse_system_info(soup_home)
        data["system_info"].update(home_info)

        # Verify upstream channels
        assert "upstream" in data
        assert len(data["upstream"]) > 0
        # First row: Channel=1, Channel ID=2 (col 3 is the actual DOCSIS channel ID)
        assert data["upstream"][0]["channel_id"] == "2"
        assert data["upstream"][0]["frequency"] == 24000000
        assert data["upstream"][0]["power"] == 36.2
        assert data["upstream"][0]["modulation"] == "ATDMA"

    def test_system_info(self, connection_html, home_html):
        """Test parsing of system info."""
        parser = MotorolaMB7621Parser()
        soup_conn = BeautifulSoup(connection_html, "html.parser")
        soup_home = BeautifulSoup(home_html, "html.parser")

        # Parse connection page
        data = parser.parse(soup_conn)

        # Parse home page for software version
        home_info = parser._parse_system_info(soup_home)
        data["system_info"].update(home_info)

        # Verify system info
        assert "system_info" in data
        assert data["system_info"]["software_version"] == "7621-5.7.1.5"
        assert data["system_info"]["system_uptime"] == "32 days 11h:58m:26s"

    def test_total_row_is_skipped(self, connection_html):
        """Test that the 'Total' summary row in downstream table is skipped.

        The MB7621's MotoConnection.asp page includes a 'Total' row at the end
        of the downstream table showing aggregate corrected/uncorrected errors.
        This row should be silently skipped (not parsed as a channel).
        """
        parser = MotorolaMB7621Parser()
        soup = BeautifulSoup(connection_html, "html.parser")

        # Verify the fixture contains the Total row
        assert "Total" in connection_html, "Fixture should contain Total row"

        # Parse and verify no channel has "Total" as its ID
        data = parser.parse(soup)
        channel_ids = [ch["channel_id"] for ch in data["downstream"]]
        assert "Total" not in channel_ids
        assert all(ch_id.isdigit() for ch_id in channel_ids)


class TestRestartDetection:
    """Test restart detection and zero-value filtering.

    During the restart window (first 5 minutes after boot),
    zero power/SNR values are filtered to None to avoid false readings.
    """

    def test_filters_zero_power_during_restart(self):
        """Test that zero power values are filtered during restart window."""
        html = """
        <html><head><title>Motorola Cable Modem</title></head><body>
        <table class="moto-table-content">
            <tr><td class="moto-param-header-s">Channel ID</td>
                <td class="moto-param-header-s">Lock Status</td>
                <td class="moto-param-header-s">Modulation</td>
                <td class="moto-param-header-s">Channel ID</td>
                <td class="moto-param-header-s">Freq. (MHz)</td>
                <td class="moto-param-header-s">Pwr (dBmV)</td>
                <td class="moto-param-header-s">SNR (dB)</td>
                <td class="moto-param-header-s">Corrected</td>
                <td class="moto-param-header-s">Uncorrected</td></tr>
            <tr><td>1</td><td>Locked</td><td>QAM256</td><td>135</td>
                <td>567.0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
        </table>
        <table class="moto-table-content">
            <tr><td>&nbsp;&nbsp;&nbsp;System Up Time</td>
                <td class='moto-content-value'>0 days 00h:04m:30s</td></tr>
        </table>
        </body></html>
        """

        parser = MotorolaMB7621Parser()
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        # During restart (< 5 min), zero power/SNR should be filtered to None
        assert len(data["downstream"]) == 1
        assert data["downstream"][0]["power"] is None  # Filtered out
        assert data["downstream"][0]["snr"] is None  # Filtered out
        assert data["system_info"]["system_uptime"] == "0 days 00h:04m:30s"

    def test_preserves_nonzero_power_during_restart(self):
        """Test that non-zero power values are preserved during restart window."""
        html = """
        <html><head><title>Motorola Cable Modem</title></head><body>
        <table class="moto-table-content">
            <tr><td class="moto-param-header-s">Channel ID</td>
                <td class="moto-param-header-s">Lock Status</td>
                <td class="moto-param-header-s">Modulation</td>
                <td class="moto-param-header-s">Channel ID</td>
                <td class="moto-param-header-s">Freq. (MHz)</td>
                <td class="moto-param-header-s">Pwr (dBmV)</td>
                <td class="moto-param-header-s">SNR (dB)</td>
                <td class="moto-param-header-s">Corrected</td>
                <td class="moto-param-header-s">Uncorrected</td></tr>
            <tr><td>1</td><td>Locked</td><td>QAM256</td><td>135</td>
                <td>567.0</td><td>3.5</td><td>38.2</td><td>0</td><td>0</td></tr>
        </table>
        <table class="moto-table-content">
            <tr><td>&nbsp;&nbsp;&nbsp;System Up Time</td>
                <td class='moto-content-value'>0 days 00h:02m:15s</td></tr>
        </table>
        </body></html>
        """

        parser = MotorolaMB7621Parser()
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        # During restart, non-zero values should be preserved
        assert len(data["downstream"]) == 1
        assert data["downstream"][0]["power"] == 3.5  # Preserved
        assert data["downstream"][0]["snr"] == 38.2  # Preserved

    def test_no_filtering_after_restart_window(self):
        """Test that zero power values are NOT filtered after restart window."""
        html = """
        <html><head><title>Motorola Cable Modem</title></head><body>
        <table class="moto-table-content">
            <tr><td class="moto-param-header-s">Channel ID</td>
                <td class="moto-param-header-s">Lock Status</td>
                <td class="moto-param-header-s">Modulation</td>
                <td class="moto-param-header-s">Channel ID</td>
                <td class="moto-param-header-s">Freq. (MHz)</td>
                <td class="moto-param-header-s">Pwr (dBmV)</td>
                <td class="moto-param-header-s">SNR (dB)</td>
                <td class="moto-param-header-s">Corrected</td>
                <td class="moto-param-header-s">Uncorrected</td></tr>
            <tr><td>1</td><td>Locked</td><td>QAM256</td><td>135</td>
                <td>567.0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
        </table>
        <table class="moto-table-content">
            <tr><td>&nbsp;&nbsp;&nbsp;System Up Time</td>
                <td class='moto-content-value'>0 days 00h:06m:00s</td></tr>
        </table>
        </body></html>
        """

        parser = MotorolaMB7621Parser()
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        # After restart window (>= 5 min), zero values should be kept
        assert len(data["downstream"]) == 1
        assert data["downstream"][0]["power"] == 0  # NOT filtered
        assert data["downstream"][0]["snr"] == 0  # NOT filtered

    def test_upstream_filtering_during_restart(self):
        """Test that zero power values are filtered for upstream during restart."""
        html = """
        <html><head><title>Motorola Cable Modem</title></head><body>
        <table class="moto-table-content">
            <tr><td class="moto-param-header-s">Channel ID</td>
                <td class="moto-param-header-s">Lock Status</td>
                <td class="moto-param-header-s">US Channel Type</td>
                <td class="moto-param-header-s">Channel ID</td>
                <td class="moto-param-header-s">Symb. Rate (Ksym/sec)</td>
                <td class="moto-param-header-s">Freq. (MHz)</td>
                <td class="moto-param-header-s">Pwr (dBmV)</td></tr>
            <tr><td>1</td><td>Locked</td><td>ATDMA</td><td>2</td>
                <td>5120</td><td>36.0</td><td>0</td></tr>
        </table>
        <table class="moto-table-content">
            <tr><td>&nbsp;&nbsp;&nbsp;System Up Time</td>
                <td class='moto-content-value'>0 days 00h:01m:00s</td></tr>
        </table>
        </body></html>
        """

        parser = MotorolaMB7621Parser()
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        # During restart, zero upstream power should be filtered
        assert len(data["upstream"]) == 1
        assert data["upstream"][0]["power"] is None  # Filtered out

    def test_restart_window_default(self):
        """Test that the restart window default is correctly defined."""
        assert _DEFAULT_RESTART_WINDOW_SECONDS == 300
        assert _DEFAULT_RESTART_WINDOW_SECONDS == 5 * 60  # 5 minutes


class TestAutoDetection:
    """Test modem auto-detection.

    These tests verify that MB7621 is correctly identified during auto-detection.
    If these fail, there's a regression in the discovery logic.
    """

    @pytest.fixture
    def swinfo_html(self):
        """Load MotoSwInfo.asp fixture - contains MB7621 model string."""
        return load_fixture("motorola", "mb7621", "MotoSwInfo.asp")

    def test_detection_with_swinfo_page(self, swinfo_html):
        """MB7621 should be detected when MotoSwInfo.asp is provided via HintMatcher.

        This is the page that contains the MB7621 model string.
        """
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(swinfo_html)
        assert any(m.parser_name == "MotorolaMB7621Parser" for m in matches)

    def test_detection_from_login_page(self, login_html):
        """MB7621 should match on login page via HintMatcher.

        The login page has "Motorola Cable Modem" + "/goform/login" which
        uniquely identifies MB7621 (MB8611 uses HNAP, not form auth).
        This allows detection even when user hasn't authenticated yet.
        """
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(login_html)
        assert any(m.parser_name == "MotorolaMB7621Parser" for m in matches)

    def test_swinfo_page_requires_auth(self):
        """MotoSwInfo.asp requires authentication.

        MB7621 redirects all content pages to login when not authenticated.
        Detection happens via authenticated session, not anonymous probing.
        """
        from custom_components.cable_modem_monitor.modem_config.adapter import get_url_patterns_for_parser

        url_patterns = get_url_patterns_for_parser("MotorolaMB7621Parser")
        assert url_patterns is not None, "MB7621 should have URL patterns in modem.yaml"

        # Find the MotoSwInfo.asp pattern
        swinfo_patterns = [p for p in url_patterns if p["path"] == "/MotoSwInfo.asp"]
        assert len(swinfo_patterns) == 1, "MB7621 should have MotoSwInfo.asp URL pattern"
        assert swinfo_patterns[0].get("auth_required", True) is True

    def test_no_public_content_pages(self):
        """MB7621 has no public content pages.

        Only static assets (CSS, images) are accessible without auth.
        This means detection requires authenticated session.
        """
        from custom_components.cable_modem_monitor.modem_config.adapter import get_url_patterns_for_parser

        url_patterns = get_url_patterns_for_parser("MotorolaMB7621Parser")
        assert url_patterns is not None

        public_patterns = [p for p in url_patterns if not p.get("auth_required", True)]
        # Public patterns are only static assets, not content pages
        for p in public_patterns:
            path = str(p["path"])
            assert path.endswith((".css", ".jpg", ".png")) or path == "/", f"Unexpected public content page: {path}"

    def test_authenticated_detection_with_swinfo(self, swinfo_html):
        """MB7621 is detected via authenticated access to MotoSwInfo.asp using HintMatcher.

        After auth discovery succeeds, detection uses the authenticated
        session to fetch content pages and identify the modem.
        """
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(swinfo_html)
        assert any(m.parser_name == "MotorolaMB7621Parser" for m in matches)
