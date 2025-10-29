"""Tests for the generic Motorola MB series parser."""
import os
from bs4 import BeautifulSoup
import pytest

from custom_components.cable_modem_monitor.parsers.motorola_mb import MotorolaMBParser

@pytest.fixture
def moto_home_html():
    """Load moto_home.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "motorola", "moto_home.html")
    with open(fixture_path, 'r') as f:
        return f.read()

@pytest.fixture
def moto_connection_html():
    """Load moto_connection.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "motorola", "moto_connection.html")
    with open(fixture_path, 'r') as f:
        return f.read()

def test_parser_detection(moto_connection_html):
    """Test that the Motorola MB parser detects a generic MB modem."""
    soup = BeautifulSoup(moto_connection_html, "html.parser")
    assert MotorolaMBParser.can_parse(soup, "http://192.168.100.1/moto_connection.html", moto_connection_html)

def test_parsing(moto_connection_html, moto_home_html):
    """Test parsing of generic MB data."""
    parser = MotorolaMBParser()
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
    assert data["upstream"][0]["modulation"] is not None

    ***REMOVED*** Verify system info
    assert data["system_info"]["software_version"] is not None