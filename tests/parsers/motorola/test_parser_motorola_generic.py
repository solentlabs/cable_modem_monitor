"""Tests for the generic Motorola MB series parser."""
import os
from bs4 import BeautifulSoup
import pytest
from unittest.mock import patch

from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser, RESTART_WINDOW_SECONDS

@pytest.fixture
def moto_home_html():
    """Load moto_home.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "generic", "moto_home.html")
    with open(fixture_path, 'r') as f:
        return f.read()

@pytest.fixture
def moto_connection_html():
    """Load moto_connection.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "generic", "moto_connection.html")
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

    # Parse connection page
    data = parser.parse(soup_conn)

    # Parse home page for software version
    home_info = parser._parse_system_info(soup_home)
    data["system_info"].update(home_info)

    # Verify downstream channels
    assert len(data["downstream"]) > 0
    assert data["downstream"][0]["channel_id"] is not None
    assert data["downstream"][0]["frequency"] > 0
    assert data["downstream"][0]["power"] is not None
    assert data["downstream"][0]["snr"] > 0
    assert data["downstream"][0]["corrected"] >= 0
    assert data["downstream"][0]["uncorrected"] >= 0
    assert data["downstream"][0]["modulation"] is not None

    # Verify upstream channels
    assert len(data["upstream"]) > 0
    assert data["upstream"][0]["channel_id"] is not None
    assert data["upstream"][0]["frequency"] > 0
    assert data["upstream"][0]["power"] is not None
    assert data["system_info"]["software_version"] == "7621-5.7.1.5"
    assert data["system_info"]["system_uptime"] == "26 days 19h:20m:55s" # This might vary, check fixture


def test_restart_detection_filters_zero_power():
    """Test that zero power values are filtered during restart window."""
    # Create minimal HTML with zero power/SNR values
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

    # During restart (< 5 min), zero power/SNR should be filtered to None
    assert len(data["downstream"]) == 1
    assert data["downstream"][0]["power"] is None  # Filtered out
    assert data["downstream"][0]["snr"] is None    # Filtered out
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

    # During restart, non-zero values should be preserved
    assert len(data["downstream"]) == 1
    assert data["downstream"][0]["power"] == 3.5   # Preserved
    assert data["downstream"][0]["snr"] == 38.2    # Preserved


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

    # After restart window (>= 5 min), zero values should be kept
    assert len(data["downstream"]) == 1
    assert data["downstream"][0]["power"] == 0  # NOT filtered
    assert data["downstream"][0]["snr"] == 0    # NOT filtered


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

    # During restart, zero upstream power should be filtered
    assert len(data["upstream"]) == 1
    assert data["upstream"][0]["power"] is None  # Filtered out


def test_restart_window_constant():
    """Test that the restart window constant is correctly defined."""
    assert RESTART_WINDOW_SECONDS == 300
    assert RESTART_WINDOW_SECONDS == 5 * 60  # 5 minutes