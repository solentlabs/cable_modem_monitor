"""Tests for the Netgear CM600 parser.

Core fixtures (parser-essential):
- DashBoard.asp: Dashboard page
- DocsisOffline.asp: Offline error page
- DocsisStatus.asp: DOCSIS channel data (downstream/upstream/uptime)
- index.html: Main page
- RouterStatus.asp: Router/wireless status (hardware/firmware version)

Extended fixtures (in extended/):
- EventLog.asp: Event log page
- GPL_rev1.htm: GPL license
- SetPassword.asp: Password change page

Related: Issue #3 (Netgear CM600 - Login Doesn't Work)
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher
from modems.netgear.cm600.parser import NetgearCM600Parser
from tests.fixtures import load_fixture


@pytest.fixture
def cm600_index_html():
    """Load CM600 index.html fixture."""
    return load_fixture("netgear", "cm600", "index.html")


@pytest.fixture
def cm600_dashboard_html():
    """Load CM600 DashBoard.asp fixture."""
    return load_fixture("netgear", "cm600", "DashBoard.asp")


@pytest.fixture
def cm600_router_status_html():
    """Load CM600 RouterStatus.asp fixture."""
    return load_fixture("netgear", "cm600", "RouterStatus.asp")


@pytest.fixture
def cm600_docsis_status_html():
    """Load CM600 DocsisStatus.asp fixture."""
    return load_fixture("netgear", "cm600", "DocsisStatus.asp")


def test_fixtures_exist():
    """Verify all captured CM600 fixtures are present."""
    from tests.fixtures import fixture_exists, get_fixture_dir

    fixtures_dir = get_fixture_dir("netgear", "cm600")

    # Core files used by parser (at root)
    core_files = [
        "DashBoard.asp",
        "DocsisOffline.asp",
        "DocsisStatus.asp",
        "index.html",
        "RouterStatus.asp",
    ]

    # Extended files for reference (in extended/)
    extended_files = [
        "EventLog.asp",
        "GPL_rev1.htm",
        "SetPassword.asp",
    ]

    for filename in core_files:
        assert fixture_exists("netgear", "cm600", filename), f"Missing core fixture: {filename}"

    for filename in extended_files:
        filepath = fixtures_dir / "extended" / filename
        assert filepath.exists(), f"Missing extended fixture: {filename}"


def test_parser_detection(cm600_index_html):
    """Test that the Netgear CM600 parser detects the modem via HintMatcher."""
    hint_matcher = HintMatcher.get_instance()
    matches = hint_matcher.match_login_markers(cm600_index_html)
    assert any(m.parser_name == "NetgearCM600Parser" for m in matches)


def test_parser_detection_via_meta_description():
    """Test CM600 detection via meta description tag using HintMatcher."""
    html = """
    <html>
    <head>
        <meta name="description" content="CM600 Cable Modem">
        <title>Some Other Title</title>
    </head>
    <body></body>
    </html>
    """
    hint_matcher = HintMatcher.get_instance()
    matches = hint_matcher.match_login_markers(html)
    assert any(m.parser_name == "NetgearCM600Parser" for m in matches)


def test_parser_detection_via_page_content():
    """Test CM600 detection via page content using HintMatcher."""
    html = """
    <html>
    <head><title>Gateway</title></head>
    <body>
        <p>Welcome to your NETGEAR CM600 Cable Modem</p>
    </body>
    </html>
    """
    hint_matcher = HintMatcher.get_instance()
    matches = hint_matcher.match_login_markers(html)
    assert any(m.parser_name == "NetgearCM600Parser" for m in matches)


def test_parser_detection_negative():
    """Test that parser correctly rejects non-CM600 modems via HintMatcher.

    Uses match_model_strings (Phase 2) for model-specific discrimination.
    """
    html = """
    <html>
    <head><title>Some Other Modem</title></head>
    <body><p>Generic status page</p></body>
    </html>
    """
    hint_matcher = HintMatcher.get_instance()
    matches = hint_matcher.match_model_strings(html)
    assert not any(m.parser_name == "NetgearCM600Parser" for m in matches)


def test_parser_system_info(cm600_router_status_html):
    """Test parsing of Netgear CM600 system info from RouterStatus.asp."""
    parser = NetgearCM600Parser()

    # Parse just the RouterStatus page using the internal method
    soup = BeautifulSoup(cm600_router_status_html, "html.parser")
    system_info = parser._parse_router_system_info(soup)

    # Check that we extracted firmware version
    assert "software_version" in system_info
    assert system_info["software_version"] == "V1.01.22"

    # Check hardware version
    assert "hardware_version" in system_info
    assert system_info["hardware_version"] == "1.01B"


def test_parser_uptime_from_docsis_status(cm600_docsis_status_html):
    """Test parsing of uptime and last boot time from DocsisStatus.asp."""
    parser = NetgearCM600Parser()
    soup = BeautifulSoup(cm600_docsis_status_html, "html.parser")

    # Parse system info from DocsisStatus.asp
    system_info = parser.parse_system_info(soup)

    # Check uptime is parsed (CM600 uses HH:MM:SS format like "1308:19:22")
    assert "system_uptime" in system_info
    assert system_info["system_uptime"] == "1308:19:22"

    # Check last boot time is calculated
    assert "last_boot_time" in system_info
    # Boot time should be an ISO formatted datetime string
    from datetime import datetime

    boot_time = datetime.fromisoformat(system_info["last_boot_time"])
    assert boot_time < datetime.now()

    # Check current time is parsed
    assert "current_time" in system_info
    assert "Tue Oct 28" in system_info["current_time"]


def test_calculate_boot_time():
    """Test boot time calculation from uptime string."""
    from datetime import datetime, timedelta

    parser = NetgearCM600Parser()

    # Test with typical uptime format: "0d 1h 23m 45s"
    boot_time_str = parser._calculate_boot_time("0d 1h 23m 45s")
    assert boot_time_str is not None

    # Parse the ISO formatted boot time
    boot_time = datetime.fromisoformat(boot_time_str)
    # Boot time should be in the past
    assert boot_time < datetime.now()

    # Calculate expected boot time (within 1 second tolerance)
    expected_uptime = timedelta(days=0, hours=1, minutes=23, seconds=45)
    expected_boot = datetime.now() - expected_uptime
    # Allow 2 second tolerance for test execution time
    assert abs((boot_time - expected_boot).total_seconds()) < 2

    # Test with longer uptime
    boot_time_str = parser._calculate_boot_time("5d 12h 30m 15s")
    assert boot_time_str is not None
    boot_time = datetime.fromisoformat(boot_time_str)
    expected_uptime = timedelta(days=5, hours=12, minutes=30, seconds=15)
    expected_boot = datetime.now() - expected_uptime
    assert abs((boot_time - expected_boot).total_seconds()) < 2

    # Test with CM600 HH:MM:SS format (e.g., "1308:19:22" = 1308 hours)
    boot_time_str = parser._calculate_boot_time("1308:19:22")
    assert boot_time_str is not None
    boot_time = datetime.fromisoformat(boot_time_str)
    # 1308 hours = 54.5 days
    expected_uptime = timedelta(hours=1308, minutes=19, seconds=22)
    expected_boot = datetime.now() - expected_uptime
    assert abs((boot_time - expected_boot).total_seconds()) < 2

    # Test with shorter HH:MM:SS format
    boot_time_str = parser._calculate_boot_time("24:30:15")
    assert boot_time_str is not None
    boot_time = datetime.fromisoformat(boot_time_str)
    expected_uptime = timedelta(hours=24, minutes=30, seconds=15)
    expected_boot = datetime.now() - expected_uptime
    assert abs((boot_time - expected_boot).total_seconds()) < 2

    # Test with invalid uptime string
    boot_time_str = parser._calculate_boot_time("invalid")
    assert boot_time_str is None

    # Test with empty string
    boot_time_str = parser._calculate_boot_time("")
    assert boot_time_str is None


# Note: Legacy test_parse_with_session_* functions removed
# The new architecture uses parse_resources() instead of parse() with session parameter


def test_parsing_downstream(cm600_docsis_status_html):
    """Test parsing of Netgear CM600 downstream data."""
    parser = NetgearCM600Parser()
    soup = BeautifulSoup(cm600_docsis_status_html, "html.parser")
    data = parser.parse(soup)

    # Verify downstream channels were parsed
    assert "downstream" in data
    assert len(data["downstream"]) == 24  # CM600 supports 24 downstream channels

    # Check first downstream channel (from HTML table)
    first_ds = data["downstream"][0]
    assert first_ds["channel_id"] == "28"
    assert first_ds["frequency"] == 573000000  # 573 MHz in Hz
    assert first_ds["power"] == 6.6  # dBmV
    assert first_ds["snr"] == 40.9  # dB
    assert first_ds["modulation"] == "QAM256"
    assert first_ds["corrected"] == 22
    assert first_ds["uncorrected"] == 0

    # Check second channel to verify parsing continues correctly
    second_ds = data["downstream"][1]
    assert second_ds["channel_id"] == "21"
    assert second_ds["frequency"] == 525000000  # 525 MHz
    assert second_ds["power"] == 6.0


def test_parsing_upstream(cm600_docsis_status_html):
    """Test parsing of Netgear CM600 upstream data."""
    parser = NetgearCM600Parser()
    soup = BeautifulSoup(cm600_docsis_status_html, "html.parser")
    data = parser.parse(soup)

    # Verify upstream channels were parsed
    assert "upstream" in data
    assert len(data["upstream"]) == 6  # CM600 has 6 locked upstream channels in this fixture

    # Check first upstream channel (from HTML table)
    first_us = data["upstream"][0]
    assert first_us["channel_id"] == "5"
    assert first_us["frequency"] == 40400000  # 40.4 MHz in Hz
    assert first_us["power"] == 42.5  # dBmV
    assert first_us["channel_type"] == "ATDMA"

    # Check second channel to verify parsing
    second_us = data["upstream"][1]
    assert second_us["channel_id"] == "2"
    assert second_us["frequency"] == 22800000  # 22.8 MHz
    assert second_us["power"] == 42.3


class TestAuthentication:
    """Test auth discovery hints and URL patterns for CM600 (v3.12.0+)."""

    def test_url_patterns_auth_required(self):
        """Test that protected URLs require authentication."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_url_patterns_for_parser

        url_patterns = get_url_patterns_for_parser("NetgearCM600Parser")
        assert url_patterns is not None, "CM600 should have URL patterns in modem.yaml"

        # DocsisStatus.asp should require auth
        docsis_pattern = next(p for p in url_patterns if p["path"] == "/DocsisStatus.asp")
        assert docsis_pattern["auth_required"] is True
        assert docsis_pattern["auth_method"] == "basic"

        # DashBoard.asp should require auth
        dashboard_pattern = next(p for p in url_patterns if p["path"] == "/DashBoard.asp")
        assert dashboard_pattern["auth_required"] is True

        # RouterStatus.asp should require auth
        router_pattern = next(p for p in url_patterns if p["path"] == "/RouterStatus.asp")
        assert router_pattern["auth_required"] is True

        # Should have a public page for detection
        public_patterns = [p for p in url_patterns if not p.get("auth_required", True)]
        assert len(public_patterns) > 0, "CM600 should have a public page for detection"


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
        # Create HTML with malformed table row (missing cells)
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

        # Should handle gracefully and skip malformed entries
        assert "downstream" in data
        assert len(data["downstream"]) == 0  # Missing cells, should skip

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
        assert len(data["upstream"]) == 0  # Incomplete row, should skip

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

        # Parser should handle ValueError and skip invalid entries
        assert "downstream" in data
        assert len(data["downstream"]) == 0  # Invalid frequency, should skip

    def test_missing_tables(self):
        """Test parsing when HTML tables are not present."""
        parser = NetgearCM600Parser()
        html = "<html><body><p>No tables here</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        # Should return empty data structures without crashing
        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}


# Note: TestRestart class removed - restart functionality moved to action layer
# See tests/core/actions/test_html.py for HTML restart action tests


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

    def test_capabilities(self):
        """Test parser capabilities include uptime and last boot time."""
        from custom_components.cable_modem_monitor.core.base_parser import ModemCapability

        parser = NetgearCM600Parser()

        # Verify uptime capabilities are declared
        assert ModemCapability.SYSTEM_UPTIME in parser.capabilities
        assert ModemCapability.LAST_BOOT_TIME in parser.capabilities

        # Verify other expected capabilities
        assert ModemCapability.SCQAM_DOWNSTREAM in parser.capabilities
        assert ModemCapability.SCQAM_UPSTREAM in parser.capabilities
        assert ModemCapability.HARDWARE_VERSION in parser.capabilities
        assert ModemCapability.SOFTWARE_VERSION in parser.capabilities
        # Note: RESTART is now an action (check via ActionFactory.supports), not a capability
