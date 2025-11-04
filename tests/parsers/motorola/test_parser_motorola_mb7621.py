"""Tests for the Motorola MB7621 parser."""
import os
from bs4 import BeautifulSoup
import pytest
from unittest.mock import Mock

from custom_components.cable_modem_monitor.parsers.motorola.mb7621 import MotorolaMB7621Parser
from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser


@pytest.fixture
def mb7621_login_html():
    """Load login.html fixture for MB7621."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "b7621", "login.html")
    with open(fixture_path, 'r') as f:
        return f.read()

@pytest.fixture
def mb7621_connection_html():
    """Load MotoConnection.asp.html fixture for MB7621."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "mb7621", "MotoConnection.asp.html")
    with open(fixture_path, 'r') as f:
        return f.read()

@pytest.fixture
def mb7621_home_html():
    """Load MotoHome.asp.html fixture for MB7621."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "mb7621", "MotoHome.asp.html")
    with open(fixture_path, 'r') as f:
        return f.read()

@pytest.fixture
def mb7621_security_html():
    """Load MotoSecurity.asp.html fixture for MB7621."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "mb7621", "MotoSecurity.asp.html")
    with open(fixture_path, 'r') as f:
        return f.read()


def test_restart_mb7621(mb7621_security_html):
    """Test the restart functionality for MB7621."""
    parser = MotorolaMB7621Parser() ***REMOVED*** Use specific parser
    session = Mock()
    base_url = "http://192.168.100.1"

    ***REMOVED*** Mock the GET request to MotoSecurity.asp
    mock_security_response = Mock()
    mock_security_response.status_code = 200
    mock_security_response.text = mb7621_security_html
    session.get.return_value = mock_security_response

    ***REMOVED*** Mock the POST request for restart
    mock_restart_response = Mock()
    mock_restart_response.status_code = 200
    mock_restart_response.text = ""
    session.post.return_value = mock_restart_response

    ***REMOVED*** Test successful restart
    result = parser.restart(session, base_url)
    assert result is True

    session.get.assert_called_once_with(f"{base_url}/MotoSecurity.asp", timeout=10)
    session.post.assert_called_once_with(
        f"{base_url}/goform/MotoSecurity",
        data={
            "UserId": "",
            "OldPassword": "",
            "NewUserId": "",
            "Password": "",
            "PasswordReEnter": "",
            "MotoSecurityAction": "1"
        },
        timeout=10
    )

    ***REMOVED*** Test restart with ConnectionResetError (expected behavior during reboot)
    session.reset_mock()
    session.get.return_value = mock_security_response
    session.post.side_effect = ConnectionResetError("Connection reset by peer")

    result = parser.restart(session, base_url)
    assert result is True

    session.get.assert_called_once_with(f"{base_url}/MotoSecurity.asp", timeout=10)
    session.post.assert_called_once()


def test_parsing_mb7621(mb7621_connection_html, mb7621_home_html):
    """Test parsing of MB7621-specific data."""
    parser = MotorolaMB7621Parser() ***REMOVED*** Use specific parser
    soup_conn = BeautifulSoup(mb7621_connection_html, "html.parser")
    soup_home = BeautifulSoup(mb7621_home_html, "html.parser")

    ***REMOVED*** Parse connection page
    data = parser.parse(soup_conn)

    ***REMOVED*** Parse home page for software version
    home_info = parser._parse_system_info(soup_home)
    data["system_info"].update(home_info)

    ***REMOVED*** Verify downstream channels (example checks, adjust based on actual fixture content)
    assert "downstream" in data
    assert len(data["downstream"]) > 0
    assert data["downstream"][0]["channel_id"] == "1"
    assert data["downstream"][0]["frequency"] == 237000000
    assert data["downstream"][0]["power"] == 0.5
    assert data["downstream"][0]["snr"] == 41.4
    assert data["downstream"][0]["corrected"] == 42
    assert data["downstream"][0]["uncorrected"] == 0
    assert data["downstream"][0]["modulation"] == "QAM256"

    ***REMOVED*** Verify upstream channels (example checks, adjust based on actual fixture content)
    assert "upstream" in data
    assert len(data["upstream"]) > 0
    assert data["upstream"][0]["channel_id"] == "1"
    assert data["upstream"][0]["frequency"] == 24000000
    assert data["upstream"][0]["power"] == 36.2
    assert data["upstream"][0]["modulation"] == "ATDMA"

    ***REMOVED*** Verify system info
    assert "system_info" in data
    assert data["system_info"]["software_version"] == "7621-5.7.1.5"
    assert data["system_info"]["system_uptime"] == "32 days 11h:58m:26s" ***REMOVED*** This might vary, check fixture