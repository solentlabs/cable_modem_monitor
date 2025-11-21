"""Tests for the Motorola MB8611 parser using HNAP protocol."""

from __future__ import annotations

import json
import os
from unittest.mock import Mock, patch

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import (
    HNAPAuthConfig,
)
from custom_components.cable_modem_monitor.core.authentication import (
    AuthStrategyType,
)
from custom_components.cable_modem_monitor.core.hnap_builder import HNAPRequestBuilder
from custom_components.cable_modem_monitor.core.hnap_json_builder import (
    HNAPJsonRequestBuilder,
)
from custom_components.cable_modem_monitor.parsers.motorola.mb8611_hnap import (
    MotorolaMB8611HnapParser,
)


@pytest.fixture
def hnap_full_status():
    """Load hnap_full_status.json fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "mb8611_hnap", "hnap_full_status.json")
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def login_html():
    """Load Login.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "mb8611_hnap", "Login.html")
    with open(fixture_path) as f:
        return f.read()


class TestDetection:
    """Test modem detection."""

    def test_from_model_name(self):
        """Test detection from MB8611 in HTML."""
        html = "<html><body>Motorola MB8611 Cable Modem</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        parser = MotorolaMB8611HnapParser()

        assert parser.can_parse(soup, "http://192.168.100.1", html) is True

    def test_from_model_number_with_spaces(self):
        """Test detection from model number with spaces."""
        html = "<html><body>Motorola MB 8611</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        parser = MotorolaMB8611HnapParser()

        assert parser.can_parse(soup, "http://192.168.100.1", html) is True

    def test_from_serial_number(self):
        """Test detection from serial number format."""
        html = "<html><body>Serial: 2251-MB8611-30-1526</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        parser = MotorolaMB8611HnapParser()

        assert parser.can_parse(soup, "http://192.168.100.1", html) is True

    def test_from_hnap_with_motorola(self):
        """Test detection from HNAP protocol indicators."""
        html = "<html><body>Motorola Modem" '<script src="/HNAP1/"></script></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        parser = MotorolaMB8611HnapParser()

        assert parser.can_parse(soup, "http://192.168.100.1", html) is True

    def test_rejects_other_modems(self):
        """Test that other modems are not detected."""
        html = "<html><body>Arris SB6190</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        parser = MotorolaMB8611HnapParser()

        assert parser.can_parse(soup, "http://192.168.100.1", html) is False

    def test_rejects_hnap_without_motorola(self):
        """Test that HNAP alone is not enough without Motorola."""
        html = "<html><body>Generic Modem" '<script src="/HNAP1/"></script></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        parser = MotorolaMB8611HnapParser()

        assert parser.can_parse(soup, "http://192.168.100.1", html) is False


class TestAuthentication:
    """Test HNAP authentication."""

    def test_has_hnap_auth_config(self):
        """Test that parser has HNAP authentication config."""
        parser = MotorolaMB8611HnapParser()

        assert parser.auth_config is not None
        assert isinstance(parser.auth_config, HNAPAuthConfig)
        assert parser.auth_config.strategy == AuthStrategyType.HNAP_SESSION
        assert parser.auth_config.login_url == "/Login.html"
        assert parser.auth_config.hnap_endpoint == "/HNAP1/"
        assert parser.auth_config.soap_action_namespace == "http://purenetworks.com/HNAP1/"

    def test_url_patterns_require_hnap_auth(self):
        """Test that URL patterns require HNAP authentication."""
        parser = MotorolaMB8611HnapParser()

        assert len(parser.url_patterns) > 0
        for pattern in parser.url_patterns:
            assert pattern["auth_method"] == "hnap"
            assert pattern["auth_required"] is True

    def test_login_uses_auth_factory(self):
        """Test that login delegates to AuthFactory."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "http://192.168.100.1"

        # Mock AuthFactory at its actual import location
        auth_path = "custom_components.cable_modem_monitor" ".core.authentication.AuthFactory"
        with patch(auth_path) as mock_factory:
            mock_strategy = Mock()
            mock_strategy.login.return_value = (True, "Login successful")
            mock_factory.get_strategy.return_value = mock_strategy

            success, message = parser.login(mock_session, base_url, "admin", "password")

            assert success is True
            assert message == "Login successful"
            mock_factory.get_strategy.assert_called_once_with(AuthStrategyType.HNAP_SESSION)


class TestHnapParsing:
    """Test HNAP data parsing."""

    def test_requires_session_and_base_url(self):
        """Test that parse raises error without session and base_url."""
        parser = MotorolaMB8611HnapParser()
        soup = BeautifulSoup("<html></html>", "html.parser")

        error_msg = "MB8611 requires session and base_url"
        with pytest.raises(ValueError, match=error_msg):
            parser.parse(soup)

        with pytest.raises(ValueError, match=error_msg):
            parser.parse(soup, session=Mock())

        with pytest.raises(ValueError, match=error_msg):
            parser.parse(soup, base_url="http://192.168.100.1")

    @patch("custom_components.cable_modem_monitor" ".parsers.motorola.mb8611_hnap.HNAPRequestBuilder")
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

        # Check first channel (ID 1)
        first_channel = data["downstream"][0]
        assert first_channel["channel_id"] == 1
        assert first_channel["lock_status"] == "Locked"
        assert first_channel["modulation"] == "QAM256"
        assert first_channel["ch_id"] == 20
        assert first_channel["frequency"] == 543_000_000  # 543.0 MHz
        assert first_channel["power"] == 1.4
        assert first_channel["snr"] == 45.1
        assert first_channel["corrected"] == 41
        assert first_channel["uncorrected"] == 0

        # Check OFDM PLC channel (last channel, ID 33)
        ofdm_channel = data["downstream"][32]
        assert ofdm_channel["channel_id"] == 33
        assert ofdm_channel["modulation"] == "OFDM PLC"
        assert ofdm_channel["ch_id"] == 193
        assert ofdm_channel["frequency"] == 957_000_000  # 957.0 MHz
        assert ofdm_channel["power"] == -4.1
        assert ofdm_channel["snr"] == 41.1
        assert ofdm_channel["corrected"] == 936482395
        assert ofdm_channel["uncorrected"] == 23115

    @patch("custom_components.cable_modem_monitor" ".parsers.motorola.mb8611_hnap.HNAPRequestBuilder")
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

        # Check first channel (ID 1)
        first_channel = data["upstream"][0]
        assert first_channel["channel_id"] == 1
        assert first_channel["lock_status"] == "Locked"
        assert first_channel["modulation"] == "SC-QAM"
        assert first_channel["ch_id"] == 17
        assert first_channel["symbol_rate"] == 5120
        # 16.4 MHz converted to Hz - account for floating-point precision
        assert abs(first_channel["frequency"] - 16_400_000) <= 1
        assert first_channel["power"] == 44.3

        # Check last channel (ID 4)
        last_channel = data["upstream"][3]
        assert last_channel["channel_id"] == 4
        assert last_channel["lock_status"] == "Locked"
        assert last_channel["modulation"] == "SC-QAM"
        assert last_channel["ch_id"] == 20
        # 35.6 MHz converted to Hz - account for floating-point precision
        assert abs(last_channel["frequency"] - 35_600_000) <= 1
        assert last_channel["power"] == 45.5

    @patch("custom_components.cable_modem_monitor" ".parsers.motorola.mb8611_hnap.HNAPRequestBuilder")
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

    @patch("custom_components.cable_modem_monitor" ".parsers.motorola.mb8611_hnap.HNAPRequestBuilder")
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

        # Verify SOAP actions
        expected_actions = [
            "GetMotoStatusStartupSequence",
            "GetMotoStatusConnectionInfo",
            "GetMotoStatusDownstreamChannelInfo",
            "GetMotoStatusUpstreamChannelInfo",
            "GetMotoLagStatus",
        ]
        mock_builder.call_multiple.assert_called_once_with(mock_session, base_url, expected_actions)


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch("custom_components.cable_modem_monitor" ".parsers.motorola.mb8611_hnap.HNAPRequestBuilder")
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

    @patch("custom_components.cable_modem_monitor" ".parsers.motorola.mb8611_hnap.HNAPRequestBuilder")
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

    @patch("custom_components.cable_modem_monitor" ".parsers.motorola.mb8611_hnap.HNAPRequestBuilder")
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
        assert data["downstream"][0]["channel_id"] == 2

    @patch("custom_components.cable_modem_monitor" ".parsers.motorola.mb8611_hnap.HNAPRequestBuilder")
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
        assert parser.name == "Motorola MB8611 (HNAP)"

    def test_manufacturer(self):
        """Test parser manufacturer."""
        parser = MotorolaMB8611HnapParser()
        assert parser.manufacturer == "Motorola"

    def test_models(self):
        """Test parser supported models."""
        parser = MotorolaMB8611HnapParser()
        assert "MB8611" in parser.models
        assert "MB8612" in parser.models

    def test_priority(self):
        """Test parser priority (model-specific should be high)."""
        parser = MotorolaMB8611HnapParser()
        assert parser.priority == 101  # Higher priority for the API-based method


class TestJsonHnapSupport:
    """Test JSON-based HNAP support for firmware variants that use JSON instead of XML/SOAP."""

    def test_json_hnap_login_success(self):
        """Test that JSON HNAP login succeeds and returns proper response."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "https://192.168.100.1"

        # Mock successful JSON HNAP login
        with patch.object(
            HNAPJsonRequestBuilder, "login", return_value=(True, '{"LoginResponse":{"LoginResult":"OK"}}')
        ):
            success, response = parser.login(mock_session, base_url, "admin", "password")

            assert success is True
            assert response is not None
            assert "LoginResponse" in response

    def test_json_hnap_login_fallback_to_xml(self):
        """Test that login falls back to XML/SOAP when JSON fails."""
        parser = MotorolaMB8611HnapParser()
        mock_session = Mock()
        base_url = "https://192.168.100.1"

        # Mock JSON login failure, XML/SOAP login success
        auth_path = "custom_components.cable_modem_monitor.core.authentication.AuthFactory"
        with patch.object(HNAPJsonRequestBuilder, "login", return_value=(False, "")), patch(auth_path) as mock_factory:
            mock_strategy = Mock()
            mock_strategy.login.return_value = (True, "XML Login OK")
            mock_factory.get_strategy.return_value = mock_strategy

            success, response = parser.login(mock_session, base_url, "admin", "password")

            assert success is True
            assert response == "XML Login OK"

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
