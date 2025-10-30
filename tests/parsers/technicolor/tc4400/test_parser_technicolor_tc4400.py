"""Tests for the Technicolor TC4400 parser."""
import os
import sys
from bs4 import BeautifulSoup
from unittest.mock import Mock
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from custom_components.cable_modem_monitor.parsers.technicolor.tc4400 import TechnicolorTC4400Parser

def load_fixture(filename):
    """Load a fixture file."""
    path = os.path.join(os.path.dirname(__file__), "fixtures", filename)
    with open(path, encoding="utf-8") as f:
        return f.read()

def test_technicolor_tc4400_parser():
    """Test the Technicolor TC4400 parser."""
    ***REMOVED*** Load the HTML content from the fixture files
    cmconnectionstatus_html = load_fixture("technicolor_tc4400_cmconnectionstatus.html")
    cmswinfo_html = load_fixture("technicolor_tc4400_cmswinfo.html")
    statsifc_html = load_fixture("technicolor_tc4400_statsifc.html")

    ***REMOVED*** Create an instance of the parser
    parser = TechnicolorTC4400Parser()

    ***REMOVED*** Test parsing of system info
    soup = BeautifulSoup(cmswinfo_html, "html.parser")
    data = parser.parse(soup)
    system_info = data["system_info"]
    assert system_info["standard_specification_compliant"] == "Docsis 3.1"
    assert system_info["hardware_version"] == "TC4400 Rev:3.6.0"
    assert system_info["software_version"] == "70.12.42-190604"
    assert system_info["mac_address"] == "90:"
    assert system_info.get("serial_number") == "CP"
    assert system_info["system_uptime"] == "17 days 00h:38m:36s"
    assert system_info["network_access"] == "Allowed"
    assert system_info["ipv4_address"] == "IPv4=10."
    assert system_info["ipv6_address"] == "IPv6="
    assert system_info["board_temperature"] == "-99.0 degrees Celsius"

    ***REMOVED*** Test parsing of downstream channels
    soup = BeautifulSoup(cmconnectionstatus_html, "html.parser")
    data = parser.parse(soup)
    downstream_channels = data["downstream"]
    assert len(downstream_channels) == 32
    assert downstream_channels[0]["channel_id"] == 12
    assert downstream_channels[0]["lock_status"] == "Locked"
    assert downstream_channels[0]["channel_type"] == "SC-QAM"
    assert downstream_channels[0]["bonding_status"] == "Bonded"
    assert downstream_channels[0]["frequency"] == 578000000
    assert downstream_channels[0]["width"] == 8000000
    assert downstream_channels[0]["snr"] == 40.1
    assert downstream_channels[0]["power"] == 3.0
    assert downstream_channels[0]["modulation"] == "QAM256"
    assert downstream_channels[0]["unerrored_codewords"] == 2893294930
    assert downstream_channels[0]["corrected"] == 201
    assert downstream_channels[0]["uncorrected"] == 449

    ***REMOVED*** Test parsing of upstream channels
    upstream_channels = data["upstream"]
    assert len(upstream_channels) == 5
    assert upstream_channels[0]["channel_id"] == 1
    assert upstream_channels[0]["lock_status"] == "Locked"
    assert upstream_channels[0]["channel_type"] == "SC-QAM"
    assert upstream_channels[0]["bonding_status"] == "Bonded"
    assert upstream_channels[0]["frequency"] == 30800000
    assert upstream_channels[0]["width"] == 6400000
    assert upstream_channels[0]["power"] == 47.0
    assert upstream_channels[0]["modulation"] == "ATDMA"

def test_tc4400_login_with_credentials():
    """Test that TC-4400 parser properly sets Basic HTTP Authentication with credentials."""
    parser = TechnicolorTC4400Parser()
    session = Mock()

    ***REMOVED*** Test with credentials - should set session.auth
    result = parser.login(session, "http://192.168.0.1", "admin", "password")

    assert result is True
    assert session.auth == ("admin", "password")

def test_tc4400_login_without_credentials():
    """Test that TC-4400 parser handles missing credentials gracefully."""
    parser = TechnicolorTC4400Parser()
    session = Mock()

    ***REMOVED*** Test without username
    result = parser.login(session, "http://192.168.0.1", "", "password")
    assert result is True

    ***REMOVED*** Test without password
    session2 = Mock()
    result = parser.login(session2, "http://192.168.0.1", "admin", "")
    assert result is True

    ***REMOVED*** Test without both
    session3 = Mock()
    result = parser.login(session3, "http://192.168.0.1", "", "")
    assert result is True

def test_tc4400_login_signature():
    """Test that login method accepts all required parameters including base_url.

    This test verifies the fix for GitHub Issue ***REMOVED***1 where the login signature
    was missing the base_url parameter, causing authentication to fail.
    """
    parser = TechnicolorTC4400Parser()
    session = Mock()

    ***REMOVED*** This should not raise TypeError - all 4 parameters should be accepted
    result = parser.login(session, "http://192.168.0.1", "admin", "password")
    assert result is True

    ***REMOVED*** Verify the signature matches what ModemScraper.login() calls
    ***REMOVED*** ModemScraper calls: parser.login(session, base_url, username, password)
    import inspect
    sig = inspect.signature(parser.login)
    params = list(sig.parameters.keys())

    ***REMOVED*** Should have: session, base_url, username, password (self is implicit)
    assert len(params) == 4
    assert params[0] == "session"
    assert params[1] == "base_url"
    assert params[2] == "username"
    assert params[3] == "password"
