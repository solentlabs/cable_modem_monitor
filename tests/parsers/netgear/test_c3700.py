"""Tests for the Netgear C3700 parser.

NOTE: The C3700 is a combo modem/router device using .htm extensions.

The diagnostics capture shows modem was offline (DocsisOffline.htm displayed).
Test fixtures capture the structure, but channel data requires the modem to be
online to access DocsisStatus.htm.

Model: C3700-100NAS
Firmware: V1.0.0.42_1.0.11
Hardware: V2.02.18

All captured fixtures (21 pages total):
- root.html, index.htm, document.htm, Logs.htm, UPnPMedia.htm
- BackupSettings.htm, DashBoard.htm, Schedule.htm, UPnP.htm
- BlockSites.htm, GuestNetwork.htm, WANSetup.htm, Diagnostics.htm
- AccessControl.htm, eventLog.htm, DynamicDNS.htm, WirelessSettings.htm
- LANSetup.htm, SpeedTest.htm, DocsisOffline.htm, AddWPSClient_TOP.htm

Missing fixture needed for full channel parsing tests:
- DocsisStatus.htm: DOCSIS channel data (only available when modem is online)
"""

from __future__ import annotations

import os

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.netgear.c3700 import NetgearC3700Parser


@pytest.fixture
def c3700_index_html():
    """Load C3700 index.htm fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "c3700", "index.htm")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def c3700_dashboard_html():
    """Load C3700 DashBoard.htm fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "c3700", "DashBoard.htm")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def c3700_docsis_offline_html():
    """Load C3700 DocsisOffline.htm fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "c3700", "DocsisOffline.htm")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def c3700_docsis_status_html():
    """Load C3700 DocsisStatus.htm fixture.

    NOTE: This fixture will be created when we have data from an online modem.
    """
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "c3700", "DocsisStatus.htm")
    if not os.path.exists(fixture_path):
        pytest.skip("DocsisStatus.htm fixture not yet available (modem was offline during capture)")
    with open(fixture_path) as f:
        return f.read()


def test_parser_detection(c3700_index_html):
    """Test that the Netgear C3700 parser detects the modem."""
    soup = BeautifulSoup(c3700_index_html, "html.parser")
    assert NetgearC3700Parser.can_parse(soup, "http://192.168.100.1/index.htm", c3700_index_html)


def test_parser_detection_from_title():
    """Test C3700 detection from page title."""
    html = """
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
    <html><head><title>NETGEAR Gateway C3700-100NAS</title></head>
    <body></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert NetgearC3700Parser.can_parse(soup, "http://192.168.100.1/", html)


def test_parser_detection_from_meta():
    """Test C3700 detection from meta description."""
    html = """
    <html>
    <head>
        <META content='C3700-100NAS' name="description">
        <title>NETGEAR Gateway</title>
    </head>
    <body></body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert NetgearC3700Parser.can_parse(soup, "http://192.168.100.1/", html)


def test_parser_detection_from_content():
    """Test C3700 detection from page content."""
    html = """
    <html>
    <head><title>NETGEAR Gateway</title></head>
    <body>
        <p>Welcome to your C3700 gateway</p>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert NetgearC3700Parser.can_parse(soup, "http://192.168.100.1/", html)


def test_parser_does_not_match_other_models():
    """Test that C3700 parser doesn't match other Netgear models."""
    # CM600 page should not match C3700 parser
    html = """
    <html>
    <head><title>NETGEAR Gateway CM600-100NAS</title></head>
    <body></body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert not NetgearC3700Parser.can_parse(soup, "http://192.168.100.1/", html)


def test_parsing_downstream(c3700_docsis_status_html):
    """Test parsing of Netgear C3700 downstream data.

    Requires DocsisStatus.htm fixture with online modem data.
    """
    parser = NetgearC3700Parser()
    soup = BeautifulSoup(c3700_docsis_status_html, "html.parser")
    data = parser.parse(soup)

    # Verify downstream channels were parsed
    assert "downstream" in data
    assert len(data["downstream"]) > 0

    # Check first downstream channel structure
    first_ds = data["downstream"][0]
    assert "channel_id" in first_ds
    assert "frequency" in first_ds
    assert "power" in first_ds
    assert "snr" in first_ds
    assert "modulation" in first_ds
    assert "corrected" in first_ds
    assert "uncorrected" in first_ds


def test_parsing_upstream(c3700_docsis_status_html):
    """Test parsing of Netgear C3700 upstream data.

    Requires DocsisStatus.htm fixture with online modem data.
    """
    parser = NetgearC3700Parser()
    soup = BeautifulSoup(c3700_docsis_status_html, "html.parser")
    data = parser.parse(soup)

    # Verify upstream channels were parsed
    assert "upstream" in data
    assert len(data["upstream"]) > 0

    # Check first upstream channel structure
    first_us = data["upstream"][0]
    assert "channel_id" in first_us
    assert "frequency" in first_us
    assert "power" in first_us
    assert "channel_type" in first_us


def test_multi_page_parsing_with_session(c3700_index_html, c3700_docsis_status_html):
    """Test that parser fetches DocsisStatus.htm when session and base_url are provided.

    This tests the multi-page parsing fix where the parser should fetch
    DocsisStatus.htm to get channel data, even when initially given a different page.
    """
    from unittest.mock import Mock

    parser = NetgearC3700Parser()

    # Create mock session that returns DocsisStatus.htm when requested
    mock_session = Mock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = c3700_docsis_status_html
    mock_session.get.return_value = mock_response

    # Parse with index.htm soup but provide session and base_url
    # Parser should fetch DocsisStatus.htm and extract channel data
    index_soup = BeautifulSoup(c3700_index_html, "html.parser")
    data = parser.parse(index_soup, session=mock_session, base_url="http://192.168.100.1")

    # Verify DocsisStatus.htm was requested
    mock_session.get.assert_called_once_with("http://192.168.100.1/DocsisStatus.htm", timeout=10)

    # Verify channel data was parsed from DocsisStatus.htm (not from index.htm)
    assert len(data["downstream"]) > 0
    assert len(data["upstream"]) > 0


def test_multi_page_parsing_fallback_on_error(c3700_index_html):
    """Test that parser gracefully handles errors when fetching DocsisStatus.htm."""
    from unittest.mock import Mock

    parser = NetgearC3700Parser()

    # Create mock session that raises an exception
    mock_session = Mock()
    mock_session.get.side_effect = Exception("Connection error")

    # Parse should not crash, just return empty data
    index_soup = BeautifulSoup(c3700_index_html, "html.parser")
    data = parser.parse(index_soup, session=mock_session, base_url="http://192.168.100.1")

    # Should return empty channel data without crashing
    assert data["downstream"] == []
    assert data["upstream"] == []


def test_empty_data_when_offline():
    """Test that parser returns empty data structures when modem is offline."""
    parser = NetgearC3700Parser()
    # Simulate offline page with no channel data
    html = """
    <html>
    <head><title>NETGEAR Gateway C3700-100NAS</title></head>
    <body>
        <h1>Failure</h1>
        <p>Your modem is offline.</p>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    data = parser.parse(soup)

    # Should return empty structures without crashing
    assert data["downstream"] == []
    assert data["upstream"] == []
    assert data["system_info"] == {}


class TestAuthentication:
    """Test HTTP Basic Authentication for C3700."""

    def test_has_basic_auth_config(self):
        """Test that parser has HTTP Basic Auth configuration."""
        from custom_components.cable_modem_monitor.core.auth_config import BasicAuthConfig
        from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType

        parser = NetgearC3700Parser()

        assert parser.auth_config is not None
        assert isinstance(parser.auth_config, BasicAuthConfig)
        assert parser.auth_config.strategy == AuthStrategyType.BASIC_HTTP

    def test_url_patterns_auth_required(self):
        """Test that protected URLs require authentication."""
        parser = NetgearC3700Parser()

        # DocsisStatus.htm should require auth
        docsis_pattern = next(p for p in parser.url_patterns if p["path"] == "/DocsisStatus.htm")
        assert docsis_pattern["auth_required"] is True
        assert docsis_pattern["auth_method"] == "basic"

        # DashBoard.htm should require auth
        dashboard_pattern = next(p for p in parser.url_patterns if p["path"] == "/DashBoard.htm")
        assert dashboard_pattern["auth_required"] is True

        # RouterStatus.htm should require auth
        router_pattern = next(p for p in parser.url_patterns if p["path"] == "/RouterStatus.htm")
        assert router_pattern["auth_required"] is True

        # Index page should NOT require auth
        index_pattern = next(p for p in parser.url_patterns if p["path"] == "/")
        assert index_pattern["auth_required"] is False

    def test_login_configures_basic_auth(self):
        """Test that login() properly configures HTTP Basic Auth."""
        from unittest.mock import Mock, patch

        parser = NetgearC3700Parser()
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


class TestEdgeCases:
    """Test edge cases and error handling for C3700."""

    def test_empty_downstream_data(self):
        """Test parsing when no downstream channels are present."""
        parser = NetgearC3700Parser()
        html = "<html><head><title>C3700</title></head><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}

    def test_malformed_downstream_entry(self):
        """Test handling of malformed downstream channel data."""
        parser = NetgearC3700Parser()
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

    def test_missing_javascript_functions(self):
        """Test parsing when JavaScript functions are not present."""
        parser = NetgearC3700Parser()
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
        parser = NetgearC3700Parser()
        assert parser.name == "Netgear C3700"

    def test_manufacturer(self):
        """Test parser manufacturer."""
        parser = NetgearC3700Parser()
        assert parser.manufacturer == "Netgear"

    def test_models(self):
        """Test parser supported models."""
        parser = NetgearC3700Parser()
        assert "C3700" in parser.models
        assert "C3700-100NAS" in parser.models

    def test_priority(self):
        """Test parser priority."""
        parser = NetgearC3700Parser()
        assert parser.priority == 50  # Standard priority
