"""Tests for the Arris/CommScope S34 parser.

The S34 uses HNAP protocol like the S33, but with key differences:
- Response format is pure JSON (not caret-delimited like S33)
- Firmware pattern: AT01.01.* (vs S33's TB01.03.*)

MVP scope: System info only (firmware, model, connection status).
Channel data will be added in Phase 4.
"""

import json
import os

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.arris.s34 import ArrisS34HnapParser
from custom_components.cable_modem_monitor.parsers.base_parser import ModemCapability, ParserStatus

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def s34_login_html():
    """Load S34 Login.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "s34", "Login.html")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def s34_device_status_response():
    """Load S34 GetArrisDeviceStatus response fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "s34", "hnap_device_status.json")
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def sample_device_status_response():
    """Sample HNAP device status response for S34 (inline for quick tests)."""
    return {
        "GetArrisDeviceStatusResponse": {
            "FirmwareVersion": "AT01.01.010.042324_S3.04.735",
            "InternetConnection": "Connected",
            "DownstreamFrequency": "483000000 Hz",
            "StatusSoftwareModelName": "S34",
            "StatusSoftwareModelName2": "S34",
            "GetArrisDeviceStatusResult": "OK",
        }
    }


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestS34ParserMetadata:
    """Test parser metadata and class attributes."""

    def test_parser_name(self):
        """Test parser name is correct."""
        assert ArrisS34HnapParser.name == "Arris S34"

    def test_parser_manufacturer(self):
        """Test manufacturer is correct."""
        assert ArrisS34HnapParser.manufacturer == "Arris/CommScope"

    def test_parser_models(self):
        """Test model list includes S34 variants."""
        assert "S34" in ArrisS34HnapParser.models
        assert "CommScope S34" in ArrisS34HnapParser.models
        assert "ARRIS S34" in ArrisS34HnapParser.models

    def test_parser_priority(self):
        """Test priority is high (HNAP API method)."""
        # S34 should have same or higher priority than S33 (101)
        assert ArrisS34HnapParser.priority >= 100

    def test_docsis_version(self):
        """Test DOCSIS version is 3.1."""
        assert ArrisS34HnapParser.docsis_version == "3.1"

    def test_verified_status(self):
        """Test parser is awaiting verification (not yet verified by user)."""
        assert ArrisS34HnapParser.status == ParserStatus.AWAITING_VERIFICATION
        parser = ArrisS34HnapParser()
        assert parser.verified is False

    def test_fixtures_path(self):
        """Test fixtures path is set correctly."""
        assert ArrisS34HnapParser.fixtures_path == "tests/parsers/arris/fixtures/s34"


class TestS34ParserCapabilities:
    """Test parser capabilities declaration (MVP scope)."""

    def test_has_version_capability(self):
        """Test software version capability (MVP)."""
        assert ArrisS34HnapParser.has_capability(ModemCapability.SOFTWARE_VERSION)

    def test_no_downstream_capability_mvp(self):
        """Test downstream channels NOT in MVP scope.

        Channel data will be added in Phase 4.
        """
        # For MVP, this should be False
        assert not ArrisS34HnapParser.has_capability(ModemCapability.DOWNSTREAM_CHANNELS)

    def test_no_upstream_capability_mvp(self):
        """Test upstream channels NOT in MVP scope.

        Channel data will be added in Phase 4.
        """
        assert not ArrisS34HnapParser.has_capability(ModemCapability.UPSTREAM_CHANNELS)

    def test_no_uptime_capability(self):
        """Test S34 does NOT have uptime capability.

        Like S33, S34 only provides current clock time, not actual uptime.
        """
        assert not ArrisS34HnapParser.has_capability(ModemCapability.SYSTEM_UPTIME)

    def test_has_restart_capability(self):
        """Test restart capability is declared."""
        assert ArrisS34HnapParser.has_capability(ModemCapability.RESTART)


class TestS34ParserDetection:
    """Test parser detection logic."""

    def test_can_parse_with_s34_model(self, s34_login_html):
        """Test detection via S34 model string."""
        soup = BeautifulSoup(s34_login_html, "html.parser")
        html_with_model = s34_login_html + "<!-- S34 -->"
        assert ArrisS34HnapParser.can_parse(soup, "http://192.168.100.1/Login.html", html_with_model)

    def test_can_parse_with_surfboard_and_hnap_and_s34(self):
        """Test detection via SURFboard + HNAP + S34 markers."""
        html = "<html><body>SURFboard HNAP S34</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert ArrisS34HnapParser.can_parse(soup, "http://192.168.100.1/", html)

    def test_can_parse_with_at01_firmware(self):
        """Test detection via S34-specific firmware pattern."""
        html = "<html><body>AT01.01.010 purenetworks.com/HNAP1 ARRIS</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert ArrisS34HnapParser.can_parse(soup, "http://192.168.100.1/", html)

    def test_cannot_parse_generic_html(self):
        """Test that generic HTML is not detected as S34."""
        html = "<html><body>Hello World</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert not ArrisS34HnapParser.can_parse(soup, "http://example.com/", html)

    def test_cannot_parse_s33_only(self):
        """Test that S33-only content is not detected as S34."""
        # S34 parser should NOT match S33-only content
        html = "<html><body>S33 HNAP purenetworks.com/HNAP1</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        # S34 should not match when only S33 is mentioned
        assert not ArrisS34HnapParser.can_parse(soup, "http://192.168.100.1/", html)


class TestS34SupportsICMP:
    """Test supports_icmp attribute."""

    def test_supports_icmp_false(self):
        """Test that S34 has supports_icmp=False (blocks ICMP ping like S33)."""
        assert ArrisS34HnapParser.supports_icmp is False

    def test_supports_icmp_instance(self):
        """Test supports_icmp on parser instance."""
        parser = ArrisS34HnapParser()
        assert parser.supports_icmp is False


class TestS34AuthConfig:
    """Test authentication configuration."""

    def test_auth_config_hnap_endpoint(self):
        """Test HNAP endpoint is correct."""
        assert ArrisS34HnapParser.auth_config.hnap_endpoint == "/HNAP1/"

    def test_auth_config_namespace(self):
        """Test HNAP namespace matches standard."""
        assert ArrisS34HnapParser.auth_config.soap_action_namespace == "http://purenetworks.com/HNAP1/"

    def test_auth_config_login_url(self):
        """Test login URL is correct."""
        assert ArrisS34HnapParser.auth_config.login_url == "/Login.html"


class TestS34SystemInfoParsing:
    """Test system info parsing from HNAP responses (MVP scope)."""

    def test_parse_device_status(self, sample_device_status_response):
        """Test parsing device status from GetArrisDeviceStatus response."""
        parser = ArrisS34HnapParser()
        system_info = parser._parse_system_info_from_hnap(sample_device_status_response)

        assert system_info["software_version"] == "AT01.01.010.042324_S3.04.735"
        assert system_info["internet_connection"] == "Connected"
        assert system_info["model_name"] == "S34"

    def test_parse_device_status_firmware_format(self, sample_device_status_response):
        """Test firmware version format is preserved."""
        parser = ArrisS34HnapParser()
        system_info = parser._parse_system_info_from_hnap(sample_device_status_response)

        # S34 firmware format: AT01.01.010.042324_S3.04.735
        # Different from S33: TB01.03.001.10_012022_212.S3
        assert "AT01" in system_info["software_version"]

    def test_parse_device_status_from_fixture(self, s34_device_status_response):
        """Test parsing from actual fixture file."""
        parser = ArrisS34HnapParser()
        system_info = parser._parse_system_info_from_hnap(s34_device_status_response)

        assert "software_version" in system_info
        assert "model_name" in system_info
        assert system_info["model_name"] == "S34"

    def test_parse_device_status_missing_fields(self):
        """Test parsing handles missing optional fields gracefully."""
        parser = ArrisS34HnapParser()
        minimal_response = {
            "GetArrisDeviceStatusResponse": {
                "FirmwareVersion": "1.0.0",
                "GetArrisDeviceStatusResult": "OK",
            }
        }
        system_info = parser._parse_system_info_from_hnap(minimal_response)
        assert system_info["software_version"] == "1.0.0"
        # Missing fields should not cause errors
        assert "internet_connection" not in system_info

    def test_parse_device_status_empty_response(self):
        """Test parsing handles empty response gracefully."""
        parser = ArrisS34HnapParser()
        empty_response = {}
        system_info = parser._parse_system_info_from_hnap(empty_response)
        assert system_info == {}

    def test_parse_device_status_missing_inner_response(self):
        """Test parsing handles missing GetArrisDeviceStatusResponse."""
        parser = ArrisS34HnapParser()
        wrong_response = {"SomeOtherResponse": {"field": "value"}}
        system_info = parser._parse_system_info_from_hnap(wrong_response)
        assert system_info == {}


class TestS34AuthFailureDetection:
    """Test _is_auth_failure method."""

    def test_detects_401_error(self):
        """Test detection of 401 Unauthorized."""
        parser = ArrisS34HnapParser()
        assert parser._is_auth_failure(Exception("HTTP 401 Unauthorized"))

    def test_detects_403_error(self):
        """Test detection of 403 Forbidden."""
        parser = ArrisS34HnapParser()
        assert parser._is_auth_failure(Exception("HTTP 403 Forbidden"))

    def test_detects_login_failed(self):
        """Test detection of login failed message."""
        parser = ArrisS34HnapParser()
        assert parser._is_auth_failure(Exception('"loginresult":"failed"'))

    def test_detects_session_timeout(self):
        """Test detection of session timeout."""
        parser = ArrisS34HnapParser()
        assert parser._is_auth_failure(Exception("session timeout"))

    def test_does_not_detect_network_error(self):
        """Test that network errors are not auth failures."""
        parser = ArrisS34HnapParser()
        assert not parser._is_auth_failure(Exception("Connection refused"))

    def test_does_not_detect_parse_error(self):
        """Test that parse errors are not auth failures."""
        parser = ArrisS34HnapParser()
        assert not parser._is_auth_failure(Exception("JSON decode error"))


class TestS34ParseMethod:
    """Test parse method error handling."""

    def test_parse_requires_session(self):
        """Test that parse raises ValueError without session."""
        parser = ArrisS34HnapParser()
        soup = BeautifulSoup("<html></html>", "html.parser")

        with pytest.raises(ValueError, match="requires session"):
            parser.parse(soup, session=None, base_url="http://192.168.100.1")

    def test_parse_requires_base_url(self):
        """Test that parse raises ValueError without base_url."""
        from unittest.mock import MagicMock

        parser = ArrisS34HnapParser()
        soup = BeautifulSoup("<html></html>", "html.parser")

        with pytest.raises(ValueError, match="requires session"):
            parser.parse(soup, session=MagicMock(), base_url=None)


class TestS34UrlPatterns:
    """Test URL patterns configuration."""

    def test_hnap_endpoint_pattern(self):
        """Test HNAP1 URL pattern exists."""
        patterns = ArrisS34HnapParser.url_patterns
        hnap_pattern = next((p for p in patterns if p["path"] == "/HNAP1/"), None)
        assert hnap_pattern is not None
        assert hnap_pattern["auth_method"] == "hnap"
        assert hnap_pattern["auth_required"] is True

    def test_login_page_pattern(self):
        """Test login page URL pattern exists."""
        patterns = ArrisS34HnapParser.url_patterns
        login_pattern = next((p for p in patterns if p["path"] == "/Login.html"), None)
        assert login_pattern is not None
        assert login_pattern["auth_required"] is False


# =============================================================================
# PHASE 4 TESTS (Placeholder - to be implemented later)
# =============================================================================


class TestS34DownstreamParsing:
    """Test downstream channel parsing (Phase 4).

    These tests are placeholders for when channel data support is added.
    """

    @pytest.mark.skip(reason="Phase 4 - Channel data not yet implemented")
    def test_parse_downstream_channels(self):
        """Test parsing downstream channels from HNAP data."""
        pass

    @pytest.mark.skip(reason="Phase 4 - Channel data not yet implemented")
    def test_parse_downstream_empty(self):
        """Test parsing empty downstream data."""
        pass


class TestS34UpstreamParsing:
    """Test upstream channel parsing (Phase 4).

    These tests are placeholders for when channel data support is added.
    """

    @pytest.mark.skip(reason="Phase 4 - Channel data not yet implemented")
    def test_parse_upstream_channels(self):
        """Test parsing upstream channels from HNAP data."""
        pass

    @pytest.mark.skip(reason="Phase 4 - Channel data not yet implemented")
    def test_parse_upstream_empty(self):
        """Test parsing empty upstream data."""
        pass


class TestS34Restart:
    """Test restart functionality."""

    def test_restart_success_with_reboot_action(self):
        """Test restart succeeds when response has REBOOT action."""
        from unittest.mock import MagicMock

        parser = ArrisS34HnapParser()

        # Mock the JSON builder to return proper responses
        mock_builder = MagicMock()
        mock_builder.call_single.side_effect = [
            # First call: GetArrisConfigurationInfo
            (
                '{"GetArrisConfigurationInfoResponse": {'
                '"GetArrisConfigurationInfoResult": "OK", '
                '"ethSWEthEEE": "1", "LedStatus": "1"}}'
            ),
            # Second call: SetArrisConfigurationInfo
            (
                '{"SetArrisConfigurationInfoResponse": {'
                '"SetArrisConfigurationInfoResult": "OK", '
                '"SetArrisConfigurationInfoAction": "REBOOT"}}'
            ),
        ]
        parser._json_builder = mock_builder

        result = parser.restart(MagicMock(), "https://192.168.100.1")

        assert result is True
        assert mock_builder.call_single.call_count == 2

    def test_restart_success_on_connection_reset(self):
        """Test restart returns True on connection reset (modem rebooting)."""
        from unittest.mock import MagicMock

        parser = ArrisS34HnapParser()

        mock_builder = MagicMock()
        mock_builder.call_single.side_effect = [
            (
                '{"GetArrisConfigurationInfoResponse": {'
                '"GetArrisConfigurationInfoResult": "OK", '
                '"ethSWEthEEE": "0", "LedStatus": "1"}}'
            ),
            ConnectionResetError("Connection reset by peer"),
        ]
        parser._json_builder = mock_builder

        result = parser.restart(MagicMock(), "https://192.168.100.1")

        assert result is True

    def test_restart_failure_on_error_response(self):
        """Test restart returns False on error response."""
        from unittest.mock import MagicMock

        parser = ArrisS34HnapParser()

        mock_builder = MagicMock()
        mock_builder.call_single.side_effect = [
            (
                '{"GetArrisConfigurationInfoResponse": {'
                '"GetArrisConfigurationInfoResult": "OK", '
                '"ethSWEthEEE": "0", "LedStatus": "1"}}'
            ),
            '{"SetArrisConfigurationInfoResponse": {"SetArrisConfigurationInfoResult": "ERROR"}}',
        ]
        parser._json_builder = mock_builder

        result = parser.restart(MagicMock(), "https://192.168.100.1")

        assert result is False
