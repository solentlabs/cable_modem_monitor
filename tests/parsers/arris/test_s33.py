"""Tests for the Arris/CommScope S33 parser.

The S33 uses HNAP protocol like the MB8611, so these tests focus on:
- Parser metadata and capabilities
- Detection logic
- Channel data parsing from HNAP responses
"""

import os

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.arris.s33 import ArrisS33HnapParser
from custom_components.cable_modem_monitor.parsers.base_parser import ModemCapability


@pytest.fixture
def s33_login_html():
    """Load S33 Login.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "s33", "Login.html")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def s33_connectionstatus_html():
    """Load S33 Cmconnectionstatus.html fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "s33", "cmconnectionstatus.html")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def sample_downstream_hnap_response():
    """Sample HNAP downstream channel response matching S33 format."""
    return {
        "GetCustomerStatusDownstreamChannelInfoResponse": {
            "CustomerConnDownstreamChannel": (
                "1^Locked^QAM256^20^537000000 Hz^5 dBmV^40 dB^1234^5|+|"
                "2^Locked^QAM256^21^543000000 Hz^4.5 dBmV^39.5 dB^1000^2|+|"
                "3^Locked^QAM256^22^549000000 Hz^4.8 dBmV^40.2 dB^800^0"
            ),
            "GetCustomerStatusDownstreamChannelInfoResult": "OK",
        }
    }


@pytest.fixture
def sample_upstream_hnap_response():
    """Sample HNAP upstream channel response matching S33 format."""
    return {
        "GetCustomerStatusUpstreamChannelInfoResponse": {
            "CustomerConnUpstreamChannel": (
                "1^Locked^SC-QAM^1^5120 Ksym/sec^38600000 Hz^43 dBmV|+|"
                "2^Locked^SC-QAM^2^5120 Ksym/sec^30600000 Hz^45 dBmV"
            ),
            "GetCustomerStatusUpstreamChannelInfoResult": "OK",
        }
    }


@pytest.fixture
def sample_connection_info_response():
    """Sample HNAP connection info response."""
    return {
        "GetCustomerStatusConnectionInfoResponse": {
            "CustomerCurSystemTime": "7 days 12:34:56",
            "CustomerConnNetworkAccess": "Allowed",
            "StatusSoftwareModelName": "S33",
            "GetCustomerStatusConnectionInfoResult": "OK",
        }
    }


@pytest.fixture
def sample_startup_sequence_response():
    """Sample HNAP startup sequence response."""
    return {
        "GetCustomerStatusStartupSequenceResponse": {
            "CustomerConnDSFreq": "537 MHz",
            "CustomerConnConnectivityStatus": "Connected",
            "CustomerConnBootStatus": "OK",
            "CustomerConnSecurityStatus": "Enabled",
            "GetCustomerStatusStartupSequenceResult": "OK",
        }
    }


@pytest.fixture
def sample_device_status_response():
    """Sample HNAP device status response with firmware version."""
    return {
        "GetArrisDeviceStatusResponse": {
            "FirmwareVersion": "TB01.03.001.10_012022_212.S3",
            "InternetConnection": "Connected",
            "DownstreamFrequency": "537000000 Hz",
            "DownstreamSignalPower": "5 dBmV",
            "DownstreamSignalSnr": "40 dB",
            "StatusSoftwareModelName": "S33",
            "GetArrisDeviceStatusResult": "OK",
        }
    }


class TestS33ParserMetadata:
    """Test parser metadata."""

    def test_parser_name(self):
        """Test parser name is correct."""
        assert ArrisS33HnapParser.name == "Arris S33"

    def test_parser_manufacturer(self):
        """Test manufacturer is correct."""
        assert ArrisS33HnapParser.manufacturer == "Arris/CommScope"

    def test_parser_models(self):
        """Test model list includes S33 variants."""
        assert "S33" in ArrisS33HnapParser.models
        assert "CommScope S33" in ArrisS33HnapParser.models
        assert "ARRIS S33" in ArrisS33HnapParser.models

    def test_parser_priority(self):
        """Test priority is high (HNAP API method)."""
        assert ArrisS33HnapParser.priority == 101

    def test_docsis_version(self):
        """Test DOCSIS version is 3.1."""
        assert ArrisS33HnapParser.docsis_version == "3.1"

    def test_verified_status(self):
        """Test parser is awaiting verification (not yet verified by user)."""
        from custom_components.cable_modem_monitor.parsers.base_parser import ParserStatus

        assert ArrisS33HnapParser.status == ParserStatus.AWAITING_VERIFICATION
        # Also test the verified property via an instance
        parser = ArrisS33HnapParser()
        assert parser.verified is False

    def test_fixtures_path(self):
        """Test fixtures path is set."""
        assert ArrisS33HnapParser.fixtures_path == "tests/parsers/arris/fixtures/s33"


class TestS33ParserCapabilities:
    """Test parser capabilities declaration."""

    def test_has_downstream_capability(self):
        """Test downstream channels capability."""
        assert ArrisS33HnapParser.has_capability(ModemCapability.DOWNSTREAM_CHANNELS)

    def test_has_upstream_capability(self):
        """Test upstream channels capability."""
        assert ArrisS33HnapParser.has_capability(ModemCapability.UPSTREAM_CHANNELS)

    def test_has_uptime_capability(self):
        """Test system uptime capability."""
        assert ArrisS33HnapParser.has_capability(ModemCapability.SYSTEM_UPTIME)

    def test_has_version_capability(self):
        """Test software version capability."""
        assert ArrisS33HnapParser.has_capability(ModemCapability.SOFTWARE_VERSION)

    def test_has_restart_capability(self):
        """Test that restart is supported (experimental - based on MB8611 pattern)."""
        assert ArrisS33HnapParser.has_capability(ModemCapability.RESTART)


class TestS33ParserDetection:
    """Test parser detection logic."""

    def test_can_parse_with_s33_model(self, s33_login_html):
        """Test detection via S33 model string."""
        soup = BeautifulSoup(s33_login_html, "html.parser")
        # Inject S33 into HTML for test (actual page may have it in JS)
        html_with_model = s33_login_html + "<!-- S33 -->"
        assert ArrisS33HnapParser.can_parse(soup, "http://192.168.100.1/Login.html", html_with_model)

    def test_can_parse_with_arris_and_hnap(self, s33_login_html):
        """Test detection via ARRIS + HNAP markers."""
        soup = BeautifulSoup(s33_login_html, "html.parser")
        # The fixture should have ARRIS branding and HNAP references
        if "ARRIS" in s33_login_html and "purenetworks.com/HNAP1" in s33_login_html:
            assert ArrisS33HnapParser.can_parse(soup, "http://192.168.100.1/Login.html", s33_login_html)

    def test_can_parse_with_commscope_and_hnap(self):
        """Test detection via CommScope + HNAP markers (line 87)."""
        html = "<html><body>CommScope purenetworks.com/HNAP1</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert ArrisS33HnapParser.can_parse(soup, "http://192.168.100.1/", html)

    def test_can_parse_with_surfboard_and_hnap(self):
        """Test detection via SURFboard + HNAP markers."""
        html = "<html><body>SURFboard HNAP</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert ArrisS33HnapParser.can_parse(soup, "http://192.168.100.1/", html)

    def test_cannot_parse_generic_html(self):
        """Test that generic HTML is not detected as S33."""
        html = "<html><body>Hello World</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert not ArrisS33HnapParser.can_parse(soup, "http://example.com/", html)


class TestS33SupportsICMP:
    """Test supports_icmp attribute (S33 blocks ICMP)."""

    def test_supports_icmp_false(self):
        """Test that S33 has supports_icmp=False (blocks ICMP ping)."""
        assert ArrisS33HnapParser.supports_icmp is False

    def test_supports_icmp_instance(self):
        """Test supports_icmp on parser instance."""
        parser = ArrisS33HnapParser()
        assert parser.supports_icmp is False


class TestS33AuthFailureDetection:
    """Test _is_auth_failure method (lines 134-150)."""

    def test_detects_401_error(self):
        """Test detection of 401 Unauthorized."""
        parser = ArrisS33HnapParser()
        assert parser._is_auth_failure(Exception("HTTP 401 Unauthorized"))

    def test_detects_403_error(self):
        """Test detection of 403 Forbidden."""
        parser = ArrisS33HnapParser()
        assert parser._is_auth_failure(Exception("HTTP 403 Forbidden"))

    def test_detects_login_failed(self):
        """Test detection of login failed message."""
        parser = ArrisS33HnapParser()
        assert parser._is_auth_failure(Exception('"loginresult":"failed"'))

    def test_detects_session_timeout(self):
        """Test detection of session timeout."""
        parser = ArrisS33HnapParser()
        assert parser._is_auth_failure(Exception("session timeout"))

    def test_does_not_detect_network_error(self):
        """Test that network errors are not auth failures."""
        parser = ArrisS33HnapParser()
        assert not parser._is_auth_failure(Exception("Connection refused"))

    def test_does_not_detect_parse_error(self):
        """Test that parse errors are not auth failures."""
        parser = ArrisS33HnapParser()
        assert not parser._is_auth_failure(Exception("JSON decode error"))


class TestS33ParseMethod:
    """Test parse method error handling (lines 164-187)."""

    def test_parse_requires_session(self):
        """Test that parse raises ValueError without session."""
        parser = ArrisS33HnapParser()
        soup = BeautifulSoup("<html></html>", "html.parser")

        with pytest.raises(ValueError, match="requires session"):
            parser.parse(soup, session=None, base_url="http://192.168.100.1")

    def test_parse_requires_base_url(self):
        """Test that parse raises ValueError without base_url."""
        from unittest.mock import MagicMock

        parser = ArrisS33HnapParser()
        soup = BeautifulSoup("<html></html>", "html.parser")

        with pytest.raises(ValueError, match="requires session"):
            parser.parse(soup, session=MagicMock(), base_url=None)


class TestS33DownstreamParsing:
    """Test downstream channel parsing from HNAP responses."""

    def test_parse_downstream_channels(self, sample_downstream_hnap_response):
        """Test parsing downstream channels from HNAP data."""
        parser = ArrisS33HnapParser()
        channels = parser._parse_downstream_from_hnap(sample_downstream_hnap_response)

        assert len(channels) == 3

        # Check first channel
        ch1 = channels[0]
        assert ch1["channel_id"] == 20
        assert ch1["lock_status"] == "Locked"
        assert ch1["modulation"] == "QAM256"
        assert ch1["frequency"] == 537000000  # Hz
        assert ch1["power"] == 5.0
        assert ch1["snr"] == 40.0
        assert ch1["corrected"] == 1234
        assert ch1["uncorrected"] == 5

    def test_parse_downstream_frequency_in_mhz(self):
        """Test parsing frequency when provided in MHz without Hz suffix (line 298)."""
        parser = ArrisS33HnapParser()
        # Frequency as plain number (MHz) - should be converted to Hz
        response = {
            "GetCustomerStatusDownstreamChannelInfoResponse": {
                "CustomerConnDownstreamChannel": "1^Locked^QAM256^20^537^5 dBmV^40 dB^100^0"
            }
        }
        channels = parser._parse_downstream_from_hnap(response)
        assert len(channels) == 1
        assert channels[0]["frequency"] == 537000000  # 537 MHz -> 537000000 Hz

    def test_parse_downstream_invalid_entry_too_few_fields(self):
        """Test parsing skips entries with too few fields (lines 281-282)."""
        parser = ArrisS33HnapParser()
        # Entry with only 5 fields (needs 9)
        response = {
            "GetCustomerStatusDownstreamChannelInfoResponse": {
                "CustomerConnDownstreamChannel": "1^Locked^QAM256^20^537000000 Hz|+|2^Locked^QAM256"
            }
        }
        channels = parser._parse_downstream_from_hnap(response)
        # Only first entry should parse
        assert len(channels) == 0  # First entry also has too few fields

    def test_parse_downstream_skips_empty_entries(self):
        """Test that empty entries in the channel data are skipped (line 275)."""
        parser = ArrisS33HnapParser()
        # Entry with empty strings between delimiters
        response = {
            "GetCustomerStatusDownstreamChannelInfoResponse": {
                "CustomerConnDownstreamChannel": "|+||+|1^Locked^QAM256^20^537000000 Hz^5 dBmV^40 dB^100^0"
            }
        }
        channels = parser._parse_downstream_from_hnap(response)
        assert len(channels) == 1
        assert channels[0]["channel_id"] == 20

    def test_parse_downstream_empty(self):
        """Test parsing empty downstream data."""
        parser = ArrisS33HnapParser()
        empty_response = {"GetCustomerStatusDownstreamChannelInfoResponse": {"CustomerConnDownstreamChannel": ""}}
        channels = parser._parse_downstream_from_hnap(empty_response)
        assert channels == []

    def test_parse_downstream_missing_key(self):
        """Test parsing when response key is missing."""
        parser = ArrisS33HnapParser()
        channels = parser._parse_downstream_from_hnap({})
        assert channels == []


class TestS33UpstreamParsing:
    """Test upstream channel parsing from HNAP responses."""

    def test_parse_upstream_channels(self, sample_upstream_hnap_response):
        """Test parsing upstream channels from HNAP data."""
        parser = ArrisS33HnapParser()
        channels = parser._parse_upstream_from_hnap(sample_upstream_hnap_response)

        assert len(channels) == 2

        # Check first channel
        ch1 = channels[0]
        assert ch1["channel_id"] == 1
        assert ch1["lock_status"] == "Locked"
        assert ch1["modulation"] == "SC-QAM"
        assert ch1["symbol_rate"] == "5120 Ksym/sec"
        assert ch1["frequency"] == 38600000  # Hz
        assert ch1["power"] == 43.0

    def test_parse_upstream_frequency_in_mhz(self):
        """Test parsing upstream frequency when provided in MHz without Hz suffix (line 382)."""
        parser = ArrisS33HnapParser()
        # Frequency as plain number (MHz) - should be converted to Hz
        response = {
            "GetCustomerStatusUpstreamChannelInfoResponse": {
                "CustomerConnUpstreamChannel": "1^Locked^SC-QAM^1^5120 Ksym/sec^38.6^43 dBmV"
            }
        }
        channels = parser._parse_upstream_from_hnap(response)
        assert len(channels) == 1
        assert channels[0]["frequency"] == 38600000  # 38.6 MHz -> 38600000 Hz

    def test_parse_upstream_skips_empty_entries(self):
        """Test that empty entries in upstream data are skipped (line 360)."""
        parser = ArrisS33HnapParser()
        response = {
            "GetCustomerStatusUpstreamChannelInfoResponse": {
                "CustomerConnUpstreamChannel": "|+||+|1^Locked^SC-QAM^1^5120^38600000 Hz^43 dBmV"
            }
        }
        channels = parser._parse_upstream_from_hnap(response)
        assert len(channels) == 1
        assert channels[0]["channel_id"] == 1

    def test_parse_upstream_invalid_entry_too_few_fields(self):
        """Test parsing skips upstream entries with too few fields (lines 366-367)."""
        parser = ArrisS33HnapParser()
        response = {
            "GetCustomerStatusUpstreamChannelInfoResponse": {
                "CustomerConnUpstreamChannel": "1^Locked^SC-QAM"  # Only 3 fields, needs 7
            }
        }
        channels = parser._parse_upstream_from_hnap(response)
        assert channels == []

    def test_parse_upstream_empty(self):
        """Test parsing empty upstream data."""
        parser = ArrisS33HnapParser()
        empty_response = {"GetCustomerStatusUpstreamChannelInfoResponse": {"CustomerConnUpstreamChannel": ""}}
        channels = parser._parse_upstream_from_hnap(empty_response)
        assert channels == []

    def test_parse_upstream_missing_key(self):
        """Test parsing when response key is missing."""
        parser = ArrisS33HnapParser()
        channels = parser._parse_upstream_from_hnap({})
        assert channels == []


class TestS33SystemInfoParsing:
    """Test system info parsing from HNAP responses."""

    def test_parse_system_info(
        self,
        sample_connection_info_response,
        sample_startup_sequence_response,
        sample_device_status_response,
    ):
        """Test parsing system info from combined HNAP data."""
        parser = ArrisS33HnapParser()

        # Combine responses (as returned by GetMultipleHNAPs)
        hnap_data = {}
        hnap_data.update(sample_connection_info_response)
        hnap_data.update(sample_startup_sequence_response)
        hnap_data.update(sample_device_status_response)

        system_info = parser._parse_system_info_from_hnap(hnap_data)

        # Connection info
        assert "system_uptime" in system_info
        assert system_info["system_uptime"] == "7 days 12:34:56"
        assert system_info["network_access"] == "Allowed"
        assert system_info["model_name"] == "S33"

        # Startup sequence info
        assert system_info["connectivity_status"] == "Connected"

        # Device status info (firmware version)
        assert "software_version" in system_info
        assert system_info["software_version"] == "TB01.03.001.10_012022_212.S3"
        assert system_info["internet_connection"] == "Connected"


class TestS33AuthConfig:
    """Test authentication configuration."""

    def test_auth_config_hnap_endpoint(self):
        """Test HNAP endpoint is correct."""
        assert ArrisS33HnapParser.auth_config.hnap_endpoint == "/HNAP1/"

    def test_auth_config_namespace(self):
        """Test HNAP namespace matches standard."""
        assert ArrisS33HnapParser.auth_config.soap_action_namespace == "http://purenetworks.com/HNAP1/"

    def test_auth_config_login_url(self):
        """Test login URL is correct."""
        assert ArrisS33HnapParser.auth_config.login_url == "/Login.html"


class TestS33UrlPatterns:
    """Test URL patterns configuration."""

    def test_hnap_endpoint_pattern(self):
        """Test HNAP1 URL pattern exists."""
        patterns = ArrisS33HnapParser.url_patterns
        hnap_pattern = next((p for p in patterns if p["path"] == "/HNAP1/"), None)
        assert hnap_pattern is not None
        assert hnap_pattern["auth_method"] == "hnap"
        assert hnap_pattern["auth_required"] is True

    def test_status_page_pattern(self):
        """Test connection status URL pattern exists."""
        patterns = ArrisS33HnapParser.url_patterns
        status_pattern = next(
            (p for p in patterns if isinstance(p["path"], str) and "connectionstatus" in p["path"].lower()),
            None,
        )
        assert status_pattern is not None
        assert status_pattern["auth_required"] is True


class TestS33Restart:
    """Test restart functionality using SetArrisConfigurationInfo."""

    def test_restart_success_with_reboot_action(self):
        """Test restart succeeds when response has REBOOT action."""
        from unittest.mock import MagicMock

        parser = ArrisS33HnapParser()

        # Mock the JSON builder to return proper responses for both calls:
        # 1. GetArrisConfigurationInfo (get current settings)
        # 2. SetArrisConfigurationInfo (send reboot command)
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

        # Check the second call (SetArrisConfigurationInfo with reboot)
        second_call_args = mock_builder.call_single.call_args_list[1]
        assert second_call_args[0][2] == "SetArrisConfigurationInfo"
        assert second_call_args[0][3]["Action"] == "reboot"
        # Should include the EEE and LED settings from GetArrisConfigurationInfo
        assert second_call_args[0][3]["SetEEEEnable"] == "1"
        assert second_call_args[0][3]["LED_Status"] == "1"

    def test_restart_success_with_ok_only(self):
        """Test restart succeeds when response has OK but no specific action."""
        from unittest.mock import MagicMock

        parser = ArrisS33HnapParser()

        mock_builder = MagicMock()
        mock_builder.call_single.side_effect = [
            # First call: GetArrisConfigurationInfo
            (
                '{"GetArrisConfigurationInfoResponse": {'
                '"GetArrisConfigurationInfoResult": "OK", '
                '"ethSWEthEEE": "0", "LedStatus": "1"}}'
            ),
            # Second call: SetArrisConfigurationInfo (OK but no action)
            '{"SetArrisConfigurationInfoResponse": {"SetArrisConfigurationInfoResult": "OK"}}',
        ]
        parser._json_builder = mock_builder

        result = parser.restart(MagicMock(), "https://192.168.100.1")

        assert result is True

    def test_restart_success_on_connection_reset(self):
        """Test restart returns True on connection reset (modem rebooting)."""
        from unittest.mock import MagicMock

        parser = ArrisS33HnapParser()

        mock_builder = MagicMock()
        # First call succeeds, second call causes connection reset (modem rebooting)
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

        parser = ArrisS33HnapParser()

        mock_builder = MagicMock()
        mock_builder.call_single.side_effect = [
            # First call: GetArrisConfigurationInfo succeeds
            (
                '{"GetArrisConfigurationInfoResponse": {'
                '"GetArrisConfigurationInfoResult": "OK", '
                '"ethSWEthEEE": "0", "LedStatus": "1"}}'
            ),
            # Second call: SetArrisConfigurationInfo returns ERROR
            '{"SetArrisConfigurationInfoResponse": {"SetArrisConfigurationInfoResult": "ERROR"}}',
        ]
        parser._json_builder = mock_builder

        result = parser.restart(MagicMock(), "https://192.168.100.1")

        assert result is False

    def test_restart_sends_correct_action_fields(self):
        """Test that restart sends the correct fields matching configuration.js."""
        from unittest.mock import MagicMock

        parser = ArrisS33HnapParser()

        mock_builder = MagicMock()
        mock_builder.call_single.side_effect = [
            # First call: GetArrisConfigurationInfo with specific values
            (
                '{"GetArrisConfigurationInfoResponse": {'
                '"GetArrisConfigurationInfoResult": "OK", '
                '"ethSWEthEEE": "1", "LedStatus": "0"}}'
            ),
            # Second call: SetArrisConfigurationInfo
            (
                '{"SetArrisConfigurationInfoResponse": {'
                '"SetArrisConfigurationInfoResult": "OK", '
                '"SetArrisConfigurationInfoAction": "REBOOT"}}'
            ),
        ]
        parser._json_builder = mock_builder

        parser.restart(MagicMock(), "https://192.168.100.1")

        # Verify the request data matches what configuration.js sends
        # The second call should have the reboot action with preserved settings
        second_call_args = mock_builder.call_single.call_args_list[1]
        request_data = second_call_args[0][3]
        assert "Action" in request_data
        assert request_data["Action"] == "reboot"
        assert "SetEEEEnable" in request_data
        assert request_data["SetEEEEnable"] == "1"  # From GetArrisConfigurationInfo
        assert "LED_Status" in request_data
        assert request_data["LED_Status"] == "0"  # From GetArrisConfigurationInfo

    def test_restart_success_on_connection_aborted(self):
        """Test restart returns True on 'Connection aborted' (lines 557-564)."""
        from unittest.mock import MagicMock

        parser = ArrisS33HnapParser()

        mock_builder = MagicMock()
        mock_builder.call_single.side_effect = [
            '{"GetArrisConfigurationInfoResponse": {'
            '"GetArrisConfigurationInfoResult": "OK", '
            '"ethSWEthEEE": "0", "LedStatus": "1"}}',
            Exception("Connection aborted"),
        ]
        parser._json_builder = mock_builder

        result = parser.restart(MagicMock(), "https://192.168.100.1")

        assert result is True

    def test_restart_failure_on_general_exception(self):
        """Test restart returns False on unexpected exception."""
        from unittest.mock import MagicMock

        parser = ArrisS33HnapParser()

        mock_builder = MagicMock()
        mock_builder.call_single.side_effect = [
            '{"GetArrisConfigurationInfoResponse": {'
            '"GetArrisConfigurationInfoResult": "OK", '
            '"ethSWEthEEE": "0", "LedStatus": "1"}}',
            Exception("Some unexpected error"),
        ]
        parser._json_builder = mock_builder

        result = parser.restart(MagicMock(), "https://192.168.100.1")

        assert result is False
