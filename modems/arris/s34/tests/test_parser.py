"""Tests for the Arris/CommScope S34 parser.

The S34 uses HNAP protocol like the S33, with key differences:
- Authentication: Uses HMAC-SHA256 (vs S33's HMAC-MD5)
- Firmware pattern: AT01.01.* (vs S33's TB01.03.*)

Channel data format is caret-delimited (same as S33).

Fixtures contributed by @rplancha (PR #90).
"""

from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemCapability
from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher
from custom_components.cable_modem_monitor.modems.arris.s34.parser import ArrisS34HnapParser
from tests.fixtures import load_fixture


@pytest.fixture
def s34_login_html():
    """Load S34 Login.html fixture."""
    return load_fixture("arris", "s34", "Login.html")


@pytest.fixture
def s34_device_status_response():
    """Load S34 hnap_device_status.json fixture."""
    import json

    content = load_fixture("arris", "s34", "hnap_device_status.json")
    return json.loads(content)


@pytest.fixture
def s34_downstream_response():
    """Load S34 hnap_downstream_channels.json fixture."""
    import json

    content = load_fixture("arris", "s34", "hnap_downstream_channels.json")
    return json.loads(content)


@pytest.fixture
def s34_upstream_response():
    """Load S34 hnap_upstream_channels.json fixture."""
    import json

    content = load_fixture("arris", "s34", "hnap_upstream_channels.json")
    return json.loads(content)


@pytest.fixture
def sample_downstream_hnap_response():
    """Sample HNAP downstream channel response matching S34 format."""
    return {
        "GetCustomerStatusDownstreamChannelInfoResponse": {
            "CustomerConnDownstreamChannel": (
                "1^Locked^256QAM^17^483000000^ 7.3^39.0^34^0^|+|"
                "2^Not Locked^Unknown^0^0^-60.0^ 7.3^0^0^|+|"  # channel_id=0, should skip
                "3^Locked^256QAM^14^465000000^ 7.6^39.0^4^0^"
            ),
            "GetCustomerStatusDownstreamChannelInfoResult": "OK",
        }
    }


@pytest.fixture
def sample_upstream_hnap_response():
    """Sample HNAP upstream channel response matching S34 format."""
    return {
        "GetCustomerStatusUpstreamChannelInfoResponse": {
            "CustomerConnUpstreamChannel": (
                "1^Locked^SC-QAM^3^6400000^22800000^37.8^|+|"
                "2^Not Locked^Unknown^0^0^0^-inf^|+|"  # channel_id=0, should skip
                "3^Locked^SC-QAM^6^3200000^40400000^38.0^"
            ),
            "GetCustomerStatusUpstreamChannelInfoResult": "OK",
        }
    }


@pytest.fixture
def sample_device_status_response():
    """Sample HNAP device status response for S34."""
    return {
        "GetArrisDeviceStatusResponse": {
            "FirmwareVersion": "AT01.01.010.042324_S3.04.735",
            "InternetConnection": "Connected",
            "DownstreamFrequency": "483000000 Hz",
            "StatusSoftwareModelName": "S34",
            "GetArrisDeviceStatusResult": "OK",
        }
    }


@pytest.fixture
def mock_hnap_builder():
    """Mock HNAP builder that returns empty response for API calls."""
    builder = MagicMock()
    builder.call_multiple.return_value = [{}, {}, {}, {}, {}]
    return builder


class TestS34ParserMetadata:
    """Test parser metadata from modem.yaml."""

    def test_parser_class_name(self):
        """Test parser class name is correct."""
        assert ArrisS34HnapParser.__name__ == "ArrisS34HnapParser"

    def test_parser_manufacturer(self):
        """Test manufacturer from modem.yaml."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("ArrisS34HnapParser")
        assert adapter is not None
        config = adapter.get_modem_config_dict()
        assert config["manufacturer"] == "Arris/CommScope"

    def test_parser_model(self):
        """Test model from modem.yaml."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("ArrisS34HnapParser")
        assert adapter is not None
        config = adapter.get_modem_config_dict()
        assert config["model"] == "S34"

    def test_docsis_version(self):
        """Test DOCSIS version is 3.1."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("ArrisS34HnapParser")
        assert adapter is not None
        assert adapter.get_docsis_version() == "3.1"

    def test_awaiting_verification_status(self):
        """Test parser is awaiting verification (not yet verified by user)."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("ArrisS34HnapParser")
        assert adapter is not None
        assert adapter.get_status() == "awaiting_verification"

    def test_fixtures_path(self):
        """Test fixtures path is set via modem.yaml adapter."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("ArrisS34HnapParser")
        assert adapter is not None
        assert adapter.get_fixtures_path() == "modems/arris/s34/fixtures"


class TestS34HmacAlgorithm:
    """Test S34 uses SHA256 HMAC (key difference from S33)."""

    def test_hmac_algorithm_sha256(self):
        """Test S34 modem.yaml specifies hmac_algorithm: sha256."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("ArrisS34HnapParser")
        assert adapter is not None
        hints = adapter.get_hnap_hints()
        assert hints is not None
        assert hints["hmac_algorithm"] == "sha256"

    def test_s33_uses_md5_for_comparison(self):
        """Verify S33 uses md5 (to confirm S34 is different)."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("ArrisS33HnapParser")
        assert adapter is not None
        hints = adapter.get_hnap_hints()
        assert hints is not None
        assert hints["hmac_algorithm"] == "md5"


class TestS34ParserCapabilities:
    """Test parser capabilities declaration."""

    def test_has_downstream_capability(self):
        """Test downstream channels capability."""
        assert ArrisS34HnapParser.has_capability(ModemCapability.SCQAM_DOWNSTREAM)

    def test_has_upstream_capability(self):
        """Test upstream channels capability."""
        assert ArrisS34HnapParser.has_capability(ModemCapability.SCQAM_UPSTREAM)

    def test_no_uptime_capability(self):
        """Test S34 does NOT have uptime capability (same as S33)."""
        assert not ArrisS34HnapParser.has_capability(ModemCapability.SYSTEM_UPTIME)

    def test_has_version_capability(self):
        """Test software version capability."""
        assert ArrisS34HnapParser.has_capability(ModemCapability.SOFTWARE_VERSION)

    def test_has_restart_action(self):
        """Test that restart is supported via ActionFactory."""
        from custom_components.cable_modem_monitor.core.actions import ActionFactory
        from custom_components.cable_modem_monitor.core.actions.base import ActionType
        from custom_components.cable_modem_monitor.modem_config import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("ArrisS34HnapParser")
        assert adapter is not None, "S34 should have modem.yaml config"
        modem_config = adapter.get_modem_config_dict()
        assert ActionFactory.supports(ActionType.RESTART, modem_config)


class TestS34ParserDetection:
    """Test parser detection logic."""

    def test_detection_with_s34_model(self, s34_login_html):
        """Test detection via S34 model string using HintMatcher."""
        html_with_model = s34_login_html + "<!-- S34 -->"
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(html_with_model)
        assert any(m.parser_name == "ArrisS34HnapParser" for m in matches)

    def test_detection_with_arris_and_hnap(self, s34_login_html):
        """Test detection via ARRIS + HNAP markers using HintMatcher."""
        if "ARRIS" in s34_login_html and "purenetworks.com/HNAP1" in s34_login_html:
            hint_matcher = HintMatcher.get_instance()
            matches = hint_matcher.match_login_markers(s34_login_html)
            assert any(m.parser_name == "ArrisS34HnapParser" for m in matches)

    def test_detection_with_commscope_and_hnap(self):
        """Test detection via CommScope + HNAP markers using HintMatcher."""
        html = "<html><body>CommScope purenetworks.com/HNAP1 S34</body></html>"
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(html)
        assert any(m.parser_name == "ArrisS34HnapParser" for m in matches)

    def test_cannot_parse_generic_html(self):
        """Test that generic HTML is not detected as S34."""
        html = "<html><body>Hello World</body></html>"
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(html)
        assert not any(m.parser_name == "ArrisS34HnapParser" for m in matches)


class TestS34ParseResources:
    """Test parse_resources method."""

    def test_returns_empty_without_hnap_response(self):
        """Test that parse_resources returns empty data without hnap_response."""
        parser = ArrisS34HnapParser()
        result = parser.parse_resources({"/": BeautifulSoup("<html></html>", "html.parser")})

        assert result["downstream"] == []
        assert result["upstream"] == []

    def test_parses_hnap_response(self, sample_downstream_hnap_response):
        """Test that parse_resources uses hnap_response from resources."""
        parser = ArrisS34HnapParser()

        resources = {
            "hnap_response": sample_downstream_hnap_response,
            "/": BeautifulSoup("<html></html>", "html.parser"),
        }

        result = parser.parse_resources(resources)

        assert "downstream" in result
        assert "upstream" in result
        assert "system_info" in result
        # Should have 2 channels (channel_id=0 filtered out)
        assert len(result["downstream"]) == 2


class TestS34DownstreamParsing:
    """Test downstream channel parsing from HNAP responses."""

    def test_parse_downstream_channels(self, sample_downstream_hnap_response):
        """Test parsing downstream channels from HNAP data."""
        parser = ArrisS34HnapParser()
        channels = parser._parse_downstream_from_hnap(sample_downstream_hnap_response)

        # Should have 2 channels (channel_id=0 filtered out)
        assert len(channels) == 2

        # Check first channel
        ch1 = channels[0]
        assert ch1["channel_id"] == 17
        assert ch1["lock_status"] == "Locked"
        assert ch1["modulation"] == "256QAM"
        assert ch1["channel_type"] == "qam"
        assert ch1["frequency"] == 483000000
        assert ch1["power"] == 7.3
        assert ch1["snr"] == 39.0
        assert ch1["corrected"] == 34
        assert ch1["uncorrected"] == 0

    def test_skips_channel_id_zero(self, sample_downstream_hnap_response):
        """Test that placeholder channels with channel_id=0 are skipped."""
        parser = ArrisS34HnapParser()
        channels = parser._parse_downstream_from_hnap(sample_downstream_hnap_response)

        # No channel should have channel_id=0
        assert all(ch["channel_id"] != 0 for ch in channels)

    def test_parse_downstream_ofdm_channel_type(self):
        """Test that OFDM modulation strings derive channel_type='ofdm'."""
        parser = ArrisS34HnapParser()
        response = {
            "GetCustomerStatusDownstreamChannelInfoResponse": {
                "CustomerConnDownstreamChannel": (
                    "1^Locked^OFDM PLC^25^690000000^ 4.7^40.0^100^0|+|" "2^Locked^256QAM^17^483000000^ 7.3^39.0^34^0"
                )
            }
        }
        channels = parser._parse_downstream_from_hnap(response)

        assert len(channels) == 2
        assert channels[0]["modulation"] == "OFDM PLC"
        assert channels[0]["channel_type"] == "ofdm"
        assert channels[1]["modulation"] == "256QAM"
        assert channels[1]["channel_type"] == "qam"

    def test_parse_downstream_from_fixture(self, s34_downstream_response):
        """Test parsing downstream channels from actual PR #90 fixture."""
        parser = ArrisS34HnapParser()
        channels = parser._parse_downstream_from_hnap(s34_downstream_response)

        # Fixture has 34 entries, 2 with channel_id=0
        assert len(channels) == 32

        # Check OFDM channel (last one in fixture)
        ofdm_channels = [ch for ch in channels if ch["channel_type"] == "ofdm"]
        assert len(ofdm_channels) == 1
        assert ofdm_channels[0]["channel_id"] == 25
        assert ofdm_channels[0]["modulation"] == "OFDM PLC"

    def test_parse_downstream_empty(self):
        """Test parsing empty downstream data."""
        parser = ArrisS34HnapParser()
        empty_response = {"GetCustomerStatusDownstreamChannelInfoResponse": {"CustomerConnDownstreamChannel": ""}}
        channels = parser._parse_downstream_from_hnap(empty_response)
        assert channels == []

    def test_parse_downstream_missing_key(self):
        """Test parsing when response key is missing."""
        parser = ArrisS34HnapParser()
        channels = parser._parse_downstream_from_hnap({})
        assert channels == []


class TestS34UpstreamParsing:
    """Test upstream channel parsing from HNAP responses."""

    def test_parse_upstream_channels(self, sample_upstream_hnap_response):
        """Test parsing upstream channels from HNAP data."""
        parser = ArrisS34HnapParser()
        channels = parser._parse_upstream_from_hnap(sample_upstream_hnap_response)

        # Should have 2 channels (channel_id=0 filtered out)
        assert len(channels) == 2

        # Check first channel
        ch1 = channels[0]
        assert ch1["channel_id"] == 3
        assert ch1["lock_status"] == "Locked"
        assert ch1["modulation"] == "SC-QAM"
        assert ch1["channel_type"] == "atdma"
        assert ch1["symbol_rate"] == "6400000"
        assert ch1["frequency"] == 22800000
        assert ch1["power"] == 37.8

    def test_skips_channel_id_zero(self, sample_upstream_hnap_response):
        """Test that placeholder channels with channel_id=0 are skipped."""
        parser = ArrisS34HnapParser()
        channels = parser._parse_upstream_from_hnap(sample_upstream_hnap_response)

        # No channel should have channel_id=0
        assert all(ch["channel_id"] != 0 for ch in channels)

    def test_parse_upstream_from_fixture(self, s34_upstream_response):
        """Test parsing upstream channels from actual PR #90 fixture."""
        parser = ArrisS34HnapParser()
        channels = parser._parse_upstream_from_hnap(s34_upstream_response)

        # Fixture has 10 entries, 5 with channel_id=0
        assert len(channels) == 5

        # All should be SC-QAM (no OFDMA in this fixture)
        assert all(ch["channel_type"] == "atdma" for ch in channels)

    def test_parse_upstream_empty(self):
        """Test parsing empty upstream data."""
        parser = ArrisS34HnapParser()
        empty_response = {"GetCustomerStatusUpstreamChannelInfoResponse": {"CustomerConnUpstreamChannel": ""}}
        channels = parser._parse_upstream_from_hnap(empty_response)
        assert channels == []


class TestS34SystemInfoParsing:
    """Test system info parsing from HNAP responses."""

    def test_parse_device_status(self, sample_device_status_response):
        """Test parsing device status from HNAP data."""
        parser = ArrisS34HnapParser()
        system_info = parser._parse_system_info_from_hnap(sample_device_status_response)

        assert system_info["software_version"] == "AT01.01.010.042324_S3.04.735"
        assert system_info["internet_connection"] == "Connected"

    def test_parse_device_status_from_fixture(self, s34_device_status_response):
        """Test parsing device status from actual PR #90 fixture."""
        parser = ArrisS34HnapParser()
        system_info = parser._parse_system_info_from_hnap(s34_device_status_response)

        assert "software_version" in system_info
        # Fixture firmware: AT01.01.010.042324_S3.04.735
        assert "AT01.01" in system_info["software_version"]


class TestS34HnapHints:
    """Test HNAP hints configuration from modem.yaml."""

    def test_hnap_hints_endpoint(self):
        """Test HNAP endpoint is correct."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("ArrisS34HnapParser")
        assert adapter is not None
        hints = adapter.get_hnap_hints()
        assert hints is not None
        assert hints["endpoint"] == "/HNAP1/"

    def test_hnap_hints_namespace(self):
        """Test HNAP namespace matches standard."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("ArrisS34HnapParser")
        assert adapter is not None
        hints = adapter.get_hnap_hints()
        assert hints is not None
        assert hints["namespace"] == "http://purenetworks.com/HNAP1/"

    def test_hnap_hints_empty_action_value(self):
        """Test S34 uses empty string for action values (same as S33)."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("ArrisS34HnapParser")
        assert adapter is not None
        hints = adapter.get_hnap_hints()
        assert hints is not None
        assert hints["empty_action_value"] == ""


class TestS34UrlPatterns:
    """Test URL patterns configuration from modem.yaml."""

    def test_has_url_patterns(self):
        """Test S34 has URL patterns in modem.yaml."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_url_patterns_for_parser

        patterns = get_url_patterns_for_parser("ArrisS34HnapParser")
        assert patterns is not None, "S34 should have URL patterns in modem.yaml"
        assert len(patterns) > 0

    def test_public_page_exists(self):
        """Test S34 has a public (no auth) page for detection."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_url_patterns_for_parser

        patterns = get_url_patterns_for_parser("ArrisS34HnapParser")
        assert patterns is not None
        public_patterns = [p for p in patterns if not p.get("auth_required", True)]
        assert len(public_patterns) > 0, "S34 should have at least one public page"
