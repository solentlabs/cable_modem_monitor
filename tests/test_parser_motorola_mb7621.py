"""Tests for the Motorola MB series parser with MB7621 fixtures."""
import os
from bs4 import BeautifulSoup
import pytest

from custom_components.cable_modem_monitor.parsers.motorola_mb import MotorolaMBParser

@pytest.fixture
def moto_home_html():
    """Load MotoHome.asp.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "motorola_mb7621", "MotoHome.asp.html")
    with open(fixture_path, 'r') as f:
        return f.read()

@pytest.fixture
def moto_connection_html():
    """Load MotoConnection.asp.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "motorola_mb7621", "MotoConnection.asp.html")
    with open(fixture_path, 'r') as f:
        return f.read()

def test_parser_detection(moto_connection_html):
    """Test that the Motorola MB parser detects MB7621 modem."""
    soup = BeautifulSoup(moto_connection_html, "html.parser")
    assert MotorolaMBParser.can_parse(soup, "http://192.168.100.1/MotoConnection.asp", moto_connection_html)

def test_parsing(moto_connection_html, moto_home_html):
    """Test parsing of MB7621 data."""
    parser = MotorolaMBParser()
    soup_conn = BeautifulSoup(moto_connection_html, "html.parser")
    soup_home = BeautifulSoup(moto_home_html, "html.parser")

    ***REMOVED*** Parse connection page
    data = parser.parse(soup_conn)

    ***REMOVED*** Parse home page for software version
    home_info = parser._parse_system_info(soup_home)
    data["system_info"].update(home_info)

    ***REMOVED*** Verify downstream channels
    assert len(data["downstream"]) == 24
    assert data["downstream"][0]["channel_id"] == "1"
    assert data["downstream"][0]["frequency"] == 237000000.0
    assert data["downstream"][0]["power"] == 0.5
    assert data["downstream"][0]["snr"] == 41.4
    assert data["downstream"][0]["corrected"] == 42
    assert data["downstream"][0]["uncorrected"] == 0
    assert data["downstream"][0]["modulation"] == "QAM256"

    ***REMOVED*** Verify upstream channels (5 locked channels)
    assert len(data["upstream"]) == 5
    assert data["upstream"][0]["channel_id"] == "1"
    assert data["upstream"][0]["frequency"] == 24000000.0
    assert data["upstream"][0]["power"] == 36.2
    assert data["upstream"][0]["modulation"] == "ATDMA"

    ***REMOVED*** Verify system info
    assert data["system_info"]["software_version"] == "7621-5.7.1.5"
