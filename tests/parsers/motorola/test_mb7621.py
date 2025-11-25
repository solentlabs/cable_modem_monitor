"""Tests for the Motorola MB7621 parser."""

from __future__ import annotations

import os
from unittest.mock import Mock

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.motorola.generic import RESTART_WINDOW_SECONDS
from custom_components.cable_modem_monitor.parsers.motorola.mb7621 import MotorolaMB7621Parser


@pytest.fixture
def login_html():
    """Load Login.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "mb7621", "Login.html")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def connection_html():
    """Load MotoConnection.asp fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "mb7621", "MotoConnection.asp")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def home_html():
    """Load MotoHome.asp fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "mb7621", "MotoHome.asp")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def security_html():
    """Load MotoSecurity.asp fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "mb7621", "MotoSecurity.asp")
    with open(fixture_path) as f:
        return f.read()


class TestRestart:
    """Test modem restart functionality."""

    def test_success(self, security_html):
        """Test the restart functionality."""
        parser = MotorolaMB7621Parser()
        session = Mock()
        base_url = "http://192.168.100.1"

        ***REMOVED*** Mock the GET request to MotoSecurity.asp
        mock_security_response = Mock()
        mock_security_response.status_code = 200
        mock_security_response.text = security_html
        session.get.return_value = mock_security_response

        ***REMOVED*** Mock the POST request for restart
        mock_restart_response = Mock()
        mock_restart_response.status_code = 200
        mock_restart_response.text = ""
        session.post.return_value = mock_restart_response

        ***REMOVED*** Test successful restart
        result = parser.restart(session, base_url)
        assert result is True

        session.get.assert_called_once_with(f"{base_url}/MotoSecurity.asp", timeout=10)
        session.post.assert_called_once_with(
            f"{base_url}/goform/MotoSecurity",
            data={
                "UserId": "",
                "OldPassword": "",
                "NewUserId": "",
                "Password": "",
                "PasswordReEnter": "",
                "MotoSecurityAction": "1",
            },
            timeout=10,
        )

    def test_with_connection_reset(self, security_html):
        """Test restart with ConnectionResetError (expected behavior during reboot)."""
        parser = MotorolaMB7621Parser()
        session = Mock()
        base_url = "http://192.168.100.1"

        ***REMOVED*** Mock the GET request to MotoSecurity.asp
        mock_security_response = Mock()
        mock_security_response.status_code = 200
        mock_security_response.text = security_html
        session.get.return_value = mock_security_response

        ***REMOVED*** Mock the POST request raising ConnectionResetError
        session.post.side_effect = ConnectionResetError("Connection reset by peer")

        result = parser.restart(session, base_url)
        assert result is True

        session.get.assert_called_once_with(f"{base_url}/MotoSecurity.asp", timeout=10)
        session.post.assert_called_once()


class TestParsing:
    """Test data parsing."""

    def test_downstream_channels(self, connection_html, home_html):
        """Test parsing of downstream channels."""
        parser = MotorolaMB7621Parser()
        soup_conn = BeautifulSoup(connection_html, "html.parser")
        soup_home = BeautifulSoup(home_html, "html.parser")

        ***REMOVED*** Parse connection page
        data = parser.parse(soup_conn)

        ***REMOVED*** Parse home page for software version
        home_info = parser._parse_system_info(soup_home)
        data["system_info"].update(home_info)

        ***REMOVED*** Verify downstream channels
        assert "downstream" in data
        assert len(data["downstream"]) > 0
        assert data["downstream"][0]["channel_id"] == "1"
        assert data["downstream"][0]["frequency"] == 237000000
        assert data["downstream"][0]["power"] == 0.5
        assert data["downstream"][0]["snr"] == 41.4
        assert data["downstream"][0]["corrected"] == 42
        assert data["downstream"][0]["uncorrected"] == 0
        assert data["downstream"][0]["modulation"] == "QAM256"

    def test_upstream_channels(self, connection_html, home_html):
        """Test parsing of upstream channels."""
        parser = MotorolaMB7621Parser()
        soup_conn = BeautifulSoup(connection_html, "html.parser")
        soup_home = BeautifulSoup(home_html, "html.parser")

        ***REMOVED*** Parse connection page
        data = parser.parse(soup_conn)

        ***REMOVED*** Parse home page for software version
        home_info = parser._parse_system_info(soup_home)
        data["system_info"].update(home_info)

        ***REMOVED*** Verify upstream channels
        assert "upstream" in data
        assert len(data["upstream"]) > 0
        assert data["upstream"][0]["channel_id"] == "1"
        assert data["upstream"][0]["frequency"] == 24000000
        assert data["upstream"][0]["power"] == 36.2
        assert data["upstream"][0]["modulation"] == "ATDMA"

    def test_system_info(self, connection_html, home_html):
        """Test parsing of system info."""
        parser = MotorolaMB7621Parser()
        soup_conn = BeautifulSoup(connection_html, "html.parser")
        soup_home = BeautifulSoup(home_html, "html.parser")

        ***REMOVED*** Parse connection page
        data = parser.parse(soup_conn)

        ***REMOVED*** Parse home page for software version
        home_info = parser._parse_system_info(soup_home)
        data["system_info"].update(home_info)

        ***REMOVED*** Verify system info
        assert "system_info" in data
        assert data["system_info"]["software_version"] == "7621-5.7.1.5"
        assert data["system_info"]["system_uptime"] == "32 days 11h:58m:26s"


class TestRestartDetection:
    """Test restart detection and zero-value filtering.

    These tests verify the base Motorola parsing behavior inherited from
    MotorolaGenericParser. During the restart window (first 5 minutes after boot),
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

        ***REMOVED*** During restart (< 5 min), zero power/SNR should be filtered to None
        assert len(data["downstream"]) == 1
        assert data["downstream"][0]["power"] is None  ***REMOVED*** Filtered out
        assert data["downstream"][0]["snr"] is None  ***REMOVED*** Filtered out
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

        ***REMOVED*** During restart, non-zero values should be preserved
        assert len(data["downstream"]) == 1
        assert data["downstream"][0]["power"] == 3.5  ***REMOVED*** Preserved
        assert data["downstream"][0]["snr"] == 38.2  ***REMOVED*** Preserved

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

        ***REMOVED*** After restart window (>= 5 min), zero values should be kept
        assert len(data["downstream"]) == 1
        assert data["downstream"][0]["power"] == 0  ***REMOVED*** NOT filtered
        assert data["downstream"][0]["snr"] == 0  ***REMOVED*** NOT filtered

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

        ***REMOVED*** During restart, zero upstream power should be filtered
        assert len(data["upstream"]) == 1
        assert data["upstream"][0]["power"] is None  ***REMOVED*** Filtered out

    def test_restart_window_constant(self):
        """Test that the restart window constant is correctly defined."""
        assert RESTART_WINDOW_SECONDS == 300
        assert RESTART_WINDOW_SECONDS == 5 * 60  ***REMOVED*** 5 minutes
