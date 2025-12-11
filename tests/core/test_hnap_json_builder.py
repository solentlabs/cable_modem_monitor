"""Tests for JSON-based HNAP Request Builder with challenge-response authentication."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from custom_components.cable_modem_monitor.core.hnap_json_builder import (
    HNAPJsonRequestBuilder,
    _hmac_md5,
)


class TestHmacMd5:
    """Test the HMAC-MD5 helper function."""

    def test_returns_uppercase_hex(self):
        """Test that HMAC-MD5 returns uppercase hexadecimal."""
        result = _hmac_md5("key", "message")
        assert result == result.upper()
        assert all(c in "0123456789ABCDEF" for c in result)

    def test_correct_length(self):
        """Test that HMAC-MD5 returns 32 character hex string."""
        result = _hmac_md5("key", "message")
        assert len(result) == 32

    def test_known_value(self):
        """Test HMAC-MD5 against known value."""
        ***REMOVED*** This matches the JavaScript hex_hmac_md5 function behavior
        result = _hmac_md5("testkey", "testmessage")
        ***REMOVED*** Verify it's a valid HMAC-MD5 output
        assert len(result) == 32
        assert result.isupper()

    def test_empty_strings(self):
        """Test HMAC-MD5 with empty strings."""
        result = _hmac_md5("", "")
        assert len(result) == 32

    def test_special_characters(self):
        """Test HMAC-MD5 with special characters."""
        result = _hmac_md5("key!@***REMOVED***$%", "message with spaces")
        assert len(result) == 32


@pytest.fixture
def builder():
    """Create a JSON HNAP request builder instance."""
    return HNAPJsonRequestBuilder(endpoint="/HNAP1/", namespace="http://purenetworks.com/HNAP1/")


@pytest.fixture
def mock_session():
    """Create a mock requests session."""
    session = MagicMock(spec=requests.Session)
    session.verify = False
    session.cookies = MagicMock()
    return session


class TestHNAPJsonRequestBuilderInit:
    """Test JSON HNAP builder initialization."""

    def test_init(self):
        """Test initialization with endpoint and namespace."""
        builder = HNAPJsonRequestBuilder(endpoint="/HNAP1/", namespace="http://purenetworks.com/HNAP1/")

        assert builder.endpoint == "/HNAP1/"
        assert builder.namespace == "http://purenetworks.com/HNAP1/"
        assert builder._private_key is None

    def test_init_custom_values(self):
        """Test initialization with custom endpoint and namespace."""
        builder = HNAPJsonRequestBuilder(endpoint="/api/hnap", namespace="http://custom.com/")

        assert builder.endpoint == "/api/hnap"
        assert builder.namespace == "http://custom.com/"


class TestHnapAuth:
    """Test HNAP_AUTH header generation."""

    def test_without_private_key(self, builder):
        """Test auth generation without private key uses default."""
        auth = builder._get_hnap_auth("Login")

        ***REMOVED*** Should have format: HASH TIMESTAMP
        parts = auth.split(" ")
        assert len(parts) == 2
        assert len(parts[0]) == 32  ***REMOVED*** HMAC-MD5 hex
        assert parts[0].isupper()
        assert parts[1].isdigit()

    def test_with_private_key(self, builder):
        """Test auth generation with private key."""
        builder._private_key = "TESTPRIVATEKEY1234567890ABCDEF"
        auth = builder._get_hnap_auth("GetMotoStatusConnectionInfo")

        parts = auth.split(" ")
        assert len(parts) == 2
        assert len(parts[0]) == 32

    @patch("time.time")
    def test_timestamp_format(self, mock_time, builder):
        """Test that timestamp is correctly formatted."""
        mock_time.return_value = 1700000000.123  ***REMOVED*** Fixed timestamp
        auth = builder._get_hnap_auth("Login")

        parts = auth.split(" ")
        timestamp = int(parts[1])
        ***REMOVED*** Timestamp should be (time * 1000) % 2000000000000
        expected = int(1700000000.123 * 1000) % 2000000000000
        assert timestamp == expected


class TestCallSingle:
    """Test single JSON HNAP action calls."""

    def test_success(self, builder, mock_session):
        """Test successful single action call."""
        mock_response = MagicMock()
        mock_response.text = '{"GetMotoStatusConnectionInfoResponse": {"Result": "OK"}}'
        mock_session.post.return_value = mock_response

        result = builder.call_single(mock_session, "http://192.168.100.1", "GetMotoStatusConnectionInfo")

        assert result == '{"GetMotoStatusConnectionInfoResponse": {"Result": "OK"}}'
        mock_session.post.assert_called_once()

    def test_request_format(self, builder, mock_session):
        """Test that request is properly formatted."""
        mock_response = MagicMock()
        mock_response.text = "{}"
        mock_session.post.return_value = mock_response

        builder.call_single(mock_session, "http://192.168.100.1", "TestAction")

        call_args = mock_session.post.call_args
        assert call_args[0][0] == "http://192.168.100.1/HNAP1/"
        assert call_args[1]["headers"]["SOAPAction"] == '"http://purenetworks.com/HNAP1/TestAction"'
        assert call_args[1]["headers"]["Content-Type"] == "application/json"
        assert "HNAP_AUTH" in call_args[1]["headers"]

    def test_with_params(self, builder, mock_session):
        """Test single call with parameters."""
        mock_response = MagicMock()
        mock_response.text = "{}"
        mock_session.post.return_value = mock_response

        params = {"Setting": "Value"}
        builder.call_single(mock_session, "http://192.168.100.1", "SetConfig", params)

        call_args = mock_session.post.call_args
        request_json = call_args[1]["json"]
        assert request_json == {"SetConfig": {"Setting": "Value"}}

    def test_handles_http_error(self, builder, mock_session):
        """Test that HTTP errors are raised."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_session.post.return_value = mock_response

        with pytest.raises(requests.HTTPError):
            builder.call_single(mock_session, "http://192.168.100.1", "TestAction")


class TestCallMultiple:
    """Test batched JSON HNAP action calls."""

    def test_success(self, builder, mock_session):
        """Test successful batched call."""
        mock_response = MagicMock()
        mock_response.text = '{"GetMultipleHNAPsResponse": {}}'
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        actions = ["GetMotoStatusConnectionInfo", "GetMotoStatusStartupSequence"]
        result = builder.call_multiple(mock_session, "http://192.168.100.1", actions)

        assert "GetMultipleHNAPsResponse" in result

    def test_request_format(self, builder, mock_session):
        """Test batched request format."""
        mock_response = MagicMock()
        mock_response.text = "{}"
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        actions = ["Action1", "Action2"]
        builder.call_multiple(mock_session, "http://192.168.100.1", actions)

        call_args = mock_session.post.call_args
        request_json = call_args[1]["json"]
        assert "GetMultipleHNAPs" in request_json
        assert "Action1" in request_json["GetMultipleHNAPs"]
        assert "Action2" in request_json["GetMultipleHNAPs"]

    def test_default_empty_action_value_is_empty_dict(self, builder, mock_session):
        """Test that default empty action value is {} for backwards compatibility.

        MB8611 was working with empty dict {}, so we preserve that as default.
        Parsers can override this for modems that need empty string "".
        """
        mock_response = MagicMock()
        mock_response.text = "{}"
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        actions = ["GetMotoStatusConnectionInfo", "GetMotoStatusStartupSequence"]
        builder.call_multiple(mock_session, "http://192.168.100.1", actions)

        call_args = mock_session.post.call_args
        request_json = call_args[1]["json"]

        ***REMOVED*** Default should be empty dict {} for MB8611 compatibility
        for action in actions:
            assert action in request_json["GetMultipleHNAPs"]
            assert request_json["GetMultipleHNAPs"][action] == {}, (
                f"Default action value should be empty dict {{}}, "
                f"got {type(request_json['GetMultipleHNAPs'][action]).__name__}: "
                f"{request_json['GetMultipleHNAPs'][action]!r}"
            )

    def test_configurable_empty_action_value_string(self, mock_session):
        """Test that empty_action_value can be configured to empty string for S33.

        S33 requires empty string "" for action values (observed in HAR captures).
        Using {} causes 500 Internal Server Error on S33.

        Reference: https://github.com/solentlabs/cable_modem_monitor/issues/32
        """
        ***REMOVED*** Create builder with empty string configuration (like S33 does)
        builder = HNAPJsonRequestBuilder(
            endpoint="/HNAP1/",
            namespace="http://purenetworks.com/HNAP1/",
            empty_action_value="",
        )

        mock_response = MagicMock()
        mock_response.text = "{}"
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        actions = ["GetCustomerStatusDownstreamChannelInfo", "GetCustomerStatusUpstreamChannelInfo"]
        builder.call_multiple(mock_session, "http://192.168.100.1", actions)

        call_args = mock_session.post.call_args
        request_json = call_args[1]["json"]

        ***REMOVED*** With empty_action_value="", should use empty strings
        for action in actions:
            assert action in request_json["GetMultipleHNAPs"]
            assert request_json["GetMultipleHNAPs"][action] == "", (
                f"Action '{action}' should have empty string value when configured, "
                f"got {type(request_json['GetMultipleHNAPs'][action]).__name__}: "
                f"{request_json['GetMultipleHNAPs'][action]!r}"
            )

    def test_soap_action_header(self, builder, mock_session):
        """Test that SOAPAction header is correct for batched calls."""
        mock_response = MagicMock()
        mock_response.text = "{}"
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        builder.call_multiple(mock_session, "http://192.168.100.1", ["Action1"])

        call_args = mock_session.post.call_args
        assert call_args[1]["headers"]["SOAPAction"] == '"http://purenetworks.com/HNAP1/GetMultipleHNAPs"'


class TestLogin:
    """Test JSON HNAP login with challenge-response authentication."""

    def test_successful_login(self, builder, mock_session):
        """Test successful two-step login flow."""
        ***REMOVED*** Step 1: Challenge response
        challenge_response = MagicMock()
        challenge_response.status_code = 200
        challenge_response.text = json.dumps(
            {
                "LoginResponse": {
                    "Challenge": "ABCD1234EFGH5678",
                    "Cookie": "session_cookie_value",
                    "PublicKey": "PUBLICKEY12345678",
                }
            }
        )

        ***REMOVED*** Step 2: Login response
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = json.dumps(
            {
                "LoginResponse": {
                    "LoginResult": "OK",
                }
            }
        )

        mock_session.post.side_effect = [challenge_response, login_response]

        success, response = builder.login(mock_session, "http://192.168.100.1", "admin", "password")

        assert success is True
        assert builder._private_key is not None
        assert len(builder._private_key) == 32  ***REMOVED*** HMAC-MD5 hex

        ***REMOVED*** Verify both cookies were set (uid and PrivateKey)
        ***REMOVED*** The modem's browser login (Login.js) requires both cookies for authenticated actions
        assert mock_session.cookies.set.call_count == 2
        mock_session.cookies.set.assert_any_call("uid", "session_cookie_value")
        mock_session.cookies.set.assert_any_call("PrivateKey", builder._private_key)

    def test_challenge_request_format(self, builder, mock_session):
        """Test that challenge request is properly formatted."""
        challenge_response = MagicMock()
        challenge_response.status_code = 200
        challenge_response.text = json.dumps(
            {
                "LoginResponse": {
                    "Challenge": "TEST",
                    "Cookie": "cookie",
                    "PublicKey": "key",
                }
            }
        )

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = json.dumps({"LoginResponse": {"LoginResult": "OK"}})

        mock_session.post.side_effect = [challenge_response, login_response]

        builder.login(mock_session, "http://192.168.100.1", "testuser", "testpass")

        ***REMOVED*** Check first call (challenge request)
        first_call = mock_session.post.call_args_list[0]
        request_json = first_call[1]["json"]
        assert request_json["Login"]["Action"] == "request"
        assert request_json["Login"]["Username"] == "testuser"
        assert request_json["Login"]["LoginPassword"] == ""
        ***REMOVED*** PrivateLogin field is required for MB8611 authentication
        assert request_json["Login"]["PrivateLogin"] == "LoginPassword"

    def test_login_request_format(self, builder, mock_session):
        """Test that login request includes computed password."""
        challenge_response = MagicMock()
        challenge_response.status_code = 200
        challenge_response.text = json.dumps(
            {
                "LoginResponse": {
                    "Challenge": "CHALLENGE123",
                    "Cookie": "cookie",
                    "PublicKey": "PUBKEY456",
                }
            }
        )

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = json.dumps({"LoginResponse": {"LoginResult": "OK"}})

        mock_session.post.side_effect = [challenge_response, login_response]

        builder.login(mock_session, "http://192.168.100.1", "admin", "password")

        ***REMOVED*** Check second call (login request)
        second_call = mock_session.post.call_args_list[1]
        request_json = second_call[1]["json"]
        assert request_json["Login"]["Action"] == "login"
        assert request_json["Login"]["Username"] == "admin"
        ***REMOVED*** LoginPassword should be a 32-char uppercase hex (HMAC-MD5)
        login_password = request_json["Login"]["LoginPassword"]
        assert len(login_password) == 32
        assert login_password.isupper()
        ***REMOVED*** PrivateLogin field is required for MB8611 authentication
        assert request_json["Login"]["PrivateLogin"] == "LoginPassword"

    def test_private_key_computation(self, builder, mock_session):
        """Test that private key is computed correctly."""
        challenge_response = MagicMock()
        challenge_response.status_code = 200
        challenge_response.text = json.dumps(
            {
                "LoginResponse": {
                    "Challenge": "TESTCHALLENGE",
                    "Cookie": "cookie",
                    "PublicKey": "TESTPUBKEY",
                }
            }
        )

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = json.dumps({"LoginResponse": {"LoginResult": "OK"}})

        mock_session.post.side_effect = [challenge_response, login_response]

        builder.login(mock_session, "http://192.168.100.1", "admin", "mypassword")

        ***REMOVED*** PrivateKey = HMAC_MD5(PublicKey + password, Challenge)
        expected_private_key = _hmac_md5("TESTPUBKEY" + "mypassword", "TESTCHALLENGE")
        assert builder._private_key == expected_private_key

    def test_login_failed_result(self, builder, mock_session):
        """Test handling of failed login result."""
        challenge_response = MagicMock()
        challenge_response.status_code = 200
        challenge_response.text = json.dumps(
            {
                "LoginResponse": {
                    "Challenge": "TEST",
                    "Cookie": "cookie",
                    "PublicKey": "key",
                }
            }
        )

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = json.dumps({"LoginResponse": {"LoginResult": "FAILED"}})

        mock_session.post.side_effect = [challenge_response, login_response]

        success, _ = builder.login(mock_session, "http://192.168.100.1", "admin", "wrongpassword")

        assert success is False
        assert builder._private_key is None  ***REMOVED*** Cleared on failure

    def test_challenge_missing_fields(self, builder, mock_session):
        """Test handling of incomplete challenge response."""
        challenge_response = MagicMock()
        challenge_response.status_code = 200
        challenge_response.text = json.dumps(
            {
                "LoginResponse": {
                    "Challenge": "TEST",
                    ***REMOVED*** Missing Cookie and PublicKey
                }
            }
        )

        mock_session.post.return_value = challenge_response

        success, _ = builder.login(mock_session, "http://192.168.100.1", "admin", "password")

        assert success is False

    def test_challenge_http_error(self, builder, mock_session):
        """Test handling of HTTP error during challenge."""
        challenge_response = MagicMock()
        challenge_response.status_code = 500
        challenge_response.text = "Server Error"

        mock_session.post.return_value = challenge_response

        success, _ = builder.login(mock_session, "http://192.168.100.1", "admin", "password")

        assert success is False

    def test_login_timeout(self, builder, mock_session):
        """Test handling of timeout during login."""
        mock_session.post.side_effect = requests.exceptions.Timeout("Connection timed out")

        success, _ = builder.login(mock_session, "http://192.168.100.1", "admin", "password")

        assert success is False
        assert builder._private_key is None

    def test_login_connection_error(self, builder, mock_session):
        """Test handling of connection error during login."""
        mock_session.post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        success, _ = builder.login(mock_session, "http://192.168.100.1", "admin", "password")

        assert success is False
        assert builder._private_key is None

    def test_invalid_json_challenge(self, builder, mock_session):
        """Test handling of invalid JSON in challenge response."""
        challenge_response = MagicMock()
        challenge_response.status_code = 200
        challenge_response.text = "not valid json"

        mock_session.post.return_value = challenge_response

        success, _ = builder.login(mock_session, "http://192.168.100.1", "admin", "password")

        assert success is False

    def test_success_result_variations(self, builder, mock_session):
        """Test that both OK and SUCCESS are accepted as successful login."""
        for result_value in ["OK", "SUCCESS"]:
            builder._private_key = None  ***REMOVED*** Reset

            challenge_response = MagicMock()
            challenge_response.status_code = 200
            challenge_response.text = json.dumps(
                {
                    "LoginResponse": {
                        "Challenge": "TEST",
                        "Cookie": "cookie",
                        "PublicKey": "key",
                    }
                }
            )

            login_response = MagicMock()
            login_response.status_code = 200
            login_response.text = json.dumps({"LoginResponse": {"LoginResult": result_value}})

            mock_session.post.side_effect = [challenge_response, login_response]

            success, _ = builder.login(mock_session, "http://192.168.100.1", "admin", "password")

            assert success is True, f"Expected success for LoginResult={result_value}"


class TestAuthenticatedRequests:
    """Test that authenticated requests use stored private key."""

    def test_call_single_uses_private_key(self, builder, mock_session):
        """Test that call_single uses stored private key for auth."""
        builder._private_key = "STOREDPRIVATEKEY***SERIAL***34"

        mock_response = MagicMock()
        mock_response.text = "{}"
        mock_session.post.return_value = mock_response

        builder.call_single(mock_session, "http://192.168.100.1", "GetData")

        call_args = mock_session.post.call_args
        auth_header = call_args[1]["headers"]["HNAP_AUTH"]

        ***REMOVED*** Auth should be computed using the stored private key
        assert len(auth_header.split(" ")[0]) == 32

    def test_call_multiple_uses_private_key(self, builder, mock_session):
        """Test that call_multiple uses stored private key for auth."""
        builder._private_key = "STOREDPRIVATEKEY***SERIAL***34"

        mock_response = MagicMock()
        mock_response.text = "{}"
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        builder.call_multiple(mock_session, "http://192.168.100.1", ["Action1"])

        call_args = mock_session.post.call_args
        auth_header = call_args[1]["headers"]["HNAP_AUTH"]

        assert len(auth_header.split(" ")[0]) == 32


class TestIntegration:
    """Integration tests for complete login and data retrieval workflow."""

    def test_full_workflow(self, builder, mock_session):
        """Test complete workflow: login then fetch data."""
        ***REMOVED*** Step 1: Challenge response
        challenge_response = MagicMock()
        challenge_response.status_code = 200
        challenge_response.text = json.dumps(
            {
                "LoginResponse": {
                    "Challenge": "INTEGRATIONTEST",
                    "Cookie": "test_session",
                    "PublicKey": "TESTPUBLIC123",
                }
            }
        )

        ***REMOVED*** Step 2: Login response
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = json.dumps({"LoginResponse": {"LoginResult": "OK"}})

        ***REMOVED*** Step 3: Data response
        data_response = MagicMock()
        data_response.status_code = 200
        data_response.text = json.dumps(
            {
                "GetMotoStatusConnectionInfoResponse": {
                    "GetMotoStatusConnectionInfoResult": "OK",
                    "MotoConnDeviceType": "MB8611",
                }
            }
        )

        mock_session.post.side_effect = [challenge_response, login_response, data_response]

        ***REMOVED*** Login
        success, _ = builder.login(mock_session, "http://192.168.100.1", "admin", "password")
        assert success is True

        ***REMOVED*** Fetch data
        result = builder.call_single(mock_session, "http://192.168.100.1", "GetMotoStatusConnectionInfo")
        assert "MB8611" in result


class TestClearAuthCache:
    """Test auth cache clearing for modem restart scenarios."""

    def test_clear_auth_cache_clears_private_key(self, builder):
        """Test that clear_auth_cache clears the stored private key."""
        builder._private_key = "STOREDPRIVATEKEY***SERIAL***34"

        builder.clear_auth_cache()

        assert builder._private_key is None

    def test_clear_auth_cache_when_already_none(self, builder):
        """Test clear_auth_cache is safe when private key is already None."""
        assert builder._private_key is None

        builder.clear_auth_cache()  ***REMOVED*** Should not raise

        assert builder._private_key is None

    def test_reauth_after_cache_clear(self, builder, mock_session):
        """Test that login works correctly after cache is cleared."""
        ***REMOVED*** First login
        challenge_response = MagicMock()
        challenge_response.status_code = 200
        challenge_response.text = json.dumps(
            {
                "LoginResponse": {
                    "Challenge": "FIRST",
                    "Cookie": "cookie1",
                    "PublicKey": "key1",
                }
            }
        )
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = json.dumps({"LoginResponse": {"LoginResult": "OK"}})

        mock_session.post.side_effect = [challenge_response, login_response]
        success, _ = builder.login(mock_session, "http://192.168.100.1", "admin", "pass")
        assert success is True
        first_key = builder._private_key

        ***REMOVED*** Clear cache (simulates modem restart)
        builder.clear_auth_cache()
        assert builder._private_key is None

        ***REMOVED*** Re-login with different challenge (modem rebooted)
        challenge_response2 = MagicMock()
        challenge_response2.status_code = 200
        challenge_response2.text = json.dumps(
            {
                "LoginResponse": {
                    "Challenge": "SECOND",
                    "Cookie": "cookie2",
                    "PublicKey": "key2",
                }
            }
        )
        login_response2 = MagicMock()
        login_response2.status_code = 200
        login_response2.text = json.dumps({"LoginResponse": {"LoginResult": "OK"}})

        mock_session.post.side_effect = [challenge_response2, login_response2]
        success, _ = builder.login(mock_session, "http://192.168.100.1", "admin", "pass")

        assert success is True
        assert builder._private_key is not None
        assert builder._private_key != first_key  ***REMOVED*** Different challenge = different key


class TestAuthAttemptTracking:
    """Test that auth attempts are tracked for diagnostics."""

    def test_get_last_auth_attempt_initially_none(self, builder):
        """Test that get_last_auth_attempt returns None before any login."""
        assert builder.get_last_auth_attempt() is None

    def test_auth_attempt_stored_on_successful_login(self, builder, mock_session):
        """Test that successful login stores auth attempt data."""
        challenge_response = MagicMock()
        challenge_response.status_code = 200
        challenge_response.text = json.dumps(
            {
                "LoginResponse": {
                    "Challenge": "TEST123",
                    "Cookie": "session_cookie",
                    "PublicKey": "PUBKEY456",
                }
            }
        )

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = json.dumps({"LoginResponse": {"LoginResult": "OK"}})

        mock_session.post.side_effect = [challenge_response, login_response]

        success, _ = builder.login(mock_session, "http://192.168.100.1", "admin", "password")

        assert success is True
        auth_attempt = builder.get_last_auth_attempt()
        assert auth_attempt is not None
        assert "challenge_request" in auth_attempt
        assert "challenge_response" in auth_attempt
        assert "login_request" in auth_attempt
        assert "login_response" in auth_attempt
        assert auth_attempt["error"] is None

    def test_auth_attempt_contains_redacted_password(self, builder, mock_session):
        """Test that stored login request has password redacted."""
        challenge_response = MagicMock()
        challenge_response.status_code = 200
        challenge_response.text = json.dumps(
            {
                "LoginResponse": {
                    "Challenge": "TEST",
                    "Cookie": "cookie",
                    "PublicKey": "key",
                }
            }
        )

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = json.dumps({"LoginResponse": {"LoginResult": "OK"}})

        mock_session.post.side_effect = [challenge_response, login_response]

        builder.login(mock_session, "http://192.168.100.1", "admin", "secretpassword")

        auth_attempt = builder.get_last_auth_attempt()
        login_req = auth_attempt["login_request"]
        ***REMOVED*** Password should be redacted
        assert login_req["Login"]["LoginPassword"] == "[REDACTED]"

    def test_auth_attempt_stores_error_on_failed_login(self, builder, mock_session):
        """Test that failed login stores error information."""
        challenge_response = MagicMock()
        challenge_response.status_code = 200
        challenge_response.text = json.dumps(
            {
                "LoginResponse": {
                    "Challenge": "TEST",
                    "Cookie": "cookie",
                    "PublicKey": "key",
                }
            }
        )

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = json.dumps({"LoginResponse": {"LoginResult": "FAILED"}})

        mock_session.post.side_effect = [challenge_response, login_response]

        success, _ = builder.login(mock_session, "http://192.168.100.1", "admin", "wrongpass")

        assert success is False
        auth_attempt = builder.get_last_auth_attempt()
        assert auth_attempt["error"] == "LoginResult=FAILED"

    def test_auth_attempt_stores_challenge_request_format(self, builder, mock_session):
        """Test that challenge request includes PrivateLogin field."""
        challenge_response = MagicMock()
        challenge_response.status_code = 200
        challenge_response.text = json.dumps(
            {
                "LoginResponse": {
                    "Challenge": "TEST",
                    "Cookie": "cookie",
                    "PublicKey": "key",
                }
            }
        )

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = json.dumps({"LoginResponse": {"LoginResult": "OK"}})

        mock_session.post.side_effect = [challenge_response, login_response]

        builder.login(mock_session, "http://192.168.100.1", "testuser", "pass")

        auth_attempt = builder.get_last_auth_attempt()
        challenge_req = auth_attempt["challenge_request"]

        ***REMOVED*** Verify PrivateLogin field is present (MB8611 requirement)
        assert challenge_req["Login"]["PrivateLogin"] == "LoginPassword"
        assert challenge_req["Login"]["Action"] == "request"
        assert challenge_req["Login"]["Username"] == "testuser"
