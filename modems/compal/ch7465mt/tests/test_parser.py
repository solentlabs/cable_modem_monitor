"""Tests for Compal CH7465MT parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from custom_components.cable_modem_monitor.modems.compal.ch7465mt.parser import (
    CompalCH7465MTParser,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def parser():
    """Create parser instance."""
    return CompalCH7465MTParser()


@pytest.fixture
def resources():
    """Load all XML fixtures as a resources dict."""
    fixture_map = {
        "fun=1": "fun1_global_settings.xml",
        "fun=2": "fun2_system_info.xml",
        "fun=10": "fun10_downstream.xml",
        "fun=11": "fun11_upstream.xml",
        "fun=144": "fun144_cm_status.xml",
    }
    result = {}
    for key, filename in fixture_map.items():
        filepath = FIXTURES_DIR / filename
        if filepath.exists():
            result[key] = filepath.read_text()
    return result


class TestCompalCH7465MTParser:
    """Tests for the Compal CH7465MT XML parser."""

    def test_parse_returns_required_keys(self, parser, resources):
        """Parser must return downstream, upstream, and system_info."""
        result = parser.parse_resources(resources)
        assert "downstream" in result
        assert "upstream" in result
        assert "system_info" in result

    def test_downstream_channel_count(self, parser, resources):
        """Should parse 24 downstream channels."""
        result = parser.parse_resources(resources)
        assert len(result["downstream"]) == 24

    def test_downstream_channel_fields(self, parser, resources):
        """Each downstream channel should have required fields."""
        result = parser.parse_resources(resources)
        for channel in result["downstream"]:
            assert "channel_id" in channel
            assert "frequency" in channel
            assert "power" in channel
            assert "snr" in channel
            assert "modulation" in channel
            assert "channel_type" in channel
            assert channel["channel_type"] == "qam"

    def test_downstream_first_channel_values(self, parser, resources):
        """Verify values of a known downstream channel."""
        result = parser.parse_resources(resources)
        # Find channel with chid=1 (602 MHz)
        ch1 = next(c for c in result["downstream"] if c["channel_id"] == 1)
        assert ch1["frequency"] == 602000000
        assert ch1["power"] == 8.0
        assert ch1["snr"] == 37.0
        assert ch1["modulation"] == "256QAM"
        assert ch1["lock_status"] == "Locked"

    def test_downstream_error_counters(self, parser, resources):
        """Downstream channels should have corrected/uncorrected error counts."""
        result = parser.parse_resources(resources)
        ch1 = next(c for c in result["downstream"] if c["channel_id"] == 1)
        assert "corrected" in ch1
        assert "uncorrected" in ch1
        assert isinstance(ch1["corrected"], int)
        assert isinstance(ch1["uncorrected"], int)

    def test_upstream_channel_count(self, parser, resources):
        """Should parse 8 upstream channels."""
        result = parser.parse_resources(resources)
        assert len(result["upstream"]) == 8

    def test_upstream_channel_fields(self, parser, resources):
        """Each upstream channel should have required fields."""
        result = parser.parse_resources(resources)
        for channel in result["upstream"]:
            assert "channel_id" in channel
            assert "frequency" in channel
            assert "power" in channel
            assert "modulation" in channel
            assert "channel_type" in channel
            assert channel["channel_type"] == "atdma"

    def test_upstream_channel_values(self, parser, resources):
        """Verify values of a known upstream channel."""
        result = parser.parse_resources(resources)
        # Find channel with usid=1 (81.7 MHz, 64QAM)
        ch1 = next(c for c in result["upstream"] if c["channel_id"] == 1)
        assert ch1["frequency"] == 81700000
        assert ch1["power"] == 38.0
        assert ch1["modulation"] == "64QAM"

    def test_system_info_software_version(self, parser, resources):
        """Should extract software version from fun=1."""
        result = parser.parse_resources(resources)
        assert result["system_info"]["software_version"] == "CH7465MT-AT-NCIP-6.15.32p3TM-GA-NOSH"

    def test_system_info_hardware_version(self, parser, resources):
        """Should extract hardware version from fun=2."""
        result = parser.parse_resources(resources)
        assert result["system_info"]["hardware_version"] == "5.01"

    def test_system_info_uptime(self, parser, resources):
        """Should extract uptime from fun=2."""
        result = parser.parse_resources(resources)
        assert "system_uptime" in result["system_info"]
        assert "day" in result["system_info"]["system_uptime"]

    def test_system_info_docsis_mode(self, parser, resources):
        """Should extract DOCSIS mode from fun=2."""
        result = parser.parse_resources(resources)
        assert result["system_info"]["docsis_mode"] == "DOCSIS 3.0"

    def test_system_info_provisioning(self, parser, resources):
        """Should extract provisioning status from fun=144."""
        result = parser.parse_resources(resources)
        assert result["system_info"]["provisioning_status"] == "Modem Mode"
        assert result["system_info"]["connectivity_status"] == "Operational"

    def test_empty_resources(self, parser):
        """Parser should handle empty resources gracefully."""
        result = parser.parse_resources({})
        assert result["downstream"] == []
        assert result["upstream"] == []
        assert result["system_info"] == {}

    def test_partial_resources(self, parser, resources):
        """Parser should handle partial resources (only downstream)."""
        partial = {"fun=10": resources["fun=10"]}
        result = parser.parse_resources(partial)
        assert len(result["downstream"]) == 24
        assert result["upstream"] == []

    def test_normalize_modulation(self, parser):
        """Modulation strings should be normalized to uppercase."""
        assert parser._normalize_modulation("256qam") == "256QAM"
        assert parser._normalize_modulation("16qam") == "16QAM"
        assert parser._normalize_modulation("64qam") == "64QAM"
        assert parser._normalize_modulation("") == ""
