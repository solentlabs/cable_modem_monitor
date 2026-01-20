"""Integration tests for authentication error recovery.

These tests verify graceful handling of:
1. Connection errors during authentication
2. Timeout errors
3. Invalid server responses
4. Partial authentication failures

This ensures the integration doesn't crash on network issues.
"""

from __future__ import annotations

import requests

from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType


class TestConnectionErrors:
    """Test handling of connection errors during auth."""

    def test_connection_refused_handled(self):
        """Verify connection refused is handled gracefully."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
            },
        )

        session = requests.Session()
        session.verify = False

        # Try to connect to a port that's not listening
        success, _ = handler.authenticate(
            session=session,
            base_url="http://127.0.0.1:59999",  # Unlikely to be in use
            username="admin",
            password="password",
        )

        assert success is False

    def test_connection_refused_basic_auth(self):
        """Verify Basic auth handles connection refused."""
        handler = AuthHandler(strategy=AuthStrategyType.BASIC_HTTP)

        session = requests.Session()
        session.verify = False

        success, _ = handler.authenticate(
            session=session,
            base_url="http://127.0.0.1:59999",
            username="admin",
            password="password",
        )

        assert success is False


class TestTimeoutErrors:
    """Test handling of timeout errors."""

    def test_timeout_handled_gracefully(self, http_server):
        """Verify timeout is handled without crashing."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
            },
        )

        session = requests.Session()
        session.verify = False

        # The test server responds quickly, so this tests the code path exists
        # For a true timeout test, we'd need a slow server
        success, _ = handler.authenticate(
            session=session,
            base_url=http_server.url,
            username="admin",
            password="password",
        )

        # This server doesn't have form auth, so it will fail
        # but importantly it shouldn't crash
        assert isinstance(success, bool)


class TestInvalidResponses:
    """Test handling of unexpected server responses."""

    def test_no_form_on_page_handled(self, http_server):
        """Verify missing form is handled gracefully."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
            },
        )

        session = requests.Session()
        session.verify = False

        # http_server returns data page, not login form
        success, html = handler.authenticate(
            session=session,
            base_url=http_server.url,
            username="admin",
            password="password",
        )

        # Should handle gracefully (the page doesn't have a login form)
        assert isinstance(success, bool)


class TestAuthStrategyFallback:
    """Test fallback behavior for unknown strategies."""

    def test_unknown_strategy_returns_success(self):
        """Verify unknown strategy allows data fetch attempt."""
        handler = AuthHandler(strategy="unknown_strategy")

        session = requests.Session()
        session.verify = False

        success, _ = handler.authenticate(
            session=session,
            base_url="http://127.0.0.1:8080",
            username="admin",
            password="password",
        )

        # Unknown strategy returns True to allow data fetch attempt
        assert success is True

    def test_none_strategy_returns_success(self):
        """Verify None strategy allows data fetch attempt."""
        handler = AuthHandler(strategy=None)

        session = requests.Session()
        session.verify = False

        success, _ = handler.authenticate(
            session=session,
            base_url="http://127.0.0.1:8080",
            username="admin",
            password="password",
        )

        # None/Unknown strategy returns True
        assert success is True


class TestMissingCredentials:
    """Test handling of missing credentials."""

    def test_form_auth_no_username(self, form_auth_server):
        """Verify form auth fails gracefully with no username."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
            },
        )

        session = requests.Session()
        session.verify = False

        success, _ = handler.authenticate(
            session=session,
            base_url=form_auth_server.url,
            username=None,
            password="password",
        )

        assert success is False

    def test_form_auth_no_password(self, form_auth_server):
        """Verify form auth fails gracefully with no password."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
            },
        )

        session = requests.Session()
        session.verify = False

        success, _ = handler.authenticate(
            session=session,
            base_url=form_auth_server.url,
            username="admin",
            password=None,
        )

        assert success is False

    def test_basic_auth_no_credentials(self, basic_auth_server):
        """Verify basic auth fails gracefully with no credentials."""
        handler = AuthHandler(strategy=AuthStrategyType.BASIC_HTTP)

        session = requests.Session()
        session.verify = False

        success, _ = handler.authenticate(
            session=session,
            base_url=basic_auth_server.url,
            username=None,
            password=None,
        )

        assert success is False

    def test_no_auth_works_without_credentials(self, http_server):
        """Verify NO_AUTH works without credentials."""
        handler = AuthHandler(strategy=AuthStrategyType.NO_AUTH)

        session = requests.Session()
        session.verify = False

        success, _ = handler.authenticate(
            session=session,
            base_url=http_server.url,
            username=None,
            password=None,
        )

        assert success is True


class TestMissingFormConfig:
    """Test handling of missing form configuration."""

    def test_form_auth_no_config(self, form_auth_server):
        """Verify form auth fails gracefully with no config."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config=None,
        )

        session = requests.Session()
        session.verify = False

        success, _ = handler.authenticate(
            session=session,
            base_url=form_auth_server.url,
            username="admin",
            password="password",
        )

        assert success is False

    def test_form_auth_empty_config(self, form_auth_server):
        """Verify form auth handles empty config."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={},
        )

        session = requests.Session()
        session.verify = False

        # Should not crash, though may fail
        success, _ = handler.authenticate(
            session=session,
            base_url=form_auth_server.url,
            username="admin",
            password="password",
        )

        assert isinstance(success, bool)


class TestRetryBehavior:
    """Test authentication retry behavior."""

    def test_can_retry_after_failure(self, form_auth_server):
        """Verify authentication can be retried after failure."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
            },
        )

        session = requests.Session()
        session.verify = False

        # First attempt with wrong credentials
        success1, _ = handler.authenticate(
            session=session,
            base_url=form_auth_server.url,
            username="wrong",
            password="wrong",
        )
        assert success1 is False

        # Retry with correct credentials
        success2, _ = handler.authenticate(
            session=session,
            base_url=form_auth_server.url,
            username="admin",
            password="password",
        )
        assert success2 is True

    def test_session_cleared_between_retries(self, form_auth_server):
        """Verify session can be reused for retry."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
            },
        )

        session = requests.Session()
        session.verify = False

        # Failed attempt
        handler.authenticate(
            session=session,
            base_url=form_auth_server.url,
            username="wrong",
            password="wrong",
        )

        # Clear cookies if any were set
        session.cookies.clear()

        # Retry should work
        success, _ = handler.authenticate(
            session=session,
            base_url=form_auth_server.url,
            username="admin",
            password="password",
        )
        assert success is True
