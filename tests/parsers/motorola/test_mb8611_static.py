"""Tests for the Motorola MB8611 static HTML parser."""

from __future__ import annotations

import os

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.motorola.mb8611_static import (
    MotorolaMB8611StaticParser,
)


@pytest.fixture
def static_conn_html():
    """Load static MotoStatusConnection.html fixture from issue #6."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "mb8611_static", "MotoStatusConnection.html")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def static_sw_html():
    """Load static MotoStatusSoftware.html fixture from issue #6."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "mb8611_static", "MotoStatusSoftware.html")
    with open(fixture_path) as f:
        return f.read()


class TestStaticHtmlParsing:
    """Test parsing from static HTML files."""

    def test_parse_downstream_from_html(self, static_conn_html):
        """Test parsing downstream channels from a static HTML table."""
        parser = MotorolaMB8611StaticParser()
        soup = BeautifulSoup(static_conn_html, "html.parser")
        data = parser.parse(soup)

        assert "downstream" in data
        assert len(data["downstream"]) == 34

        # Check first channel
        first_channel = data["downstream"][0]
        assert first_channel["channel_id"] == 1
        assert first_channel["lock_status"] == "Locked"
        assert first_channel["modulation"] == "QAM256"
        assert first_channel["ch_id"] == 44
        assert first_channel["frequency"] == 639_000_000
        assert first_channel["power"] == -4.6
        assert first_channel["snr"] == 40.0
        assert first_channel["corrected"] == 0
        assert first_channel["uncorrected"] == 0

        # Check a middle channel
        middle_channel = data["downstream"][15]
        assert middle_channel["channel_id"] == 16
        assert middle_channel["ch_id"] == 27
        assert middle_channel["power"] == -1.1

        # Check last channel (OFDM)
        last_channel = data["downstream"][33]
        assert last_channel["channel_id"] == 34
        assert last_channel["lock_status"] == "Locked"
        assert last_channel["modulation"] == "OFDM PLC"
        assert last_channel["ch_id"] == 194
        assert last_channel["frequency"] == 957_000_000
        assert last_channel["power"] == -5.4
        assert last_channel["snr"] == 37.4
        assert last_channel["corrected"] == 6557784
        assert last_channel["uncorrected"] == 0

    def test_parse_upstream_from_html(self, static_conn_html):
        """Test parsing upstream channels from a static HTML table."""
        parser = MotorolaMB8611StaticParser()
        soup = BeautifulSoup(static_conn_html, "html.parser")
        data = parser.parse(soup)

        assert "upstream" in data
        assert len(data["upstream"]) == 4

        # Check first channel
        first_channel = data["upstream"][0]
        assert first_channel["channel_id"] == 1
        assert first_channel["lock_status"] == "Locked"
        assert first_channel["modulation"] == "SC-QAM"
        assert first_channel["ch_id"] == 1
        assert first_channel["symbol_rate"] == 5120
        assert first_channel["frequency"] == 16_400_000
        assert first_channel["power"] == 46.0

        # Check last channel
        last_channel = data["upstream"][3]
        assert last_channel["channel_id"] == 4
        assert last_channel["ch_id"] == 4
        assert last_channel["frequency"] == 35_600_000
        assert last_channel["power"] == 48.3

    def test_parse_system_info_from_html(self, static_conn_html, static_sw_html):
        """Test parsing system info from static HTML pages."""
        parser = MotorolaMB8611StaticParser()

        # The parser gets soup from one page at a time.
        # We test them separately and merge the results to check all fields.
        soup_conn = BeautifulSoup(static_conn_html, "html.parser")
        data_conn = parser.parse(soup_conn)

        soup_sw = BeautifulSoup(static_sw_html, "html.parser")
        data_sw = parser.parse(soup_sw)

        # Merge system info from both pages
        system_info = data_conn["system_info"] | data_sw["system_info"]

        assert system_info["system_uptime"] == "0 days 00h:27m:18s"
        assert system_info["network_access"] == "Allowed"
        assert system_info["connectivity_status"] == "OK"
        assert system_info["boot_status"] == "OK"
        assert system_info["security_status"] == "Enabled"
        assert system_info["security_comment"] == "BPI+"
        assert system_info["downstream_frequency"] == "639000000 Hz"
        assert system_info["docsis_version"] == "DOCSIS 3.1"
        assert system_info["hardware_version"] == "V1.0"
        assert system_info["software_version"] == "8611-19.2.18"


class TestMetadata:
    """Test parser metadata."""

    def test_name(self):
        """Test parser name."""
        parser = MotorolaMB8611StaticParser()
        assert parser.name == "Motorola MB8611 (Static)"

    def test_priority(self):
        """Test parser priority."""
        parser = MotorolaMB8611StaticParser()
        assert parser.priority == 100


class TestUrlPatterns:
    """Test parser URL patterns configuration."""

    def test_has_url_patterns(self):
        """Test that parser has url_patterns attribute."""
        from custom_components.cable_modem_monitor.parsers import get_parser_by_name

        parser_class = get_parser_by_name("Motorola MB8611 (Static)")
        assert parser_class is not None

        # Check for url_patterns attribute
        assert hasattr(parser_class, "url_patterns")
        assert isinstance(parser_class.url_patterns, list)
        assert len(parser_class.url_patterns) > 0

    def test_url_patterns_format(self):
        """Test that url_patterns are correctly formatted."""
        from custom_components.cable_modem_monitor.parsers import get_parser_by_name

        parser_class = get_parser_by_name("Motorola MB8611 (Static)")
        assert parser_class is not None

        # Check first pattern
        pattern = parser_class.url_patterns[0]
        assert "path" in pattern
        assert "auth_method" in pattern
        assert "auth_required" in pattern

        # Check specific values
        assert pattern["path"] == "/MotoStatusConnection.html"
        assert pattern["auth_method"] == "none"
        assert pattern["auth_required"] is False
