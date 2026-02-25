"""Tests for the Technicolor TC4400 parser."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from modems.technicolor.tc4400.parser import (
    _DEFAULT_RESTART_WINDOW_SECONDS,
    TechnicolorTC4400Parser,
)
from tests.fixtures import load_fixture


@pytest.fixture
def cmconnectionstatus_html():
    """Load cmconnectionstatus.html fixture."""
    return load_fixture("technicolor", "tc4400", "cmconnectionstatus.html")


@pytest.fixture
def cmswinfo_html():
    """Load cmswinfo.html fixture."""
    return load_fixture("technicolor", "tc4400", "cmswinfo.html")


@pytest.fixture
def statsifc_html():
    """Load statsifc.html fixture."""
    return load_fixture("technicolor", "tc4400", "statsifc.html")


class TestParsing:
    """Test parser functionality."""

    def test_system_info(self, cmswinfo_html):
        """Test parsing of system info."""
        parser = TechnicolorTC4400Parser()
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

    def test_downstream_channels(self, cmconnectionstatus_html):
        """Test parsing of downstream channels."""
        parser = TechnicolorTC4400Parser()
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

    def test_upstream_channels(self, cmconnectionstatus_html):
        """Test parsing of upstream channels."""
        parser = TechnicolorTC4400Parser()
        soup = BeautifulSoup(cmconnectionstatus_html, "html.parser")
        data = parser.parse(soup)
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


class TestRestartDetection:
    """Test restart detection and zero-value filtering."""

    def test_filters_zero_power(self):
        """Test that zero power values are filtered during restart window."""
        html = """
        <html><body>
        <table><tr><th colspan="13">Downstream Channel Status</th></tr>
        <tr><td class="hd">Index</td><td class="hd">Channel ID</td><td class="hd">Lock Status</td>
            <td class="hd">Channel Type</td><td class="hd">Bonding Group ID</td><td class="hd">Frequency (MHz)</td>
            <td class="hd">Width (MHz)</td><td class="hd">SNR (dB)</td><td class="hd">Power (dBmV)</td>
            <td class="hd">Modulation</td><td class="hd">Unerrored Codewords</td>
            <td class="hd">Correctable Codewords</td><td class="hd">Uncorrectable Codewords</td></tr>
        <tr><td>1</td><td>12</td><td>Locked</td><td>SC-QAM</td><td>Bonded</td>
            <td>578</td><td>8</td><td>0</td><td>0</td><td>QAM256</td>
            <td>100</td><td>0</td><td>0</td></tr>
        </table>
        <table><tr><td class="hd">System Up Time</td><td>0 days 00h:03m:45s</td></tr></table>
        </body></html>
        """

        parser = TechnicolorTC4400Parser()
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        # During restart (< 5 min), zero power/SNR should be filtered to None
        assert len(data["downstream"]) == 1
        assert data["downstream"][0]["power"] is None  # Filtered out
        assert data["downstream"][0]["snr"] is None  # Filtered out
        assert data["system_info"]["system_uptime"] == "0 days 00h:03m:45s"

    def test_preserves_nonzero_power(self):
        """Test that non-zero power values are preserved during restart window."""
        html = """
        <html><body>
        <table><tr><th colspan="13">Downstream Channel Status</th></tr>
        <tr><td class="hd">Index</td><td class="hd">Channel ID</td><td class="hd">Lock Status</td>
            <td class="hd">Channel Type</td><td class="hd">Bonding Group ID</td><td class="hd">Frequency (MHz)</td>
            <td class="hd">Width (MHz)</td><td class="hd">SNR (dB)</td><td class="hd">Power (dBmV)</td>
            <td class="hd">Modulation</td><td class="hd">Unerrored Codewords</td>
            <td class="hd">Correctable Codewords</td><td class="hd">Uncorrectable Codewords</td></tr>
        <tr><td>1</td><td>12</td><td>Locked</td><td>SC-QAM</td><td>Bonded</td>
            <td>578</td><td>8</td><td>40.1</td><td>3.0</td><td>QAM256</td>
            <td>100</td><td>0</td><td>0</td></tr>
        </table>
        <table><tr><td class="hd">System Up Time</td><td>0 days 00h:02m:00s</td></tr></table>
        </body></html>
        """

        parser = TechnicolorTC4400Parser()
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        # During restart, non-zero values should be preserved
        assert len(data["downstream"]) == 1
        assert data["downstream"][0]["power"] == 3.0  # Preserved
        assert data["downstream"][0]["snr"] == 40.1  # Preserved

    def test_no_filtering_after_window(self):
        """Test that zero power values are NOT filtered after restart window."""
        html = """
        <html><body>
        <table><tr><th colspan="13">Downstream Channel Status</th></tr>
        <tr><td class="hd">Index</td><td class="hd">Channel ID</td><td class="hd">Lock Status</td>
            <td class="hd">Channel Type</td><td class="hd">Bonding Group ID</td><td class="hd">Frequency (MHz)</td>
            <td class="hd">Width (MHz)</td><td class="hd">SNR (dB)</td><td class="hd">Power (dBmV)</td>
            <td class="hd">Modulation</td><td class="hd">Unerrored Codewords</td>
            <td class="hd">Correctable Codewords</td><td class="hd">Uncorrectable Codewords</td></tr>
        <tr><td>1</td><td>12</td><td>Locked</td><td>SC-QAM</td><td>Bonded</td>
            <td>578</td><td>8</td><td>0</td><td>0</td><td>QAM256</td>
            <td>100</td><td>0</td><td>0</td></tr>
        </table>
        <table><tr><td class="hd">System Up Time</td><td>0 days 00h:06m:00s</td></tr></table>
        </body></html>
        """

        parser = TechnicolorTC4400Parser()
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        # After restart window (>= 5 min), zero values should be kept
        assert len(data["downstream"]) == 1
        assert data["downstream"][0]["power"] == 0  # NOT filtered
        assert data["downstream"][0]["snr"] == 0  # NOT filtered

    def test_filters_upstream_zero_power(self):
        """Test that zero power values are filtered for upstream during restart."""
        html = """
        <html><body>
        <table><tr><th colspan="9">Upstream Channel Status</th></tr>
        <tr><td class="hd">Index</td><td class="hd">Channel ID</td><td class="hd">Lock Status</td>
            <td class="hd">Channel Type</td><td class="hd">Bonding Group ID</td><td class="hd">Frequency (MHz)</td>
            <td class="hd">Width (MHz)</td><td class="hd">Power (dBmV)</td><td class="hd">Modulation</td></tr>
        <tr><td>1</td><td>1</td><td>Locked</td><td>SC-QAM</td><td>Bonded</td>
            <td>30.8</td><td>6.4</td><td>0</td><td>ATDMA</td></tr>
        </table>
        <table><tr><td class="hd">System Up Time</td><td>0 days 00h:01m:30s</td></tr></table>
        </body></html>
        """

        parser = TechnicolorTC4400Parser()
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        # During restart, zero upstream power should be filtered
        assert len(data["upstream"]) == 1
        assert data["upstream"][0]["power"] is None  # Filtered out


class TestConstants:
    """Test parser constants."""

    def test_window_default(self):
        """Test that the restart window default is correctly defined."""
        assert _DEFAULT_RESTART_WINDOW_SECONDS == 300
        assert _DEFAULT_RESTART_WINDOW_SECONDS == 5 * 60  # 5 minutes
