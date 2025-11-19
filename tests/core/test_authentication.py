"""Tests for Authentication Strategies."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from custom_components.cable_modem_monitor.core.auth_config import AuthStrategyType, FormAuthConfig
from custom_components.cable_modem_monitor.core.authentication import (
    BasicHttpAuthStrategy,
    FormPlainAuthStrategy,
    NoAuthStrategy,
)


@pytest.fixture
def mock_session():
    """Create a mock requests session."""
    session = MagicMock(spec=requests.Session)
    session.verify = False
    return session


@pytest.fixture
def form_auth_config():
    """Create a form auth configuration."""
    return FormAuthConfig(
        strategy=AuthStrategyType.FORM_PLAIN,
        login_url="/login.asp",
        username_field="username",
        password_field="password",
        success_indicator="/status.asp",
    )


class TestNoAuthStrategy:
    """Test NoAuthStrategy."""

    def test_no_auth_always_succeeds(self, mock_session):
        """Test that NoAuthStrategy always returns success."""
        strategy = NoAuthStrategy()
        config = MagicMock()

        success, response = strategy.login(mock_session, "http://192.168.1.1", None, None, config)

        assert success is True
        assert response is None

    def test_no_auth_with_credentials(self, mock_session):
        """Test NoAuthStrategy ignores credentials."""
        strategy = NoAuthStrategy()
        config = MagicMock()

        success, response = strategy.login(mock_session, "http://192.168.1.1", "admin", "password", config)

        assert success is True
        assert response is None


class TestBasicHttpAuthStrategy:
    """Test BasicHttpAuthStrategy."""

    def test_basic_auth_sets_session_auth(self, mock_session):
        """Test that Basic Auth sets credentials on session."""
        strategy = BasicHttpAuthStrategy()
        config = MagicMock()

        success, response = strategy.login(mock_session, "http://192.168.1.1", "admin", "password", config)

        assert success is True
        assert response is None
        assert mock_session.auth == ("admin", "password")

    def test_basic_auth_without_credentials(self, mock_session):
        """Test Basic Auth without credentials."""
        strategy = BasicHttpAuthStrategy()
        config = MagicMock()

        success, response = strategy.login(mock_session, "http://192.168.1.1", None, None, config)

        assert success is True
        assert response is None
        assert not hasattr(mock_session, "auth") or mock_session.auth is None

    def test_basic_auth_missing_username(self, mock_session):
        """Test Basic Auth with missing username."""
        strategy = BasicHttpAuthStrategy()
        config = MagicMock()

        success, response = strategy.login(mock_session, "http://192.168.1.1", None, "password", config)

        assert success is True
        assert response is None

    def test_basic_auth_missing_password(self, mock_session):
        """Test Basic Auth with missing password."""
        strategy = BasicHttpAuthStrategy()
        config = MagicMock()

        success, response = strategy.login(mock_session, "http://192.168.1.1", "admin", None, config)

        assert success is True
        assert response is None


class TestFormPlainAuthStrategy:
    """Test FormPlainAuthStrategy."""

    def test_form_auth_success(self, mock_session, form_auth_config):
        """Test successful form authentication."""
        strategy = FormPlainAuthStrategy()

        # Mock successful response
        mock_response = MagicMock()
        mock_response.url = "http://192.168.1.1/status.asp"  # Success indicator
        mock_response.text = "<html>Logged in</html>"
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        success, response = strategy.login(mock_session, "http://192.168.1.1", "admin", "password", form_auth_config)

        assert success is True
        assert response is not None

        # Verify POST call
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "http://192.168.1.1/login.asp"
        assert call_args[1]["data"] == {"username": "admin", "password": "password"}

    def test_form_auth_without_credentials(self, mock_session, form_auth_config):
        """Test form auth without credentials."""
        strategy = FormPlainAuthStrategy()

        success, response = strategy.login(mock_session, "http://192.168.1.1", None, None, form_auth_config)

        assert success is True
        assert response is None
        mock_session.post.assert_not_called()

    def test_form_auth_wrong_config_type(self, mock_session):
        """Test form auth with wrong config type."""
        strategy = FormPlainAuthStrategy()
        wrong_config = MagicMock()  # Not a FormAuthConfig

        success, response = strategy.login(mock_session, "http://192.168.1.1", "admin", "password", wrong_config)

        assert success is False
        assert response is None

    def test_form_auth_large_response_indicator(self, mock_session):
        """Test form auth with size-based success indicator."""
        # Config with digit success indicator (response size check)
        config = FormAuthConfig(
            strategy=AuthStrategyType.FORM_PLAIN,
            login_url="/login.asp",
            username_field="username",
            password_field="password",
            success_indicator="1000",  # Response must be > 1000 bytes
        )

        strategy = FormPlainAuthStrategy()

        # Mock large response
        mock_response = MagicMock()
        mock_response.url = "http://192.168.1.1/other.asp"
        mock_response.text = "x" * 2000  # 2000 bytes
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        success, response = strategy.login(mock_session, "http://192.168.1.1", "admin", "password", config)

        assert success is True


class TestAuthStrategyFactoryPattern:
    """Test that auth strategies can be instantiated and used polymorphically."""

    @pytest.mark.parametrize(
        "strategy_class",
        [
            NoAuthStrategy,
            BasicHttpAuthStrategy,
            FormPlainAuthStrategy,
        ],
    )
    def test_all_strategies_have_login_method(self, strategy_class):
        """Test that all strategies implement login method."""
        strategy = strategy_class()

        assert hasattr(strategy, "login")
        assert callable(strategy.login)
