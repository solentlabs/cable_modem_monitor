"""Tests for the Motorola MB8611 parser using HNAP protocol."""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth import (
    HNAPJsonRequestBuilder,
    HNAPRequestBuilder,
)
from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher
from custom_components.cable_modem_monitor.modems.motorola.mb8611.parser import (
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

    @patch("custom_components.cable_modem_monitor" ".modems.motorola.mb8611.parser.HNAPRequestBuilder")
    def test_downstream_channels(self, mock_builder_class, hnap_full_status):
        """Test parsing of downstream channels from HNAP response."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "http://192.168.100.1"

        # Mock HNAPRequestBuilder
        mock_builder = Mock()
        mock_builder.call_multiple.return_value = json.dumps(hnap_full_status)
        mock_builder_class.return_value = mock_builder

        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url=base_url)

        # Verify downstream channels
        assert "downstream" in data
        assert len(data["downstream"]) == 33  # 32 QAM256 + 1 OFDM PLC

        # Check first channel (DOCSIS Channel ID 20)
        first_channel = data["downstream"][0]
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
        ofdm_channel = data["downstream"][32]
        assert ofdm_channel["channel_id"] == 193  # DOCSIS Channel ID
        assert ofdm_channel["modulation"] == "OFDM PLC"
        assert ofdm_channel["channel_type"] == "ofdm"  # Derived from modulation (issue #87)
        assert ofdm_channel["frequency"] == 957_000_000  # 957.0 MHz
        assert ofdm_channel["power"] == -4.1
        assert ofdm_channel["snr"] == 41.1
        assert ofdm_channel["corrected"] == 936482395
        assert ofdm_channel["uncorrected"] == 23115

    @patch("custom_components.cable_modem_monitor" ".modems.motorola.mb8611.parser.HNAPRequestBuilder")
    def test_upstream_channels(self, mock_builder_class, hnap_full_status):
        """Test parsing of upstream channels from HNAP response."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "http://192.168.100.1"

        # Mock HNAPRequestBuilder
        mock_builder = Mock()
        mock_builder.call_multiple.return_value = json.dumps(hnap_full_status)
        mock_builder_class.return_value = mock_builder

        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url=base_url)

        # Verify upstream channels
        assert "upstream" in data
        assert len(data["upstream"]) == 4

        # Check first channel (DOCSIS Channel ID 17)
        first_channel = data["upstream"][0]
        assert first_channel["channel_id"] == 17  # DOCSIS Channel ID
        assert first_channel["lock_status"] == "Locked"
        assert first_channel["modulation"] == "SC-QAM"
        assert first_channel["channel_type"] == "atdma"  # Derived from modulation
        assert first_channel["symbol_rate"] == 5120
        # 16.4 MHz converted to Hz - account for floating-point precision
        assert abs(first_channel["frequency"] - 16_400_000) <= 1
        assert first_channel["power"] == 44.3

        # Check last channel (DOCSIS Channel ID 20)
        last_channel = data["upstream"][3]
        assert last_channel["channel_id"] == 20  # DOCSIS Channel ID
        assert last_channel["lock_status"] == "Locked"
        assert last_channel["modulation"] == "SC-QAM"
        assert last_channel["channel_type"] == "atdma"  # Derived from modulation
        # 35.6 MHz converted to Hz - account for floating-point precision
        assert abs(last_channel["frequency"] - 35_600_000) <= 1
        assert last_channel["power"] == 45.5

    @patch("custom_components.cable_modem_monitor" ".modems.motorola.mb8611.parser.HNAPRequestBuilder")
    def test_system_info(self, mock_builder_class, hnap_full_status):
        """Test parsing of system info from HNAP response."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "http://192.168.100.1"

        # Mock HNAPRequestBuilder
        mock_builder = Mock()
        mock_builder.call_multiple.return_value = json.dumps(hnap_full_status)
        mock_builder_class.return_value = mock_builder

        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url=base_url)

        # Verify system info
        assert "system_info" in data
        system_info = data["system_info"]

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

    @patch("custom_components.cable_modem_monitor" ".modems.motorola.mb8611.parser.HNAPRequestBuilder")
    def test_builder_called_correctly(self, mock_builder_class, hnap_full_status):
        """Test that HNAPRequestBuilder is called with correct parameters."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "http://192.168.100.1"

        # Mock HNAPRequestBuilder
        mock_builder = Mock()
        mock_builder.call_multiple.return_value = json.dumps(hnap_full_status)
        mock_builder_class.return_value = mock_builder

        soup = BeautifulSoup("<html></html>", "html.parser")
        parser.parse(soup, session=mock_session, base_url=base_url)

        # Verify builder instantiation
        mock_builder_class.assert_called_once_with(endpoint="/HNAP1/", namespace="http://purenetworks.com/HNAP1/")

        # Verify SOAP actions (including GetMotoStatusSoftware added in v3.9+)
        expected_actions = [
            "GetMotoStatusStartupSequence",
            "GetMotoStatusConnectionInfo",
            "GetMotoStatusDownstreamChannelInfo",
            "GetMotoStatusUpstreamChannelInfo",
            "GetMotoStatusSoftware",
            "GetMotoLagStatus",
        ]
        mock_builder.call_multiple.assert_called_once_with(mock_session, base_url, expected_actions)


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch("custom_components.cable_modem_monitor" ".modems.motorola.mb8611.parser.HNAPRequestBuilder")
    def test_handles_invalid_json(self, mock_builder_class):
        """Test that parse handles invalid JSON gracefully."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "http://192.168.100.1"

        # Mock HNAPRequestBuilder returning invalid JSON
        mock_builder = Mock()
        mock_builder.call_multiple.return_value = "not valid json {"
        mock_builder_class.return_value = mock_builder

        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url=base_url)

        # Should return empty data structures
        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}

    @patch("custom_components.cable_modem_monitor" ".modems.motorola.mb8611.parser.HNAPRequestBuilder")
    def test_handles_missing_downstream_data(self, mock_builder_class):
        """Test that parse handles missing downstream channel data."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "http://192.168.100.1"

        # Mock response without downstream data
        response = {
            "GetMultipleHNAPsResponse": {
                "GetMotoStatusDownstreamChannelInfoResponse": {
                    "MotoConnDownstreamChannel": "",
                    "GetMotoStatusDownstreamChannelInfoResult": "OK",
                }
            }
        }

        mock_builder = Mock()
        mock_builder.call_multiple.return_value = json.dumps(response)
        mock_builder_class.return_value = mock_builder

        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url=base_url)

        # Should handle empty data
        assert data["downstream"] == []

    @patch("custom_components.cable_modem_monitor" ".modems.motorola.mb8611.parser.HNAPRequestBuilder")
    def test_handles_malformed_channel_entry(self, mock_builder_class):
        """Test that parse handles malformed channel entries."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "http://192.168.100.1"

        # Mock response with malformed channel data (missing fields)
        response = {
            "GetMultipleHNAPsResponse": {
                "GetMotoStatusDownstreamChannelInfoResponse": {
                    "MotoConnDownstreamChannel": ("1^Locked^QAM256^|+|" "2^Locked^QAM256^1^429.0^ 1.3^45.4^26^0^"),
                    "GetMotoStatusDownstreamChannelInfoResult": "OK",
                }
            }
        }

        mock_builder = Mock()
        mock_builder.call_multiple.return_value = json.dumps(response)
        mock_builder_class.return_value = mock_builder

        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url=base_url)

        # Should skip malformed entry and parse valid one
        assert len(data["downstream"]) == 1
        assert data["downstream"][0]["channel_id"] == 1  # DOCSIS Channel ID from fields[3]

    @patch("custom_components.cable_modem_monitor" ".modems.motorola.mb8611.parser.HNAPRequestBuilder")
    def test_handles_exception_in_builder(self, mock_builder_class):
        """Test that parse handles exceptions from builder."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "http://192.168.100.1"

        # Mock builder raising exception
        mock_builder = Mock()
        mock_builder.call_multiple.side_effect = Exception("Network error")
        mock_builder_class.return_value = mock_builder

        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url=base_url)

        # Should return empty data structures
        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}

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


class TestJsonHnapSupport:
    """Test JSON-based HNAP support for firmware variants that use JSON instead of XML/SOAP.

    Note: As of v3.12.0, login() is handled by AuthHandler, not parser.
    Login tests moved to tests/core/test_auth_handler.py.
    """

    def test_json_hnap_parse_success(self, hnap_full_status):
        """Test parsing modem data using JSON HNAP."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "https://192.168.100.1"

        # Mock JSON HNAP response
        with patch.object(HNAPJsonRequestBuilder, "call_multiple", return_value=json.dumps(hnap_full_status)):
            soup = BeautifulSoup("<html></html>", "html.parser")
            data = parser.parse(soup, session=mock_session, base_url=base_url)

            # Should successfully parse using JSON HNAP
            assert "downstream" in data
            assert "upstream" in data
            assert len(data["downstream"]) == 33
            assert len(data["upstream"]) == 4

    def test_json_hnap_parse_fallback_to_xml(self, hnap_full_status):
        """Test that parsing falls back to XML/SOAP when JSON HNAP fails."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "https://192.168.100.1"

        # Mock JSON failure, XML/SOAP success
        with (
            patch.object(HNAPJsonRequestBuilder, "call_multiple", side_effect=Exception("JSON not supported")),
            patch.object(HNAPRequestBuilder, "call_multiple", return_value=json.dumps(hnap_full_status)),
        ):
            soup = BeautifulSoup("<html></html>", "html.parser")
            data = parser.parse(soup, session=mock_session, base_url=base_url)

            # Should successfully parse using XML/SOAP fallback
            assert "downstream" in data
            assert len(data["downstream"]) == 33

    def test_both_json_and_xml_fail(self):
        """Test error handling when both JSON and XML/SOAP HNAP fail."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "https://192.168.100.1"

        # Mock both methods failing
        with (
            patch.object(HNAPJsonRequestBuilder, "call_multiple", side_effect=Exception("JSON failed")),
            patch.object(HNAPRequestBuilder, "call_multiple", side_effect=Exception("XML failed")),
        ):
            soup = BeautifulSoup("<html></html>", "html.parser")
            data = parser.parse(soup, session=mock_session, base_url=base_url)

            # Should return empty data structures
            assert data["downstream"] == []
            assert data["upstream"] == []
            assert data["system_info"] == {}

    def test_both_json_and_xml_fail_with_auth_error(self):
        """Test that auth failures are properly detected and flagged."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "https://192.168.100.1"

        # Mock both methods failing with auth errors
        with (
            patch.object(HNAPJsonRequestBuilder, "call_multiple", side_effect=Exception("401 Unauthorized")),
            patch.object(HNAPRequestBuilder, "call_multiple", side_effect=Exception("Login failed")),
        ):
            soup = BeautifulSoup("<html></html>", "html.parser")
            data = parser.parse(soup, session=mock_session, base_url=base_url)

            # Should return empty data structures
            assert data["downstream"] == []
            assert data["upstream"] == []
            assert data["system_info"] == {}

            # Should flag auth failure
            assert data["_auth_failure"] is True
            assert data["_login_page_detected"] is True
            assert "_diagnostic_context" in data
            assert data["_diagnostic_context"]["parser"] == "MB8611 HNAP"
            assert data["_diagnostic_context"]["error_type"] == "HNAP authentication failure"

    def test_json_fails_with_401_xml_succeeds(self, hnap_full_status):
        """Test that only JSON auth failure doesn't trigger false positive."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "https://192.168.100.1"

        # Mock JSON failing with 401, but XML succeeding
        with (
            patch.object(HNAPJsonRequestBuilder, "call_multiple", side_effect=Exception("401 Unauthorized")),
            patch.object(HNAPRequestBuilder, "call_multiple", return_value=json.dumps(hnap_full_status)),
        ):
            soup = BeautifulSoup("<html></html>", "html.parser")
            data = parser.parse(soup, session=mock_session, base_url=base_url)

            # Should successfully parse using XML/SOAP fallback
            assert "downstream" in data
            assert len(data["downstream"]) == 33
            # Should NOT flag auth failure (XML succeeded)
            assert "_auth_failure" not in data
            assert "_login_page_detected" not in data

    def test_non_auth_errors_dont_trigger_auth_failure(self):
        """Test that non-auth errors (network, parsing) don't trigger auth failure flag."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "https://192.168.100.1"

        # Mock both methods failing with non-auth errors
        with (
            patch.object(HNAPJsonRequestBuilder, "call_multiple", side_effect=Exception("Connection timeout")),
            patch.object(HNAPRequestBuilder, "call_multiple", side_effect=Exception("Invalid JSON response")),
        ):
            soup = BeautifulSoup("<html></html>", "html.parser")
            data = parser.parse(soup, session=mock_session, base_url=base_url)

            # Should return empty data structures
            assert data["downstream"] == []
            assert data["upstream"] == []
            assert data["system_info"] == {}

            # Should NOT flag auth failure (these are network/parsing errors)
            assert "_auth_failure" not in data
            assert "_login_page_detected" not in data


class TestAuthFailureDetection:
    """Test authentication failure detection helper method."""

    def test_detects_401_error(self):
        """Test that 401 errors are detected as auth failures."""
        parser = MotorolaMB8611HnapParser()
        error = Exception("HTTP 401 Unauthorized")
        assert parser._is_auth_failure(error) is True

    def test_detects_403_error(self):
        """Test that 403 errors are detected as auth failures."""
        parser = MotorolaMB8611HnapParser()
        error = Exception("HTTP 403 Forbidden")
        assert parser._is_auth_failure(error) is True

    def test_detects_login_failed(self):
        """Test that login failed messages are detected."""
        parser = MotorolaMB8611HnapParser()
        error = Exception('Response contains "LoginResult":"FAILED"')
        assert parser._is_auth_failure(error) is True

    def test_detects_authentication_failed(self):
        """Test that authentication failed messages are detected."""
        parser = MotorolaMB8611HnapParser()
        error = Exception("Authentication failed - invalid credentials")
        assert parser._is_auth_failure(error) is True

    def test_detects_session_timeout(self):
        """Test that session timeout errors are detected."""
        parser = MotorolaMB8611HnapParser()
        error = Exception("Session timeout - please login again")
        assert parser._is_auth_failure(error) is True

    def test_ignores_network_errors(self):
        """Test that network errors are NOT detected as auth failures."""
        parser = MotorolaMB8611HnapParser()
        error = Exception("Connection timeout")
        assert parser._is_auth_failure(error) is False

    def test_ignores_parsing_errors(self):
        """Test that parsing errors are NOT detected as auth failures."""
        parser = MotorolaMB8611HnapParser()
        error = Exception("Invalid JSON response")
        assert parser._is_auth_failure(error) is False

    def test_ignores_generic_errors(self):
        """Test that generic errors are NOT detected as auth failures."""
        parser = MotorolaMB8611HnapParser()
        error = Exception("Something went wrong")
        assert parser._is_auth_failure(error) is False


class TestSoftwareVersionParsing:
    """Test software version parsing from GetMotoStatusSoftware."""

    @patch("custom_components.cable_modem_monitor" ".modems.motorola.mb8611.parser.HNAPRequestBuilder")
    def test_software_version_parsed(self, mock_builder_class, hnap_full_status):
        """Test that software version is parsed from HNAP response."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "http://192.168.100.1"

        mock_builder = Mock()
        mock_builder.call_multiple.return_value = json.dumps(hnap_full_status)
        mock_builder_class.return_value = mock_builder

        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url=base_url)

        assert "system_info" in data
        assert data["system_info"]["software_version"] == "8611-19.2.18"

    @patch("custom_components.cable_modem_monitor" ".modems.motorola.mb8611.parser.HNAPRequestBuilder")
    def test_docsis_version_parsed(self, mock_builder_class, hnap_full_status):
        """Test that DOCSIS spec version is parsed from HNAP response."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "http://192.168.100.1"

        mock_builder = Mock()
        mock_builder.call_multiple.return_value = json.dumps(hnap_full_status)
        mock_builder_class.return_value = mock_builder

        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url=base_url)

        assert "system_info" in data
        assert data["system_info"]["docsis_version"] == "DOCSIS 3.1"

    @patch("custom_components.cable_modem_monitor" ".modems.motorola.mb8611.parser.HNAPRequestBuilder")
    def test_serial_number_parsed(self, mock_builder_class, hnap_full_status):
        """Test that serial number is parsed from HNAP response."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "http://192.168.100.1"

        mock_builder = Mock()
        mock_builder.call_multiple.return_value = json.dumps(hnap_full_status)
        mock_builder_class.return_value = mock_builder

        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url=base_url)

        assert "system_info" in data
        assert data["system_info"]["serial_number"] == "***SERIAL***"

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
    """Test modem restart functionality."""

    def test_restart_capability_declared(self):
        """Test that RESTART capability is declared."""
        from custom_components.cable_modem_monitor.core.base_parser import ModemCapability

        parser = MotorolaMB8611HnapParser()
        assert ModemCapability.RESTART in parser.capabilities

    def test_restart_method_exists(self):
        """Test that restart method exists."""
        parser = MotorolaMB8611HnapParser()
        assert hasattr(parser, "restart")
        assert callable(parser.restart)

    @patch("custom_components.cable_modem_monitor.modems.motorola.mb8611.parser.HNAPJsonRequestBuilder")
    def test_restart_success(self, mock_builder_class):
        """Test successful restart command.

        The restart uses SetStatusSecuritySettings (from MotoStatusSecurity.html)
        with MotoStatusSecurityAction=1 to trigger a reboot.
        """
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "https://192.168.100.1"

        # Mock successful restart response
        mock_builder = Mock()
        mock_builder.call_single.return_value = json.dumps(
            {"SetStatusSecuritySettingsResponse": {"SetStatusSecuritySettingsResult": "OK"}}
        )
        mock_builder_class.return_value = mock_builder

        result = parser.restart(mock_session, base_url)

        assert result is True
        mock_builder.call_single.assert_called_once()
        call_args = mock_builder.call_single.call_args
        assert call_args[0][2] == "SetStatusSecuritySettings"
        assert call_args[0][3]["MotoStatusSecurityAction"] == "1"
        assert call_args[0][3]["MotoStatusSecXXX"] == "XXX"

    @patch("custom_components.cable_modem_monitor.modems.motorola.mb8611.parser.HNAPJsonRequestBuilder")
    def test_restart_connection_reset_is_success(self, mock_builder_class):
        """Test that connection reset during restart is treated as success."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "https://192.168.100.1"

        # Mock connection reset (modem rebooting)
        mock_builder = Mock()
        mock_builder.call_single.side_effect = ConnectionResetError("Connection reset by peer")
        mock_builder_class.return_value = mock_builder

        result = parser.restart(mock_session, base_url)

        # Connection reset means the modem is rebooting - success!
        assert result is True

    @patch("custom_components.cable_modem_monitor.modems.motorola.mb8611.parser.HNAPJsonRequestBuilder")
    def test_restart_failure(self, mock_builder_class):
        """Test restart failure response."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "https://192.168.100.1"

        # Mock failed restart response
        mock_builder = Mock()
        mock_builder.call_single.return_value = json.dumps(
            {"SetStatusSecuritySettingsResponse": {"SetStatusSecuritySettingsResult": "FAILED"}}
        )
        mock_builder_class.return_value = mock_builder

        result = parser.restart(mock_session, base_url)

        assert result is False

    def test_restart_uses_stored_json_builder(self):
        """Test that restart reuses the JSON builder from login."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "https://192.168.100.1"

        # Simulate that login was called and stored a builder
        mock_builder = Mock()
        mock_builder.call_single.return_value = json.dumps(
            {"SetStatusSecuritySettingsResponse": {"SetStatusSecuritySettingsResult": "OK"}}
        )
        parser._json_builder = mock_builder

        result = parser.restart(mock_session, base_url)

        assert result is True
        # Should use the stored builder, not create a new one
        mock_builder.call_single.assert_called_once()
