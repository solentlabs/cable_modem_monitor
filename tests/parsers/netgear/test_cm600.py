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
