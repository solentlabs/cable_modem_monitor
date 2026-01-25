"""Tests for FormAjaxAuthStrategy.

This tests the AJAX-based form authentication where login is handled via
JavaScript XMLHttpRequest instead of traditional form submission.

Auth flow:
1. Client generates random nonce (configurable length)
2. Credentials are formatted and base64-encoded:
   base64(urlencode("username={user}:password={pass}"))
3. POST to endpoint with arguments + nonce
4. Response is plain text: "Url:/path" (success) or "Error:msg" (failure)
"""

from __future__ import annotations

import base64
from unittest.mock import MagicMock
from urllib.parse import quote

import pytest
import requests

from custom_components.cable_modem_monitor.core.auth import AuthStrategyType
from custom_components.cable_modem_monitor.core.auth.configs import FormAjaxAuthConfig
from custom_components.cable_modem_monitor.core.auth.strategies.form_ajax import (
    FormAjaxAuthStrategy,
)
from custom_components.cable_modem_monitor.core.auth.types import AuthErrorType

# =============================================================================
# Test Data
# =============================================================================

# Simulated successful login response
SUCCESS_RESPONSE = "Url:/index.html"

# Simulated failed login response
ERROR_RESPONSE = "Error:Invalid password"

# Simulated post-login page HTML
POST_LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head><title>Modem Status</title></head>
<body>
<h1>Connection Status</h1>
<p>Status: OK</p>
</body>
</html>
"""


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
    """Create a mock requests session."""
    session = MagicMock(spec=requests.Session)
    session.verify = False
    session.cookies = MagicMock()
    session.cookies.keys.return_value = []
    return session


@pytest.fixture
def form_ajax_config():
    """Default FormAjaxAuthConfig with typical AJAX login settings."""
    return FormAjaxAuthConfig(
        strategy=AuthStrategyType.FORM_AJAX,
        endpoint="/cgi-bin/adv_pwd_cgi",
        nonce_field="ar_nonce",
        nonce_length=8,
        arguments_field="arguments",
        credential_format="username={username}:password={password}",
        success_prefix="Url:",
        error_prefix="Error:",
    )


# =============================================================================
# Tests: Successful Login
# =============================================================================


class TestFormAjaxSuccessfulLogin:
    """Test successful AJAX login flow."""

    def test_successful_login_returns_ok(self, mock_session, form_ajax_config):
        """Successful login returns AuthResult.ok with post-login HTML."""
        strategy = FormAjaxAuthStrategy()

        # AJAX endpoint returns success
        ajax_response = MagicMock()
        ajax_response.status_code = 200
        ajax_response.text = SUCCESS_RESPONSE

        # Follow-up GET returns post-login page
        post_login_response = MagicMock()
        post_login_response.status_code = 200
        post_login_response.text = POST_LOGIN_HTML

        mock_session.post.return_value = ajax_response
        mock_session.get.return_value = post_login_response

        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password123",
            form_ajax_config,
        )

        assert result.success is True
        assert "Connection Status" in result.response_html

    def test_posts_to_correct_endpoint(self, mock_session, form_ajax_config):
        """Verifies POST is sent to configured endpoint."""
        strategy = FormAjaxAuthStrategy()

        ajax_response = MagicMock()
        ajax_response.status_code = 200
        ajax_response.text = SUCCESS_RESPONSE

        post_login_response = MagicMock()
        post_login_response.status_code = 200
        post_login_response.text = POST_LOGIN_HTML

        mock_session.post.return_value = ajax_response
        mock_session.get.return_value = post_login_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password123",
            form_ajax_config,
        )

        mock_session.post.assert_called_once()
        called_url = mock_session.post.call_args[0][0]
        assert called_url == "http://192.168.100.1/cgi-bin/adv_pwd_cgi"

    def test_sends_correct_form_data_structure(self, mock_session, form_ajax_config):
        """Verifies form data contains arguments and nonce fields."""
        strategy = FormAjaxAuthStrategy()

        ajax_response = MagicMock()
        ajax_response.status_code = 200
        ajax_response.text = SUCCESS_RESPONSE

        post_login_response = MagicMock()
        post_login_response.status_code = 200
        post_login_response.text = POST_LOGIN_HTML

        mock_session.post.return_value = ajax_response
        mock_session.get.return_value = post_login_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password123",
            form_ajax_config,
        )

        call_kwargs = mock_session.post.call_args[1]
        form_data = call_kwargs["data"]

        # Should have both fields
        assert "arguments" in form_data
        assert "ar_nonce" in form_data

        # Nonce should be 8 digits
        assert len(form_data["ar_nonce"]) == 8
        assert form_data["ar_nonce"].isdigit()

    def test_credentials_are_properly_encoded(self, mock_session, form_ajax_config):
        """Verifies credentials are base64(urlencode(format_string))."""
        strategy = FormAjaxAuthStrategy()

        ajax_response = MagicMock()
        ajax_response.status_code = 200
        ajax_response.text = SUCCESS_RESPONSE

        post_login_response = MagicMock()
        post_login_response.status_code = 200
        post_login_response.text = POST_LOGIN_HTML

        mock_session.post.return_value = ajax_response
        mock_session.get.return_value = post_login_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password123",
            form_ajax_config,
        )

        call_kwargs = mock_session.post.call_args[1]
        form_data = call_kwargs["data"]

        # Decode and verify
        encoded_args = form_data["arguments"]
        decoded_bytes = base64.b64decode(encoded_args)
        decoded_str = decoded_bytes.decode("utf-8")

        # Should be URL-encoded "username=admin:password=password123"
        expected = quote("username=admin:password=password123", safe="")
        assert decoded_str == expected

    def test_sends_ajax_headers(self, mock_session, form_ajax_config):
        """Verifies X-Requested-With header is sent (AJAX indicator)."""
        strategy = FormAjaxAuthStrategy()

        ajax_response = MagicMock()
        ajax_response.status_code = 200
        ajax_response.text = SUCCESS_RESPONSE

        post_login_response = MagicMock()
        post_login_response.status_code = 200
        post_login_response.text = POST_LOGIN_HTML

        mock_session.post.return_value = ajax_response
        mock_session.get.return_value = post_login_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password123",
            form_ajax_config,
        )

        call_kwargs = mock_session.post.call_args[1]
        headers = call_kwargs["headers"]

        assert headers["X-Requested-With"] == "XMLHttpRequest"
        assert "Referer" in headers


# =============================================================================
# Tests: Failed Login
# =============================================================================


class TestFormAjaxFailedLogin:
    """Test AJAX login failure handling."""

    def test_error_response_returns_failure(self, mock_session, form_ajax_config):
        """Error: prefix in response returns AuthResult.fail."""
        strategy = FormAjaxAuthStrategy()

        ajax_response = MagicMock()
        ajax_response.status_code = 200
        ajax_response.text = ERROR_RESPONSE

        mock_session.post.return_value = ajax_response

        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "wrongpassword",
            form_ajax_config,
        )

        assert result.success is False
        assert result.error_type == AuthErrorType.INVALID_CREDENTIALS
        assert "Invalid password" in result.error_message

    def test_unexpected_response_returns_failure(self, mock_session, form_ajax_config):
        """Unexpected response format returns AuthResult.fail."""
        strategy = FormAjaxAuthStrategy()

        ajax_response = MagicMock()
        ajax_response.status_code = 200
        ajax_response.text = "Something unexpected happened"

        mock_session.post.return_value = ajax_response

        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            form_ajax_config,
        )

        assert result.success is False
        assert result.error_type == AuthErrorType.UNKNOWN_ERROR

    def test_connection_error_returns_failure(self, mock_session, form_ajax_config):
        """Connection error returns AuthResult.fail."""
        strategy = FormAjaxAuthStrategy()

        mock_session.post.side_effect = requests.exceptions.ConnectionError("timeout")

        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            form_ajax_config,
        )

        assert result.success is False
        assert result.error_type == AuthErrorType.CONNECTION_FAILED


# =============================================================================
# Tests: Credential Validation
# =============================================================================


class TestFormAjaxCredentialValidation:
    """Test credential validation."""

    def test_missing_username_returns_failure(self, mock_session, form_ajax_config):
        """Missing username returns AuthResult.fail."""
        strategy = FormAjaxAuthStrategy()

        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            None,
            "password",
            form_ajax_config,
        )

        assert result.success is False
        assert result.error_type == AuthErrorType.MISSING_CREDENTIALS
        mock_session.post.assert_not_called()

    def test_missing_password_returns_failure(self, mock_session, form_ajax_config):
        """Missing password returns AuthResult.fail."""
        strategy = FormAjaxAuthStrategy()

        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            None,
            form_ajax_config,
        )

        assert result.success is False
        assert result.error_type == AuthErrorType.MISSING_CREDENTIALS
        mock_session.post.assert_not_called()

    def test_wrong_config_type_returns_failure(self, mock_session):
        """Wrong config type returns AuthResult.fail."""
        from custom_components.cable_modem_monitor.core.auth.configs import FormAuthConfig

        wrong_config = FormAuthConfig(
            strategy=AuthStrategyType.FORM_PLAIN,
            login_url="/login",
        )

        strategy = FormAjaxAuthStrategy()

        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            wrong_config,
        )

        assert result.success is False
        assert result.error_type == AuthErrorType.STRATEGY_NOT_CONFIGURED


# =============================================================================
# Tests: Nonce Generation
# =============================================================================


class TestFormAjaxNonceGeneration:
    """Test nonce generation."""

    def test_nonce_is_random(self, mock_session, form_ajax_config):
        """Nonce is different on each call."""
        strategy = FormAjaxAuthStrategy()

        ajax_response = MagicMock()
        ajax_response.status_code = 200
        ajax_response.text = SUCCESS_RESPONSE

        post_login_response = MagicMock()
        post_login_response.status_code = 200
        post_login_response.text = POST_LOGIN_HTML

        mock_session.post.return_value = ajax_response
        mock_session.get.return_value = post_login_response

        # First login
        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            form_ajax_config,
        )
        first_nonce = mock_session.post.call_args[1]["data"]["ar_nonce"]

        # Reset mock
        mock_session.reset_mock()
        mock_session.post.return_value = ajax_response
        mock_session.get.return_value = post_login_response

        # Second login
        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            form_ajax_config,
        )
        second_nonce = mock_session.post.call_args[1]["data"]["ar_nonce"]

        # Nonces should be different (statistically very likely)
        assert first_nonce != second_nonce

    def test_custom_nonce_length(self, mock_session):
        """Custom nonce length is respected."""
        config = FormAjaxAuthConfig(
            strategy=AuthStrategyType.FORM_AJAX,
            endpoint="/login",
            nonce_length=12,  # Custom length
        )

        strategy = FormAjaxAuthStrategy()

        ajax_response = MagicMock()
        ajax_response.status_code = 200
        ajax_response.text = "Url:/home"

        post_login_response = MagicMock()
        post_login_response.status_code = 200
        post_login_response.text = "<html>OK</html>"

        mock_session.post.return_value = ajax_response
        mock_session.get.return_value = post_login_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            config,
        )

        nonce = mock_session.post.call_args[1]["data"]["ar_nonce"]
        assert len(nonce) == 12


# =============================================================================
# Tests: Custom Configuration
# =============================================================================


class TestFormAjaxCustomConfig:
    """Test custom configuration options."""

    def test_custom_endpoint(self, mock_session):
        """Custom endpoint is used."""
        config = FormAjaxAuthConfig(
            strategy=AuthStrategyType.FORM_AJAX,
            endpoint="/custom/ajax/login",
        )

        strategy = FormAjaxAuthStrategy()

        ajax_response = MagicMock()
        ajax_response.status_code = 200
        ajax_response.text = "Url:/home"

        post_login_response = MagicMock()
        post_login_response.status_code = 200
        post_login_response.text = "<html>OK</html>"

        mock_session.post.return_value = ajax_response
        mock_session.get.return_value = post_login_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            config,
        )

        called_url = mock_session.post.call_args[0][0]
        assert called_url == "http://192.168.100.1/custom/ajax/login"

    def test_custom_field_names(self, mock_session):
        """Custom field names are used."""
        config = FormAjaxAuthConfig(
            strategy=AuthStrategyType.FORM_AJAX,
            endpoint="/login",
            nonce_field="my_nonce",
            arguments_field="my_args",
        )

        strategy = FormAjaxAuthStrategy()

        ajax_response = MagicMock()
        ajax_response.status_code = 200
        ajax_response.text = "Url:/home"

        post_login_response = MagicMock()
        post_login_response.status_code = 200
        post_login_response.text = "<html>OK</html>"

        mock_session.post.return_value = ajax_response
        mock_session.get.return_value = post_login_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            config,
        )

        form_data = mock_session.post.call_args[1]["data"]
        assert "my_nonce" in form_data
        assert "my_args" in form_data

    def test_custom_credential_format(self, mock_session):
        """Custom credential format is used."""
        config = FormAjaxAuthConfig(
            strategy=AuthStrategyType.FORM_AJAX,
            endpoint="/login",
            credential_format="user={username}&pass={password}",
        )

        strategy = FormAjaxAuthStrategy()

        ajax_response = MagicMock()
        ajax_response.status_code = 200
        ajax_response.text = "Url:/home"

        post_login_response = MagicMock()
        post_login_response.status_code = 200
        post_login_response.text = "<html>OK</html>"

        mock_session.post.return_value = ajax_response
        mock_session.get.return_value = post_login_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "mypass",
            config,
        )

        form_data = mock_session.post.call_args[1]["data"]
        decoded = base64.b64decode(form_data["arguments"]).decode("utf-8")

        # Should be URL-encoded "user=admin&pass=mypass"
        expected = quote("user=admin&pass=mypass", safe="")
        assert decoded == expected

    def test_custom_response_prefixes(self, mock_session):
        """Custom success/error prefixes are recognized."""
        config = FormAjaxAuthConfig(
            strategy=AuthStrategyType.FORM_AJAX,
            endpoint="/login",
            success_prefix="OK:",
            error_prefix="FAIL:",
        )

        strategy = FormAjaxAuthStrategy()

        # Test success with custom prefix
        ajax_response = MagicMock()
        ajax_response.status_code = 200
        ajax_response.text = "OK:/dashboard"

        post_login_response = MagicMock()
        post_login_response.status_code = 200
        post_login_response.text = "<html>Dashboard</html>"

        mock_session.post.return_value = ajax_response
        mock_session.get.return_value = post_login_response

        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            config,
        )

        assert result.success is True

        # Test failure with custom prefix
        mock_session.reset_mock()
        ajax_response.text = "FAIL:Bad credentials"
        mock_session.post.return_value = ajax_response

        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            config,
        )

        assert result.success is False
        assert "Bad credentials" in result.error_message
