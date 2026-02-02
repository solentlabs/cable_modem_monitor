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

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher
from modems.netgear.c3700.parser import NetgearC3700Parser
from tests.fixtures import load_fixture


@pytest.fixture
def c3700_index_html():
    """Load C3700 index.htm fixture."""
    return load_fixture("netgear", "c3700", "index.htm")


@pytest.fixture
def c3700_dashboard_html():
    """Load C3700 DashBoard.htm fixture."""
    return load_fixture("netgear", "c3700", "DashBoard.htm")


@pytest.fixture
def c3700_docsis_offline_html():
    """Load C3700 DocsisOffline.htm fixture."""
    return load_fixture("netgear", "c3700", "DocsisOffline.htm")


@pytest.fixture
def c3700_docsis_status_html():
    """Load C3700 DocsisStatus.htm fixture.

    NOTE: This fixture will be created when we have data from an online modem.
    """
    try:
        return load_fixture("netgear", "c3700", "DocsisStatus.htm")
    except FileNotFoundError:
        pytest.skip("DocsisStatus.htm fixture not yet available (modem was offline during capture)")
        return None  # Unreachable - pytest.skip raises, but satisfies static analysis


@pytest.fixture
def c3700_router_status_html():
    """Load C3700 RouterStatus.htm fixture.

    Contains system info (hardware/firmware versions).
    """
    try:
        return load_fixture("netgear", "c3700", "RouterStatus.htm")
    except FileNotFoundError:
        pytest.skip("RouterStatus.htm fixture not yet available")
        return None  # Unreachable - pytest.skip raises, but satisfies static analysis


def test_parser_detection(c3700_index_html):
    """Test that the Netgear C3700 parser detects the modem via HintMatcher."""
    hint_matcher = HintMatcher.get_instance()
    matches = hint_matcher.match_login_markers(c3700_index_html)
    assert any(m.parser_name == "NetgearC3700Parser" for m in matches)


def test_parser_detection_from_title():
    """Test C3700 detection from page title via HintMatcher."""
    html = """
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
    <html><head><title>NETGEAR Gateway C3700-100NAS</title></head>
    <body></body></html>
    """
    hint_matcher = HintMatcher.get_instance()
    matches = hint_matcher.match_login_markers(html)
    assert any(m.parser_name == "NetgearC3700Parser" for m in matches)


def test_parser_detection_from_meta():
    """Test C3700 detection from meta description via HintMatcher."""
    html = """
    <html>
    <head>
        <META content='C3700-100NAS' name="description">
        <title>NETGEAR Gateway</title>
    </head>
    <body></body>
    </html>
    """
    hint_matcher = HintMatcher.get_instance()
    matches = hint_matcher.match_login_markers(html)
    assert any(m.parser_name == "NetgearC3700Parser" for m in matches)


def test_parser_detection_from_content():
    """Test C3700 detection from page content via HintMatcher."""
    html = """
    <html>
    <head><title>NETGEAR Gateway</title></head>
    <body>
        <p>Welcome to your C3700 gateway</p>
    </body>
    </html>
    """
    hint_matcher = HintMatcher.get_instance()
    matches = hint_matcher.match_login_markers(html)
    assert any(m.parser_name == "NetgearC3700Parser" for m in matches)


def test_parser_does_not_match_other_models():
    """Test that C3700 parser doesn't match other Netgear models via HintMatcher.

    Uses match_model_strings (Phase 2) for model-specific discrimination.
    login_markers (Phase 1) uses shared manufacturer markers like 'NETGEAR'.
    """
    # CM600 page should not match C3700 parser
    html = """
    <html>
    <head><title>NETGEAR Gateway CM600-100NAS</title></head>
    <body></body>
    </html>
    """
    hint_matcher = HintMatcher.get_instance()
    matches = hint_matcher.match_model_strings(html)
    assert not any(m.parser_name == "NetgearC3700Parser" for m in matches)


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

    # Verify actual values from fixture (channel 41, ATDMA, 17.8 MHz, 54.3 dBmV)
    # IMPORTANT: Parser returns uppercase "ATDMA" as-is from modem HTML
    # sensor.py must normalize to lowercase for _upstream_by_id lookup
    assert first_us["channel_id"] == "41"
    assert first_us["channel_type"] == "ATDMA"  # Raw value from modem (uppercase)
    assert first_us["frequency"] == 17800000
    assert first_us["power"] == 54.3


def test_multi_page_parsing_with_session(c3700_index_html, c3700_docsis_status_html, c3700_router_status_html):
    """Test that parser fetches DocsisStatus.htm and RouterStatus.htm when session and base_url are provided.

    This tests the multi-page parsing fix where the parser should fetch
    DocsisStatus.htm to get channel data and RouterStatus.htm for system info,
    even when initially given a different page.
    """
    from unittest.mock import Mock, call

    parser = NetgearC3700Parser()

    # Create mock session that returns appropriate pages when requested
    mock_session = Mock()

    def mock_get(url, timeout=10):
        mock_response = Mock()
        mock_response.status_code = 200
        if "DocsisStatus.htm" in url:
            mock_response.text = c3700_docsis_status_html
        elif "RouterStatus.htm" in url:
            mock_response.text = c3700_router_status_html
        else:
            mock_response.text = c3700_index_html
        return mock_response

    mock_session.get.side_effect = mock_get

    # Parse with index.htm soup but provide session and base_url
    # Parser should fetch DocsisStatus.htm and RouterStatus.htm
    index_soup = BeautifulSoup(c3700_index_html, "html.parser")
    data = parser.parse(index_soup, session=mock_session, base_url="http://192.168.100.1")

    # Verify both pages were requested
    expected_calls = [
        call("http://192.168.100.1/DocsisStatus.htm", timeout=10),
        call("http://192.168.100.1/RouterStatus.htm", timeout=10),
    ]
    mock_session.get.assert_has_calls(expected_calls, any_order=False)
    assert mock_session.get.call_count == 2

    # Verify channel data was parsed from DocsisStatus.htm
    assert len(data["downstream"]) > 0
    assert len(data["upstream"]) > 0

    # Verify system info was parsed from RouterStatus.htm
    assert "system_info" in data
    assert data["system_info"].get("hardware_version") is not None
    assert data["system_info"].get("software_version") is not None


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

    # Should return empty channel structures without crashing
    # Model name is still extracted from static page content
    assert data["downstream"] == []
    assert data["upstream"] == []
    assert data["system_info"].get("model_name") == "C3700-100NAS"


class TestAuthentication:
    """Test auth discovery hints and URL patterns for C3700 (v3.12.0+)."""

    def test_url_patterns_auth_required(self):
        """Test that protected URLs require authentication."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_url_patterns_for_parser

        url_patterns = get_url_patterns_for_parser("NetgearC3700Parser")
        assert url_patterns is not None, "C3700 should have URL patterns in modem.yaml"

        # DocsisStatus.htm should require auth
        docsis_pattern = next(p for p in url_patterns if p["path"] == "/DocsisStatus.htm")
        assert docsis_pattern["auth_required"] is True
        assert docsis_pattern["auth_method"] == "basic"

        # DashBoard.htm should require auth
        dashboard_pattern = next(p for p in url_patterns if p["path"] == "/DashBoard.htm")
        assert dashboard_pattern["auth_required"] is True

        # RouterStatus.htm should require auth
        router_pattern = next(p for p in url_patterns if p["path"] == "/RouterStatus.htm")
        assert router_pattern["auth_required"] is True

        # Index page should NOT require auth (could be / or /index.htm)
        public_patterns = [p for p in url_patterns if not p.get("auth_required", True)]
        assert len(public_patterns) > 0, "C3700 should have a public index page"


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

    def test_capabilities_include_uptime_and_restart(self):
        """Test that parser capabilities include uptime and restart."""
        from custom_components.cable_modem_monitor.core.base_parser import ModemCapability

        parser = NetgearC3700Parser()
        assert ModemCapability.SYSTEM_UPTIME in parser.capabilities
        assert ModemCapability.LAST_BOOT_TIME in parser.capabilities
        # Note: RESTART is now an action (check via ActionFactory.supports), not a capability


# Note: TestRestart class removed - restart functionality moved to action layer
# See tests/core/actions/test_html.py for HTML restart action tests


class TestUptimeParsing:
    """Test uptime parsing functionality."""

    def test_parse_uptime_from_system_info(self, c3700_router_status_html):
        """Test parsing uptime from RouterStatus.htm."""
        parser = NetgearC3700Parser()
        soup = BeautifulSoup(c3700_router_status_html, "html.parser")
        system_info = parser.parse_system_info(soup)

        # The fixture has "26 days ***IPv6***" which contains sanitized data
        # Since *** is in the uptime, it should NOT be parsed
        # This test documents the expected behavior with sanitized data
        assert "hardware_version" in system_info
        assert "software_version" in system_info

    def test_parse_uptime_with_real_data(self):
        """Test parsing uptime when data is not sanitized."""
        parser = NetgearC3700Parser()
        # Create HTML with unsanitized uptime data (tagValues[33] = uptime)
        tag_values = (
            "C279T00-01|V2.02.18|serial|1|mac1|ip1|gw1|dns1|Allowed|mac2|ip2|"
            "dhcp|ip3|dns2|mac3|ip4|On|ssid1|region1|ch1|speed1|on1|on2|ssid2|"
            "region2|ch2|speed2|on3|on4|guest1|off1|guest2|off2|"
            "5 days 12:34:56|Wed Nov 26 2025|conf1|conf2"
        )
        html = f"""
        <script>
        var tagValueList = '{tag_values}';
        </script>
        """
        soup = BeautifulSoup(html, "html.parser")
        system_info = parser.parse_system_info(soup)

        assert system_info.get("system_uptime") == "5 days 12:34:56"
        assert "last_boot_time" in system_info  # Should have calculated boot time

    def test_calculate_boot_time(self):
        """Test boot time calculation from uptime string."""
        from datetime import datetime, timedelta

        parser = NetgearC3700Parser()

        # Test with "2 days" uptime
        boot_time = parser._calculate_boot_time("2 days")
        assert boot_time is not None

        # Parse the ISO format and verify it's approximately 2 days ago
        boot_datetime = datetime.fromisoformat(boot_time)
        expected_boot = datetime.now() - timedelta(days=2)

        # Allow 1 minute tolerance for test execution time
        assert abs((boot_datetime - expected_boot).total_seconds()) < 60

    def test_calculate_boot_time_with_invalid_string(self):
        """Test boot time calculation returns None for invalid input."""
        parser = NetgearC3700Parser()

        result = parser._calculate_boot_time("invalid uptime string")

        assert result is None
