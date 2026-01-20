"""Tests for the Arris CM820B parser."""

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemCapability
from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher
from custom_components.cable_modem_monitor.modems.arris.cm820b.parser import ArrisCM820BParser
from tests.fixtures import load_fixture


@pytest.fixture
def arris_cm820b_status_html():
    """Load CM820B status page fixture."""
    return load_fixture("arris", "cm820b", "cgi-bin/status_cgi")


@pytest.fixture
def arris_cm820b_info_html():
    """Load CM820B info page fixture."""
    return load_fixture("arris", "cm820b", "cgi-bin/vers_cgi")


class TestCM820BParserDetection:
    """Test parser detection logic."""

    def test_parser_detection(self, arris_cm820b_info_html):
        """Test that the Arris CM820B parser detects the modem via HintMatcher."""
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(arris_cm820b_info_html)
        assert any(m.parser_name == "ArrisCM820BParser" for m in matches)

    def test_parser_metadata(self):
        """Test parser metadata is correct."""
        assert ArrisCM820BParser.name == "ARRIS CM820B"
        assert ArrisCM820BParser.manufacturer == "ARRIS"
        assert "CM820B" in ArrisCM820BParser.models

        # Status and docsis_version now read from modem.yaml via adapter
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("ArrisCM820BParser")
        assert adapter is not None
        assert adapter.get_docsis_version() == "3.0"
        assert adapter.get_status() == "verified"  # Verified by @dimkalinux (PR #57)


class TestCM820BParserCapabilities:
    """Test parser capabilities declaration."""

    def test_has_downstream_capability(self):
        """Test downstream channels capability."""
        assert ArrisCM820BParser.has_capability(ModemCapability.SCQAM_DOWNSTREAM)

    def test_has_upstream_capability(self):
        """Test upstream channels capability."""
        assert ArrisCM820BParser.has_capability(ModemCapability.SCQAM_UPSTREAM)

    def test_has_uptime_capability(self):
        """Test uptime capability (from cmswinfo.html)."""
        assert ArrisCM820BParser.has_capability(ModemCapability.SYSTEM_UPTIME)


class TestCM820BDownstreamParsing:
    """Test downstream channel parsing."""

    def test_parsing_downstream(self, arris_cm820b_status_html):
        """Test parsing of Arris CM820B downstream data."""
        parser = ArrisCM820BParser()
        soup = BeautifulSoup(arris_cm820b_status_html, "html.parser")
        data = parser.parse(soup)

        # Verify downstream channels (8 channels in fixture)
        assert "downstream" in data
        assert len(data["downstream"]) == 8

        # Check first downstream channel
        first_ds = data["downstream"][0]
        assert first_ds["channel_id"] == "73"
        assert first_ds["frequency"] == 178000000
        assert first_ds["snr"] == 34.48
        assert first_ds["power"] == 3.82
        assert first_ds["corrected"] == 33958022
        assert first_ds["uncorrected"] == 445244
        assert first_ds["modulation"] == "256QAM"

        # Check second channel to verify parsing
        second_ds = data["downstream"][1]
        assert second_ds["channel_id"] == "74"
        assert second_ds["frequency"] == 186000000
        assert second_ds["modulation"] == "256QAM"


class TestCM820BUpstreamParsing:
    """Test upstream channel parsing."""

    def test_parsing_upstream(self, arris_cm820b_status_html):
        """Test parsing of Arris CM820B upstream data."""
        parser = ArrisCM820BParser()
        soup = BeautifulSoup(arris_cm820b_status_html, "html.parser")
        data = parser.parse(soup)

        # Verify upstream channels (4 channels expected)
        assert "upstream" in data
        assert len(data["upstream"]) == 4

        # Check first upstream channel
        first_us = data["upstream"][0]
        assert first_us["channel_id"] == "6"
        assert first_us["frequency"] == 47000000
        assert first_us["power"] == 46.25
        assert first_us["modulation"] == "32QAM"
        assert first_us["symbol_rate"] == 5120


class TestCM820BSystemInfo:
    """Test system info parsing."""

    def test_parsing_system_info(self, arris_cm820b_status_html):
        """Test parsing of Arris CM820B system info."""
        parser = ArrisCM820BParser()
        soup = BeautifulSoup(arris_cm820b_status_html, "html.parser")
        data = parser.parse(soup)

        # Verify system info exists
        assert "system_info" in data
        assert isinstance(data["system_info"], dict)
        assert data["system_info"]["system_uptime"] == "6 d:  2 h: 33  m"


class TestCM820BEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_html_returns_empty_channels(self):
        """Test parsing empty HTML returns empty lists."""
        parser = ArrisCM820BParser()
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        data = parser.parse(soup)

        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}

    def test_no_downstream_table_returns_empty(self):
        """Test parsing HTML without downstream table returns empty list."""
        parser = ArrisCM820BParser()
        html = "<html><body><table><tr><td>Some other data</td></tr></table></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        assert data["downstream"] == []

    def test_no_upstream_table_returns_empty(self):
        """Test parsing HTML without upstream table returns empty list."""
        parser = ArrisCM820BParser()
        html = "<html><body><table><tr><td>Some other data</td></tr></table></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        assert data["upstream"] == []

    def test_malformed_table_handled_gracefully(self):
        """Test that malformed tables don't crash the parser."""
        parser = ArrisCM820BParser()
        # Table with Downstream 1 but incomplete rows
        html = """
        <html><body>
        <table>
            <tr><td>Downstream 1</td></tr>
        </table>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        # Should return empty list, not crash
        assert data["downstream"] == []

    def test_missing_uptime_handled_gracefully(self):
        """Test that missing uptime doesn't crash the parser."""
        parser = ArrisCM820BParser()
        html = "<html><body><table><tr><td>No uptime here</td></tr></table></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        system_info = parser._parse_system_info(soup)

        assert system_info == {}

    def test_detection_rejects_non_cm820b(self):
        """Test that HintMatcher rejects non-CM820B modems."""
        html = "<html><body>Some random modem page</body></html>"
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(html)
        assert not any(m.parser_name == "ArrisCM820BParser" for m in matches)
