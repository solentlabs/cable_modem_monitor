"Tests for the generic Motorola MB series parser."
import os
from bs4 import BeautifulSoup
import pytest
from unittest.mock import patch

from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser, RESTART_WINDOW_SECONDS

@pytest.fixture
def moto_home_html():
    """Load moto_home.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "generic", "MotoHome.asp")
    with open(fixture_path, 'r') as f:
        return f.read()

@pytest.fixture
def moto_connection_html():
    """Load moto_connection.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "generic", "MotoConnection.asp")
    with open(fixture_path, 'r') as f:
        return f.read()

def test_parser_detection(moto_connection_html):
    """Test that the Motorola MB parser detects a generic MB modem."""
    soup = BeautifulSoup(moto_connection_html, "html.parser")
    assert MotorolaGenericParser.can_parse(soup, "http://192.168.100.1/moto_connection.html", moto_connection_html)

def test_parsing(moto_connection_html, moto_home_html):
    """Test parsing of generic MB data."""
    parser = MotorolaGenericParser()
    soup_conn = BeautifulSoup(moto_connection_html, "html.parser")
    soup_home = BeautifulSoup(moto_home_html, "html.parser")

    ***REMOVED*** Parse connection page
    data = parser.parse(soup_conn)

    ***REMOVED*** Parse home page for software version
    home_info = parser._parse_system_info(soup_home)
    data["system_info"].update(home_info)

    ***REMOVED*** Verify downstream channels
    assert len(data["downstream"]) > 0
    assert data["downstream"][0]["channel_id"] is not None
    assert data["downstream"][0]["frequency"] > 0
    assert data["downstream"][0]["power"] is not None
    assert data["downstream"][0]["snr"] > 0
    assert data["downstream"][0]["corrected"] >= 0
    assert data["downstream"][0]["uncorrected"] >= 0
    assert data["downstream"][0]["modulation"] is not None

    ***REMOVED*** Verify upstream channels
    assert len(data["upstream"]) > 0
    assert data["upstream"][0]["channel_id"] is not None
    assert data["upstream"][0]["frequency"] > 0
    assert data["upstream"][0]["power"] is not None
    assert data["system_info"]["software_version"] == "7621-5.7.1.5"
    assert data["system_info"]["system_uptime"] == "26 days 19h:20m:55s" ***REMOVED*** This might vary, check fixture


def test_restart_detection_filters_zero_power():
    """Test that zero power values are filtered during restart window."""
    ***REMOVED*** Create minimal HTML with zero power/SNR values
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

    parser = MotorolaGenericParser()
    soup = BeautifulSoup(html, "html.parser")
    data = parser.parse(soup)

    ***REMOVED*** During restart (< 5 min), zero power/SNR should be filtered to None
    assert len(data["downstream"]) == 1
    assert data["downstream"][0]["power"] is None  ***REMOVED*** Filtered out
    assert data["downstream"][0]["snr"] is None    ***REMOVED*** Filtered out
    assert data["system_info"]["system_uptime"] == "0 days 00h:04m:30s"


def test_restart_detection_preserves_nonzero_power():
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

    parser = MotorolaGenericParser()
    soup = BeautifulSoup(html, "html.parser")
    data = parser.parse(soup)

    ***REMOVED*** During restart, non-zero values should be preserved
    assert len(data["downstream"]) == 1
    assert data["downstream"][0]["power"] == 3.5   ***REMOVED*** Preserved
    assert data["downstream"][0]["snr"] == 38.2    ***REMOVED*** Preserved


def test_no_filtering_after_restart_window():
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

    parser = MotorolaGenericParser()
    soup = BeautifulSoup(html, "html.parser")
    data = parser.parse(soup)

    ***REMOVED*** After restart window (>= 5 min), zero values should be kept
    assert len(data["downstream"]) == 1
    assert data["downstream"][0]["power"] == 0  ***REMOVED*** NOT filtered
    assert data["downstream"][0]["snr"] == 0    ***REMOVED*** NOT filtered


def test_restart_detection_upstream_channels():
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

    parser = MotorolaGenericParser()
    soup = BeautifulSoup(html, "html.parser")
    data = parser.parse(soup)

    ***REMOVED*** During restart, zero upstream power should be filtered
    assert len(data["upstream"]) == 1
    assert data["upstream"][0]["power"] is None  ***REMOVED*** Filtered out


def test_restart_window_constant():
    """Test that the restart window constant is correctly defined."""
    assert RESTART_WINDOW_SECONDS == 300
    assert RESTART_WINDOW_SECONDS == 5 * 60  ***REMOVED*** 5 minutes

def test_downstream_channels(moto_connection_html):
    """Test parsing downstream channels."""
    parser = MotorolaGenericParser()
    soup = BeautifulSoup(moto_connection_html, 'html.parser')
    system_info = parser._parse_system_info(soup)
    channels = parser._parse_downstream(soup, system_info)

    assert len(channels) == 24, f"Expected 24 downstream channels, got {len(channels)}"

    first_ch = channels[0]
    assert 'channel_id' in first_ch, "Missing 'channel_id' field"
    assert 'power' in first_ch, "Missing 'power' field"
    assert 'snr' in first_ch, "Missing 'snr' field"
    assert 'frequency' in first_ch, "Missing 'frequency' field"
    assert 'corrected' in first_ch, "Missing 'corrected' field"
    assert 'uncorrected' in first_ch, "Missing 'uncorrected' field"

def test_upstream_channels(moto_connection_html):
    """Test parsing upstream channels."""
    parser = MotorolaGenericParser()
    soup = BeautifulSoup(moto_connection_html, 'html.parser')
    system_info = parser._parse_system_info(soup)
    channels = parser._parse_upstream(soup, system_info)

    assert len(channels) > 0, "Should have at least one upstream channel"

    first_ch = channels[0]
    assert 'channel_id' in first_ch, "Missing 'channel_id' field"
    assert 'power' in first_ch, "Missing 'power' field"
    assert 'frequency' in first_ch, "Missing 'frequency' field"

def test_software_version(moto_home_html):
    """Test parsing software version."""
    parser = MotorolaGenericParser()
    soup = BeautifulSoup(moto_home_html, 'html.parser')

    info = parser._parse_system_info(soup)

    assert info['software_version'] != "Unknown", f"Should find software version, got '{info['software_version']}'"
    assert info['software_version'] == "7621-5.7.1.5", f"Expected '7621-5.7.1.5', got '{info['software_version']}'"

def test_system_uptime(moto_connection_html):
    """Test parsing system uptime."""
    parser = MotorolaGenericParser()
    soup = BeautifulSoup(moto_connection_html, 'html.parser')

    info = parser._parse_system_info(soup)

    assert info['system_uptime'] != "Unknown", f"Should find system uptime, got '{info['system_uptime']}'"
    assert "days" in info['system_uptime'].lower() or "h:" in info['system_uptime'], \
        f"Uptime should contain time info, got '{info['system_uptime']}'"

def test_channel_counts(moto_connection_html, moto_home_html):
    """Test parsing channel counts."""
    parser = MotorolaGenericParser()
    soup_conn = BeautifulSoup(moto_connection_html, 'html.parser')
    soup_home = BeautifulSoup(moto_home_html, 'html.parser')
    system_info = parser._parse_system_info(soup_conn)
    system_info.update(parser._parse_system_info(soup_home))

    downstream_channels = parser._parse_downstream(soup_conn, system_info)
    upstream_channels = parser._parse_upstream(soup_conn, system_info)

    assert len(downstream_channels) is not None, "Should find downstream count"
    assert len(upstream_channels) is not None, "Should find upstream count"
    assert len(downstream_channels) == 24, \
        f"Expected 24 downstream channels, got {len(downstream_channels)}"
    assert len(upstream_channels) == 5, \
        f"Expected 5 upstream channels, got {len(upstream_channels)}"

def test_error_totals(moto_connection_html):
    """Test error total calculations."""
    parser = MotorolaGenericParser()
    soup = BeautifulSoup(moto_connection_html, 'html.parser')
    system_info = parser._parse_system_info(soup)
    channels = parser._parse_downstream(soup, system_info)
    total_corrected = sum(ch.get("corrected", 0) for ch in channels)
    total_uncorrected = sum(ch.get("uncorrected", 0) for ch in channels)

    assert isinstance(total_corrected, int), "Total corrected should be int"
    assert isinstance(total_uncorrected, int), "Total uncorrected should be int"
    assert total_corrected >= 0, "Total corrected should be non-negative"
    assert total_uncorrected >= 0, "Total uncorrected should be non-negative"