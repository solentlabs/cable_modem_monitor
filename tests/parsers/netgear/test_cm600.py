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

Related: Issue #3 (Netgear CM600 - Login Doesn't Work)
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
    soup = BeautifulSoup(cm600_router_status_html, "html.parser")
    data = parser.parse(soup)

    # Verify system info was extracted
    assert "system_info" in data
    system_info = data["system_info"]

    # Check that we extracted firmware version
    assert "software_version" in system_info
    assert system_info["software_version"] == "V1.01.22"

    # Check hardware version if available
    if "hardware_version" in system_info:
        assert system_info["hardware_version"] is not None


def test_parsing_downstream(cm600_docsis_status_html):
    """Test parsing of Netgear CM600 downstream data."""
    parser = NetgearCM600Parser()
    soup = BeautifulSoup(cm600_docsis_status_html, "html.parser")
    data = parser.parse(soup)

    # Verify downstream channels were parsed
    assert "downstream" in data
    assert len(data["downstream"]) == 8  # CM600 has 8 downstream channels in this fixture

    # Check first downstream channel
    first_ds = data["downstream"][0]
    assert first_ds["channel_id"] == "1"
    assert first_ds["frequency"] == 141000000  # 141 MHz in Hz
    assert first_ds["power"] == -5.0  # dBmV
    assert first_ds["snr"] == 41.9  # dB
    assert first_ds["modulation"] == "QAM256"
    assert first_ds["corrected"] == 0
    assert first_ds["uncorrected"] == 0

    # Check second channel to verify parsing continues correctly
    second_ds = data["downstream"][1]
    assert second_ds["channel_id"] == "2"
    assert second_ds["frequency"] == 147000000  # 147 MHz
    assert second_ds["power"] == -4.7


def test_parsing_upstream(cm600_docsis_status_html):
    """Test parsing of Netgear CM600 upstream data."""
    parser = NetgearCM600Parser()
    soup = BeautifulSoup(cm600_docsis_status_html, "html.parser")
    data = parser.parse(soup)

    # Verify upstream channels were parsed
    assert "upstream" in data
    assert len(data["upstream"]) == 4  # CM600 has 4 upstream channels in this fixture

    # Check first upstream channel
    first_us = data["upstream"][0]
    assert first_us["channel_id"] == "1"
    assert first_us["frequency"] == 13400000  # 13.4 MHz in Hz
    assert first_us["power"] == 50.0  # dBmV
    assert first_us["channel_type"] == "ATDMA"

    # Check second channel to verify parsing
    second_us = data["upstream"][1]
    assert second_us["channel_id"] == "2"
    assert second_us["frequency"] == 16700000  # 16.7 MHz
    assert second_us["power"] == 50.0


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

        # DocsisStatus.asp should require auth
        docsis_pattern = next(p for p in parser.url_patterns if p["path"] == "/DocsisStatus.asp")
        assert docsis_pattern["auth_required"] is True
        assert docsis_pattern["auth_method"] == "basic"

        # DashBoard.asp should require auth
        dashboard_pattern = next(p for p in parser.url_patterns if p["path"] == "/DashBoard.asp")
        assert dashboard_pattern["auth_required"] is True

        # RouterStatus.asp should require auth
        router_pattern = next(p for p in parser.url_patterns if p["path"] == "/RouterStatus.asp")
        assert router_pattern["auth_required"] is True

        # Index page should NOT require auth
        index_pattern = next(p for p in parser.url_patterns if p["path"] == "/")
        assert index_pattern["auth_required"] is False

    def test_login_configures_basic_auth(self):
        """Test that login() properly configures HTTP Basic Auth."""
        from unittest.mock import Mock, patch

        parser = NetgearCM600Parser()
        mock_session = Mock()
        base_url = "http://192.168.100.1"

        # Mock AuthFactory
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

        # Mock AuthFactory - Basic Auth should skip when no credentials
        auth_path = "custom_components.cable_modem_monitor.core.authentication.AuthFactory"
        with patch(auth_path) as mock_factory:
            mock_strategy = Mock()
            mock_strategy.login.return_value = (True, None)  # Skip login, return success
            mock_factory.get_strategy.return_value = mock_strategy

            success = parser.login(mock_session, base_url, None, None)

            assert success is True


class TestEdgeCases:
    """Test edge cases and error handling for CM600."""

    def test_empty_downstream_data(self):
        """Test parsing when no downstream channels are present."""
        parser = NetgearCM600Parser()
        # Create HTML without downstream channel data
        html = "<html><head><title>CM600</title></head><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}

    def test_malformed_downstream_entry(self):
        """Test handling of malformed downstream channel data."""
        parser = NetgearCM600Parser()
        # Create HTML with malformed JavaScript (missing fields)
        html = """
        <html><script>
        function InitDsTableTagValue() {
            var tagValueList = '2|1|Locked|QAM256|incomplete';  // Missing fields
            return tagValueList.split("|");
        }
        </script></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        # Should handle gracefully and return empty or partial data
        assert "downstream" in data
        # Parser should skip malformed entries

    def test_malformed_upstream_entry(self):
        """Test handling of malformed upstream channel data."""
        parser = NetgearCM600Parser()
        html = """
        <html><script>
        function InitUsTableTagValue() {
            var tagValueList = '1|1|Locked';  // Incomplete data
            return tagValueList.split("|");
        }
        </script></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        assert "upstream" in data
        assert len(data["upstream"]) == 0  # Should skip malformed entry

    def test_invalid_frequency_values(self):
        """Test handling of invalid frequency values."""
        parser = NetgearCM600Parser()
        html = """
        <html><script>
        function InitDsTableTagValue() {
            var tagValueList = '1|1|Locked|QAM256|1|invalid_freq| Hz|-5.0|41.9|0|0';
            return tagValueList.split("|");
        }
        </script></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        # Parser should handle ValueError and skip invalid entries
        assert "downstream" in data

    def test_missing_javascript_functions(self):
        """Test parsing when JavaScript functions are not present."""
        parser = NetgearCM600Parser()
        html = "<html><body><p>No JavaScript here</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        # Should return empty data structures without crashing
        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}


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
        assert parser.priority == 50  # Standard priority
