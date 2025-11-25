"""Tests for the Netgear CM600 parser.

NOTE: Parser implementation pending DocsisStatus.asp HTML capture.
The CM600 uses /DocsisStatus.asp for DOCSIS channel data, which was
not captured in initial diagnostics due to a bug (now fixed).

Current fixtures available:
- DashBoard.asp: Dashboard page
- DocsisOffline.asp: Offline error page
- EventLog.asp: Event log page
- GPL_rev1.htm: GPL license
- index.html: Main page
- RouterStatus.asp: Router/wireless status
- SetPassword.asp: Password change page

Missing fixture needed for parser:
- DocsisStatus.asp: DOCSIS channel data (downstream/upstream)

Related: Issue ***REMOVED***3 (Netgear CM600 - Login Doesn't Work)
"""

from __future__ import annotations

import os

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.netgear.cm600 import NetgearCM600Parser


@pytest.fixture
def cm600_index_html():
    """Load CM600 index.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm600", "index.html")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def cm600_dashboard_html():
    """Load CM600 DashBoard.asp fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm600", "DashBoard.asp")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def cm600_router_status_html():
    """Load CM600 RouterStatus.asp fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm600", "RouterStatus.asp")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def cm600_docsis_status_html():
    """Load CM600 DocsisStatus.asp fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm600", "DocsisStatus.asp")
    with open(fixture_path) as f:
        return f.read()


def test_fixtures_exist():
    """Verify all captured CM600 fixtures are present."""
    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures", "cm600")

    expected_files = [
        "DashBoard.asp",
        "DocsisOffline.asp",
        "DocsisStatus.asp",
        "EventLog.asp",
        "GPL_rev1.htm",
        "index.html",
        "RouterStatus.asp",
        "SetPassword.asp",
    ]

    for filename in expected_files:
        filepath = os.path.join(fixtures_dir, filename)
        assert os.path.exists(filepath), f"Missing fixture: {filename}"


def test_parser_detection(cm600_index_html):
    """Test that the Netgear CM600 parser detects the modem."""
    soup = BeautifulSoup(cm600_index_html, "html.parser")
    assert NetgearCM600Parser.can_parse(soup, "http://192.168.100.1/", cm600_index_html)


def test_parser_system_info(cm600_router_status_html):
    """Test parsing of Netgear CM600 system info from RouterStatus.asp."""
    parser = NetgearCM600Parser()

    ***REMOVED*** Parse just the RouterStatus page using the internal method
    soup = BeautifulSoup(cm600_router_status_html, "html.parser")
    system_info = parser._parse_router_system_info(soup)

    ***REMOVED*** Check that we extracted firmware version
    assert "software_version" in system_info
    assert system_info["software_version"] == "V1.01.22"

    ***REMOVED*** Check hardware version
    assert "hardware_version" in system_info
    assert system_info["hardware_version"] == "1.01B"


def test_calculate_boot_time():
    """Test boot time calculation from uptime string."""
    from datetime import datetime, timedelta

    parser = NetgearCM600Parser()

    ***REMOVED*** Test with typical uptime format: "0d 1h 23m 45s"
    boot_time_str = parser._calculate_boot_time("0d 1h 23m 45s")
    assert boot_time_str is not None

    ***REMOVED*** Parse the ISO formatted boot time
    boot_time = datetime.fromisoformat(boot_time_str)
    ***REMOVED*** Boot time should be in the past
    assert boot_time < datetime.now()

    ***REMOVED*** Calculate expected boot time (within 1 second tolerance)
    expected_uptime = timedelta(days=0, hours=1, minutes=23, seconds=45)
    expected_boot = datetime.now() - expected_uptime
    ***REMOVED*** Allow 2 second tolerance for test execution time
    assert abs((boot_time - expected_boot).total_seconds()) < 2

    ***REMOVED*** Test with longer uptime
    boot_time_str = parser._calculate_boot_time("5d 12h 30m 15s")
    assert boot_time_str is not None
    boot_time = datetime.fromisoformat(boot_time_str)
    expected_uptime = timedelta(days=5, hours=12, minutes=30, seconds=15)
    expected_boot = datetime.now() - expected_uptime
    assert abs((boot_time - expected_boot).total_seconds()) < 2

    ***REMOVED*** Test with invalid uptime string
    boot_time_str = parser._calculate_boot_time("invalid")
    assert boot_time_str is None

    ***REMOVED*** Test with empty string
    boot_time_str = parser._calculate_boot_time("")
    assert boot_time_str is None


def test_parsing_downstream(cm600_docsis_status_html):
    """Test parsing of Netgear CM600 downstream data."""
    parser = NetgearCM600Parser()
    soup = BeautifulSoup(cm600_docsis_status_html, "html.parser")
    data = parser.parse(soup)

    ***REMOVED*** Verify downstream channels were parsed
    assert "downstream" in data
    assert len(data["downstream"]) == 24  ***REMOVED*** CM600 supports 24 downstream channels

    ***REMOVED*** Check first downstream channel (from HTML table)
    first_ds = data["downstream"][0]
    assert first_ds["channel_id"] == "28"
    assert first_ds["frequency"] == 573000000  ***REMOVED*** 573 MHz in Hz
    assert first_ds["power"] == 6.6  ***REMOVED*** dBmV
    assert first_ds["snr"] == 40.9  ***REMOVED*** dB
    assert first_ds["modulation"] == "QAM256"
    assert first_ds["corrected"] == 22
    assert first_ds["uncorrected"] == 0

    ***REMOVED*** Check second channel to verify parsing continues correctly
    second_ds = data["downstream"][1]
    assert second_ds["channel_id"] == "21"
    assert second_ds["frequency"] == 525000000  ***REMOVED*** 525 MHz
    assert second_ds["power"] == 6.0


def test_parsing_upstream(cm600_docsis_status_html):
    """Test parsing of Netgear CM600 upstream data."""
    parser = NetgearCM600Parser()
    soup = BeautifulSoup(cm600_docsis_status_html, "html.parser")
    data = parser.parse(soup)

    ***REMOVED*** Verify upstream channels were parsed
    assert "upstream" in data
    assert len(data["upstream"]) == 6  ***REMOVED*** CM600 has 6 locked upstream channels in this fixture

    ***REMOVED*** Check first upstream channel (from HTML table)
    first_us = data["upstream"][0]
    assert first_us["channel_id"] == "5"
    assert first_us["frequency"] == 40400000  ***REMOVED*** 40.4 MHz in Hz
    assert first_us["power"] == 42.5  ***REMOVED*** dBmV
    assert first_us["channel_type"] == "ATDMA"

    ***REMOVED*** Check second channel to verify parsing
    second_us = data["upstream"][1]
    assert second_us["channel_id"] == "2"
    assert second_us["frequency"] == 22800000  ***REMOVED*** 22.8 MHz
    assert second_us["power"] == 42.3


class TestAuthentication:
    """Test HTTP Basic Authentication for CM600."""

    def test_has_basic_auth_config(self):
        """Test that parser has HTTP Basic Auth configuration."""
        from custom_components.cable_modem_monitor.core.auth_config import BasicAuthConfig
        from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType

        parser = NetgearCM600Parser()

        assert parser.auth_config is not None
        assert isinstance(parser.auth_config, BasicAuthConfig)
        assert parser.auth_config.strategy == AuthStrategyType.BASIC_HTTP

    def test_url_patterns_auth_required(self):
        """Test that protected URLs require authentication."""
        parser = NetgearCM600Parser()

        ***REMOVED*** DocsisStatus.asp should require auth
        docsis_pattern = next(p for p in parser.url_patterns if p["path"] == "/DocsisStatus.asp")
        assert docsis_pattern["auth_required"] is True
        assert docsis_pattern["auth_method"] == "basic"

        ***REMOVED*** DashBoard.asp should require auth
        dashboard_pattern = next(p for p in parser.url_patterns if p["path"] == "/DashBoard.asp")
        assert dashboard_pattern["auth_required"] is True

        ***REMOVED*** RouterStatus.asp should require auth
        router_pattern = next(p for p in parser.url_patterns if p["path"] == "/RouterStatus.asp")
        assert router_pattern["auth_required"] is True

        ***REMOVED*** Index page should NOT require auth
        index_pattern = next(p for p in parser.url_patterns if p["path"] == "/")
        assert index_pattern["auth_required"] is False

    def test_login_configures_basic_auth(self):
        """Test that login() properly configures HTTP Basic Auth."""
        from unittest.mock import Mock, patch

        parser = NetgearCM600Parser()
        mock_session = Mock()
        base_url = "http://192.168.100.1"

        ***REMOVED*** Mock AuthFactory
        auth_path = "custom_components.cable_modem_monitor.core.authentication.AuthFactory"
        with patch(auth_path) as mock_factory:
            mock_strategy = Mock()
            mock_strategy.login.return_value = (True, None)
            mock_factory.get_strategy.return_value = mock_strategy

            success = parser.login(mock_session, base_url, "admin", "password")

            assert success is True
            mock_strategy.login.assert_called_once_with(mock_session, base_url, "admin", "password", parser.auth_config)

    def test_login_without_credentials(self):
        """Test login behavior when no credentials provided."""
        from unittest.mock import Mock, patch

        parser = NetgearCM600Parser()
        mock_session = Mock()
        base_url = "http://192.168.100.1"

        ***REMOVED*** Mock AuthFactory - Basic Auth should skip when no credentials
        auth_path = "custom_components.cable_modem_monitor.core.authentication.AuthFactory"
        with patch(auth_path) as mock_factory:
            mock_strategy = Mock()
            mock_strategy.login.return_value = (True, None)  ***REMOVED*** Skip login, return success
            mock_factory.get_strategy.return_value = mock_strategy

            success = parser.login(mock_session, base_url, None, None)

            assert success is True


class TestEdgeCases:
    """Test edge cases and error handling for CM600."""

    def test_empty_downstream_data(self):
        """Test parsing when no downstream channels are present."""
        parser = NetgearCM600Parser()
        ***REMOVED*** Create HTML without downstream channel data
        html = "<html><head><title>CM600</title></head><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}

    def test_malformed_downstream_entry(self):
        """Test handling of malformed downstream channel data."""
        parser = NetgearCM600Parser()
        ***REMOVED*** Create HTML with malformed table row (missing cells)
        html = """
        <html>
        <table id="dsTable">
            <tr><th>Channel</th><th>Lock Status</th></tr>
            <tr><td>1</td><td>Locked</td></tr>
        </table>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        ***REMOVED*** Should handle gracefully and skip malformed entries
        assert "downstream" in data
        assert len(data["downstream"]) == 0  ***REMOVED*** Missing cells, should skip

    def test_malformed_upstream_entry(self):
        """Test handling of malformed upstream channel data."""
        parser = NetgearCM600Parser()
        html = """
        <html>
        <table id="usTable">
            <tr><th>Channel</th><th>Lock Status</th></tr>
            <tr><td>1</td><td>Locked</td><td>ATDMA</td></tr>
        </table>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        assert "upstream" in data
        assert len(data["upstream"]) == 0  ***REMOVED*** Incomplete row, should skip

    def test_invalid_frequency_values(self):
        """Test handling of invalid frequency values."""
        parser = NetgearCM600Parser()
        html = """
        <html>
        <table id="dsTable">
            <tr>
                <th>Channel</th><th>Lock</th><th>Mod</th><th>ID</th><th>Freq</th>
                <th>Pwr</th><th>SNR</th><th>Corr</th><th>Uncorr</th>
            </tr>
            <tr>
                <td>1</td><td>Locked</td><td>QAM256</td><td>1</td>
                <td>invalid Hz</td><td>-5.0</td><td>41.9</td><td>0</td><td>0</td>
            </tr>
        </table>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        ***REMOVED*** Parser should handle ValueError and skip invalid entries
        assert "downstream" in data
        assert len(data["downstream"]) == 0  ***REMOVED*** Invalid frequency, should skip

    def test_missing_tables(self):
        """Test parsing when HTML tables are not present."""
        parser = NetgearCM600Parser()
        html = "<html><body><p>No tables here</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        ***REMOVED*** Should return empty data structures without crashing
        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}


class TestRestart:
    """Test modem restart functionality."""

    def test_restart_method_exists(self):
        """Test that CM600 parser has restart method."""
        parser = NetgearCM600Parser()
        assert hasattr(parser, "restart")
        assert callable(parser.restart)

    def test_restart_sends_correct_request(self):
        """Test that restart sends correct POST request."""
        from unittest.mock import Mock

        parser = NetgearCM600Parser()
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        base_url = "http://192.168.100.1"
        success = parser.restart(mock_session, base_url)

        assert success is True
        mock_session.post.assert_called_once_with(
            "http://192.168.100.1/goform/RouterStatus",
            data={"RsAction": "2"},
            timeout=10,
        )

    def test_restart_handles_failure(self):
        """Test that restart handles HTTP errors gracefully."""
        from unittest.mock import Mock

        parser = NetgearCM600Parser()
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_session.post.return_value = mock_response

        base_url = "http://192.168.100.1"
        success = parser.restart(mock_session, base_url)

        assert success is False


class TestMetadata:
    """Test parser metadata."""

    def test_name(self):
        """Test parser name."""
        parser = NetgearCM600Parser()
        assert parser.name == "Netgear CM600"

    def test_manufacturer(self):
        """Test parser manufacturer."""
        parser = NetgearCM600Parser()
        assert parser.manufacturer == "Netgear"

    def test_models(self):
        """Test parser supported models."""
        parser = NetgearCM600Parser()
        assert "CM600" in parser.models

    def test_priority(self):
        """Test parser priority."""
        parser = NetgearCM600Parser()
        assert parser.priority == 50  ***REMOVED*** Standard priority
