"""Tests for the Motorola MB8611 parser using HNAP protocol.

Note: Legacy parse(soup, session, base_url) tests removed in v3.13.0.
Parsing is now done via parse_resources() with data provided by HNAPLoader.
Restart functionality moved to action layer - see tests/core/actions/test_hnap.py.
"""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher
from modems.motorola.mb8611.parser import (
    MotorolaMB8611HnapParser,
)
from tests.fixtures import get_fixture_path, load_fixture


@pytest.fixture
def hnap_full_status():
    """Load hnap_full_status.json fixture."""
    path = get_fixture_path("motorola", "mb8611", "hnap_full_status.json")
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def login_html():
    """Load Login.html fixture."""
    return load_fixture("motorola", "mb8611", "Login.html")


class TestDetection:
    """Test modem detection via HintMatcher.

    HintMatcher has two phases:
    - Phase 1 (login_markers): Pre-auth detection using HNAP markers
    - Phase 2 (model_strings): Post-auth detection using model identifiers

    MB8611 login_markers: HNAP, purenetworks.com/HNAP1, SOAPAction, /Login.html
    MB8611 model_strings: MB8611, MB 8611, 2251-MB8611, MB8612
    """

    def test_from_model_name_phase2(self):
        """Test Phase 2 detection from MB8611 model string."""
        html = "<html><body>Motorola MB8611 Cable Modem</body></html>"
        hint_matcher = HintMatcher.get_instance()
        # Model strings are matched in Phase 2 (post-auth detection)
        matches = hint_matcher.match_model_strings(html)
        assert any(m.parser_name == "MotorolaMB8611HnapParser" for m in matches)

    def test_from_model_number_with_spaces_phase2(self):
        """Test Phase 2 detection from model number with spaces."""
        html = "<html><body>Motorola MB 8611</body></html>"
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_model_strings(html)
        assert any(m.parser_name == "MotorolaMB8611HnapParser" for m in matches)

    def test_from_serial_number_phase2(self):
        """Test Phase 2 detection from serial number format."""
        html = "<html><body>Serial: 2251-MB8611-30-1526</body></html>"
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_model_strings(html)
        assert any(m.parser_name == "MotorolaMB8611HnapParser" for m in matches)

    def test_from_hnap_markers_phase1(self):
        """Test Phase 1 detection from HNAP login markers."""
        # HTML with HNAP markers (visible on login page)
        html = '<html><body><script src="/HNAP1/">HNAP purenetworks.com/HNAP1</script></body></html>'
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(html)
        assert any(m.parser_name == "MotorolaMB8611HnapParser" for m in matches)

    def test_rejects_other_modems(self):
        """Test that other modems are not detected via HintMatcher."""
        html = "<html><body>Arris SB6190</body></html>"
        hint_matcher = HintMatcher.get_instance()
        # Should not match Phase 1 (no HNAP markers)
        login_matches = hint_matcher.match_login_markers(html)
        assert not any(m.parser_name == "MotorolaMB8611HnapParser" for m in login_matches)
        # Should not match Phase 2 (no MB8611 model strings)
        model_matches = hint_matcher.match_model_strings(html)
        assert not any(m.parser_name == "MotorolaMB8611HnapParser" for m in model_matches)

    def test_hnap_markers_identify_multiple_hnap_parsers(self):
        """Test that HNAP markers alone may match multiple HNAP parsers.

        Both MB8611 and S33 use HNAP markers, so Phase 1 detection
        alone cannot distinguish between them. Phase 2 model strings
        provide the disambiguation.
        """
        html = "<html><body>HNAP purenetworks.com/HNAP1</body></html>"
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(html)
        # HNAP markers may match multiple parsers
        parser_names = [m.parser_name for m in matches]
        # MB8611 should be in the matches
        assert "MotorolaMB8611HnapParser" in parser_names


class TestHnapHints:
    """Test HNAP hints configuration from modem.yaml (v3.12.0+)."""

    def test_has_hnap_hints(self):
        """Test that MB8611 has HNAP hints in modem.yaml."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("MotorolaMB8611HnapParser")
        assert adapter is not None
        hints = adapter.get_hnap_hints()
        assert hints is not None
        assert hints["endpoint"] == "/HNAP1/"
        assert hints["namespace"] == "http://purenetworks.com/HNAP1/"
        assert hints["empty_action_value"] == ""  # Verified from HAR capture

    def test_url_patterns_from_modem_yaml(self):
        """Test that MB8611 has URL patterns in modem.yaml."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_url_patterns_for_parser

        url_patterns = get_url_patterns_for_parser("MotorolaMB8611HnapParser")
        assert url_patterns is not None, "MB8611 should have URL patterns in modem.yaml"
        assert len(url_patterns) > 0

        # Protected pages should require HNAP auth
        protected_patterns = [p for p in url_patterns if p.get("auth_required", True)]
        assert len(protected_patterns) > 0, "MB8611 should have protected pages"
        for pattern in protected_patterns:
            assert pattern["auth_method"] == "hnap"

        # Should have some public pages for detection
        public_patterns = [p for p in url_patterns if not p.get("auth_required", True)]
        assert len(public_patterns) > 0, "MB8611 should have public pages for detection"


class TestHnapParsing:
    """Test HNAP data parsing."""

    def test_returns_empty_without_hnap_builder(self):
        """Test that parse_resources returns empty data without hnap_builder."""
        parser = MotorolaMB8611HnapParser()

        # No hnap_builder in resources - parser returns empty data
        result = parser.parse_resources({"/": BeautifulSoup("<html></html>", "html.parser")})

        assert result["downstream"] == []
        assert result["upstream"] == []

    def test_uses_hnap_builder_from_resources(self):
        """Test that parse_resources uses hnap_builder from resources."""
        parser = MotorolaMB8611HnapParser()
        mock_builder = Mock()
        mock_builder.call_multiple.return_value = [{}, {}, {}, {}, {}]

        resources = {
            "hnap_builder": mock_builder,
            "/": BeautifulSoup("<html></html>", "html.parser"),
        }

        # Should work without raising - builder is available
        result = parser.parse_resources(resources)

        # Result has structure (actual parsing tested in other tests)
        assert "downstream" in result
        assert "upstream" in result
        assert "system_info" in result

    def test_downstream_channels_from_hnap_response(self, hnap_full_status):
        """Test parsing of downstream channels from HNAP response dict."""
        parser = MotorolaMB8611HnapParser()

        # Extract inner data from GetMultipleHNAPsResponse wrapper
        inner_data = hnap_full_status.get("GetMultipleHNAPsResponse", {})
        channels = parser._parse_downstream_from_hnap(inner_data)

        # Verify downstream channels
        assert len(channels) == 33  # 32 QAM256 + 1 OFDM PLC

        # Check first channel (DOCSIS Channel ID 20)
        first_channel = channels[0]
        assert first_channel["channel_id"] == 20  # DOCSIS Channel ID
        assert first_channel["lock_status"] == "Locked"
        assert first_channel["modulation"] == "QAM256"
        assert first_channel["channel_type"] == "qam"  # Derived from modulation
        assert first_channel["frequency"] == 543_000_000  # 543.0 MHz
        assert first_channel["power"] == 1.4
        assert first_channel["snr"] == 45.1
        assert first_channel["corrected"] == 41
        assert first_channel["uncorrected"] == 0

        # Check OFDM PLC channel (last channel, DOCSIS Channel ID 193)
        ofdm_channel = channels[32]
        assert ofdm_channel["channel_id"] == 193  # DOCSIS Channel ID
        assert ofdm_channel["modulation"] == "OFDM PLC"
        assert ofdm_channel["channel_type"] == "ofdm"  # Derived from modulation (issue #87)
        assert ofdm_channel["frequency"] == 957_000_000  # 957.0 MHz
        assert ofdm_channel["power"] == -4.1
        assert ofdm_channel["snr"] == 41.1
        assert ofdm_channel["corrected"] == 936482395
        assert ofdm_channel["uncorrected"] == 23115

    def test_upstream_channels_from_hnap_response(self, hnap_full_status):
        """Test parsing of upstream channels from HNAP response dict."""
        parser = MotorolaMB8611HnapParser()

        # Extract inner data from GetMultipleHNAPsResponse wrapper
        inner_data = hnap_full_status.get("GetMultipleHNAPsResponse", {})
        channels = parser._parse_upstream_from_hnap(inner_data)

        # Verify upstream channels
        assert len(channels) == 4

        # Check first channel (DOCSIS Channel ID 17)
        first_channel = channels[0]
        assert first_channel["channel_id"] == 17  # DOCSIS Channel ID
        assert first_channel["lock_status"] == "Locked"
        assert first_channel["modulation"] == "SC-QAM"
        assert first_channel["channel_type"] == "atdma"  # Derived from modulation
        assert first_channel["symbol_rate"] == 5120
        # 16.4 MHz converted to Hz - account for floating-point precision
        assert abs(first_channel["frequency"] - 16_400_000) <= 1
        assert first_channel["power"] == 44.3

        # Check last channel (DOCSIS Channel ID 20)
        last_channel = channels[3]
        assert last_channel["channel_id"] == 20  # DOCSIS Channel ID
        assert last_channel["lock_status"] == "Locked"
        assert last_channel["modulation"] == "SC-QAM"
        assert last_channel["channel_type"] == "atdma"  # Derived from modulation
        # 35.6 MHz converted to Hz - account for floating-point precision
        assert abs(last_channel["frequency"] - 35_600_000) <= 1
        assert last_channel["power"] == 45.5

    def test_system_info_from_hnap_response(self, hnap_full_status):
        """Test parsing of system info from HNAP response dict."""
        parser = MotorolaMB8611HnapParser()

        # Extract inner data from GetMultipleHNAPsResponse wrapper
        inner_data = hnap_full_status.get("GetMultipleHNAPsResponse", {})
        system_info = parser._parse_system_info_from_hnap(inner_data)

        # Check uptime
        assert system_info["system_uptime"] == "47 days 21h:15m:38s"

        # Check network access
        assert system_info["network_access"] == "Allowed"

        # Check connectivity status
        assert system_info["connectivity_status"] == "OK"

        # Check boot status
        assert system_info["boot_status"] == "OK"

        # Check security
        assert system_info["security_status"] == "Enabled"
        assert system_info["security_comment"] == "BPI+"

        # Check downstream frequency
        assert system_info["downstream_frequency"] == "543000000 Hz"


class TestEdgeCases:
    """Test edge cases and error handling with internal parsing methods.

    Note: Legacy parse() with session tests removed in v3.13.0.
    Error handling for HNAP responses now tested via parse_resources() path.
    """

    def test_empty_downstream_data(self):
        """Test downstream parsing with empty HNAP data."""
        parser = MotorolaMB8611HnapParser()
        hnap_data: dict = {}

        channels = parser._parse_downstream_from_hnap(hnap_data)

        assert channels == []

    def test_empty_upstream_data(self):
        """Test upstream parsing with empty HNAP data."""
        parser = MotorolaMB8611HnapParser()
        hnap_data: dict = {}

        channels = parser._parse_upstream_from_hnap(hnap_data)

        assert channels == []

    def test_empty_system_info_data(self):
        """Test system info parsing with empty HNAP data."""
        parser = MotorolaMB8611HnapParser()
        hnap_data: dict = {}

        system_info = parser._parse_system_info_from_hnap(hnap_data)

        assert system_info == {}


class TestMetadata:
    """Test parser metadata."""

    def test_name(self):
        """Test parser name."""
        parser = MotorolaMB8611HnapParser()
        assert parser.name == "Motorola MB8611"

    def test_manufacturer(self):
        """Test parser manufacturer."""
        parser = MotorolaMB8611HnapParser()
        assert parser.manufacturer == "Motorola"

    def test_models(self):
        """Test parser supported models."""
        parser = MotorolaMB8611HnapParser()
        assert "MB8611" in parser.models
        assert "MB8612" in parser.models

    def test_ofdm_capability(self):
        """Test that OFDM_DOWNSTREAM capability is declared.

        The MB8611 returns OFDM channels (modulation="OFDM PLC") in the same
        MotoConnDownstreamChannel response as QAM channels. The fixture shows
        channel 33 with modulation "OFDM PLC" at 957 MHz.
        """
        from custom_components.cable_modem_monitor.core.base_parser import ModemCapability

        parser = MotorolaMB8611HnapParser()
        assert ModemCapability.OFDM_DOWNSTREAM in parser.capabilities


class TestSoftwareVersionParsing:
    """Test software version parsing from GetMotoStatusSoftware.

    Note: Legacy parse() with session tests removed in v3.13.0.
    Software version parsing now tested via parse_resources() path.
    """

    def test_software_info_with_empty_response(self):
        """Test software info parsing with empty GetMotoStatusSoftwareResponse."""
        parser = MotorolaMB8611HnapParser()
        hnap_data: dict = {}

        system_info: dict = {}
        parser._extract_software_info(hnap_data, system_info)

        # Should not add any keys
        assert "software_version" not in system_info
        assert "docsis_version" not in system_info
        assert "serial_number" not in system_info

    def test_software_version_capability(self):
        """Test that SOFTWARE_VERSION capability is declared."""
        from custom_components.cable_modem_monitor.core.base_parser import ModemCapability

        parser = MotorolaMB8611HnapParser()
        assert ModemCapability.SOFTWARE_VERSION in parser.capabilities


class TestRestartCapability:
    """Test modem restart capability is declared.

    Note: Restart functionality moved to action layer in v3.13.0.
    See tests/core/actions/test_hnap.py for restart action tests.
    """

    def test_restart_action_configured(self):
        """Test that restart action is configured in modem.yaml."""
        from custom_components.cable_modem_monitor.core.actions import ActionFactory
        from custom_components.cable_modem_monitor.core.actions.base import ActionType
        from custom_components.cable_modem_monitor.modem_config import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("MotorolaMB8611HnapParser")
        assert adapter is not None, "MB8611 should have modem.yaml config"
        modem_config = adapter.get_modem_config_dict()
        assert ActionFactory.supports(ActionType.RESTART, modem_config)
