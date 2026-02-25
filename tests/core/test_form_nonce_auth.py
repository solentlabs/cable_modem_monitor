"""Tests for FormNonceAuthStrategy.

Tests the form_nonce authentication strategy used by ARRIS SB6190 (firmware 9.1.103+).
Based on HAR capture from Issue #93 (@HenryGeorge1978).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.cable_modem_monitor.core.auth.configs import FormNonceAuthConfig
from custom_components.cable_modem_monitor.core.auth.strategies.form_nonce import (
    FormNonceAuthStrategy,
)
from custom_components.cable_modem_monitor.core.auth.types import AuthErrorType


class TestFormNonceAuthStrategy:
    """Tests for FormNonceAuthStrategy."""

    @pytest.fixture
    def strategy(self):
        """Create strategy instance."""
        return FormNonceAuthStrategy()

    @pytest.fixture
    def config(self):
        """Create default SB6190 config."""
        return FormNonceAuthConfig(
            endpoint="/cgi-bin/adv_pwd_cgi",
            username_field="username",
            password_field="password",
            nonce_field="ar_nonce",
            nonce_length=8,
            success_prefix="Url:",
            error_prefix="Error:",
            timeout=10,
        )

    @pytest.fixture
    def mock_session(self):
        """Create mock session."""
        session = MagicMock()
        session.verify = True
        return session

    def test_login_success(self, strategy, config, mock_session):
        """Test successful login with redirect response."""
        # Mock login POST response
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = "Url:/cgi-bin/status"

        # Mock data page GET response
        data_response = MagicMock()
        data_response.text = "<html>Downstream Bonded Channels</html>"

        mock_session.post.return_value = login_response
        mock_session.get.return_value = data_response

        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password123",
            config,
        )

        assert result.success is True
        assert "Downstream Bonded Channels" in result.response_html

        # Verify POST was made with correct fields
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        form_data = call_args.kwargs["data"]
        assert form_data["username"] == "admin"
        assert form_data["password"] == "password123"
        assert "ar_nonce" in form_data
        assert len(form_data["ar_nonce"]) == 8
        assert form_data["ar_nonce"].isdigit()

    def test_login_invalid_credentials(self, strategy, config, mock_session):
        """Test login with invalid credentials."""
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = "Error:Invalid password"

        mock_session.post.return_value = login_response

        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "wrongpassword",
            config,
        )

        assert result.success is False
        assert result.error_type == AuthErrorType.INVALID_CREDENTIALS
        assert "Invalid password" in result.error_message

    def test_login_missing_credentials(self, strategy, config, mock_session):
        """Test login without credentials."""
        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            None,
            None,
            config,
        )

        assert result.success is False
        assert result.error_type == AuthErrorType.MISSING_CREDENTIALS

    def test_login_unexpected_response(self, strategy, config, mock_session):
        """Test handling of unexpected response format."""
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = "<html>Some unexpected HTML</html>"

        mock_session.post.return_value = login_response

        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            config,
        )

        assert result.success is False
        assert result.error_type == AuthErrorType.UNKNOWN_ERROR

    def test_login_connection_error(self, strategy, config, mock_session):
        """Test handling of connection errors."""
        mock_session.post.side_effect = Exception("Connection refused")

        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            config,
        )

        assert result.success is False
        assert result.error_type == AuthErrorType.CONNECTION_FAILED

    def test_nonce_generation(self, strategy, config, mock_session):
        """Test that nonce is random and correct length."""
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = "Url:/cgi-bin/status"

        data_response = MagicMock()
        data_response.text = "<html></html>"

        mock_session.post.return_value = login_response
        mock_session.get.return_value = data_response

        # Call login twice to verify different nonces
        strategy.login(mock_session, "http://192.168.100.1", "admin", "pass", config)
        first_nonce = mock_session.post.call_args.kwargs["data"]["ar_nonce"]

        strategy.login(mock_session, "http://192.168.100.1", "admin", "pass", config)
        second_nonce = mock_session.post.call_args.kwargs["data"]["ar_nonce"]

        # Both should be 8-digit numeric strings
        assert len(first_nonce) == 8
        assert len(second_nonce) == 8
        assert first_nonce.isdigit()
        assert second_nonce.isdigit()
        # Very unlikely to be the same (1 in 100 million)
        # But don't assert this as it could randomly fail

    def test_xhr_header_included(self, strategy, config, mock_session):
        """Test that X-Requested-With header is included (AJAX marker)."""
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = "Url:/status"

        data_response = MagicMock()
        data_response.text = "<html></html>"

        mock_session.post.return_value = login_response
        mock_session.get.return_value = data_response

        strategy.login(mock_session, "http://192.168.100.1", "admin", "pass", config)

        headers = mock_session.post.call_args.kwargs["headers"]
        assert headers["X-Requested-With"] == "XMLHttpRequest"

    def test_wrong_config_type(self, strategy, mock_session):
        """Test that wrong config type is rejected."""
        from custom_components.cable_modem_monitor.core.auth.configs import FormAuthConfig

        wrong_config = FormAuthConfig(timeout=10)

        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            wrong_config,
        )

        assert result.success is False
        assert result.error_type == AuthErrorType.STRATEGY_NOT_CONFIGURED
