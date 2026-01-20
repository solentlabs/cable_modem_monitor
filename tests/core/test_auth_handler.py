"""Tests for the AuthHandler class.

This tests the runtime authentication handler that applies stored
authentication strategies during polling.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType


class TestAuthHandlerInit:
    """Test AuthHandler initialization."""

    def test_init_with_string_strategy(self):
        """Test initialization with string strategy."""
        handler = AuthHandler(strategy="basic_http")
        assert handler.strategy == AuthStrategyType.BASIC_HTTP

    def test_init_with_enum_strategy(self):
        """Test initialization with enum strategy."""
        handler = AuthHandler(strategy=AuthStrategyType.FORM_PLAIN)
        assert handler.strategy == AuthStrategyType.FORM_PLAIN

    def test_init_with_none_strategy(self):
        """Test initialization with None strategy."""
        handler = AuthHandler(strategy=None)
        assert handler.strategy == AuthStrategyType.UNKNOWN

    def test_init_with_unknown_string(self):
        """Test initialization with unknown string defaults to UNKNOWN."""
        handler = AuthHandler(strategy="not_a_real_strategy")
        assert handler.strategy == AuthStrategyType.UNKNOWN

    def test_init_with_uppercase_string(self):
        """Test initialization with uppercase string (case-insensitive matching)."""
        # Config entries may store uppercase strategy names
        handler = AuthHandler(strategy="FORM_PLAIN")
        assert handler.strategy == AuthStrategyType.FORM_PLAIN

        handler2 = AuthHandler(strategy="BASIC_HTTP")
        assert handler2.strategy == AuthStrategyType.BASIC_HTTP

    def test_init_with_legacy_form_base64(self):
        """Test that legacy form_base64 strategy maps to form_plain."""
        # form_base64 was consolidated into form_plain - encoding via password_encoding
        handler = AuthHandler(strategy="form_base64")
        assert handler.strategy == AuthStrategyType.FORM_PLAIN

    def test_init_with_form_config(self):
        """Test initialization with form config."""
        form_config = {
            "action": "/login",
            "method": "POST",
            "username_field": "user",
            "password_field": "pass",
        }
        handler = AuthHandler(strategy="form_plain", form_config=form_config)
        assert handler.form_config == form_config


class TestAuthHandlerNoAuth:
    """Test NO_AUTH strategy."""

    def test_no_auth_succeeds_without_credentials(self):
        """Test NO_AUTH strategy succeeds."""
        handler = AuthHandler(strategy=AuthStrategyType.NO_AUTH)
        session = MagicMock()

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username=None,
            password=None,
        )

        assert success is True
        assert html is None


class TestAuthHandlerBasicAuth:
    """Test BASIC_HTTP strategy."""

    def test_basic_auth_sets_session_auth(self):
        """Test Basic Auth sets session.auth but does NOT return HTML.

        Basic auth is per-request (header-based via session.auth), not session-based.
        The handler verifies credentials work but does NOT return HTML because
        the scraper fetches the actual data page with the auth header.
        Returning HTML from the root page would replace the correctly-fetched
        data page HTML, breaking modems like TC4400 where root is a frameset.
        """
        handler = AuthHandler(strategy=AuthStrategyType.BASIC_HTTP)
        session = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.text = "<html>Status Page</html>"
        session.get.return_value = response

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username="admin",
            password="password",
        )

        assert success is True
        assert session.auth == ("admin", "password")
        assert html is None  # Basic auth does NOT return HTML - scraper fetches data page

    def test_basic_auth_fails_without_credentials(self):
        """Test Basic Auth fails without credentials."""
        handler = AuthHandler(strategy=AuthStrategyType.BASIC_HTTP)
        session = MagicMock()

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username=None,
            password=None,
        )

        assert success is False
        assert html is None

    def test_basic_auth_fails_on_401(self):
        """Test Basic Auth fails on 401 response."""
        handler = AuthHandler(strategy=AuthStrategyType.BASIC_HTTP)
        session = MagicMock()
        response = MagicMock()
        response.status_code = 401
        session.get.return_value = response

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username="admin",
            password="wrong",
        )

        assert success is False
        assert session.auth is None  # Should be cleared on failure

    def test_basic_auth_handles_exception(self):
        """Test Basic Auth handles connection exception."""
        handler = AuthHandler(strategy=AuthStrategyType.BASIC_HTTP)
        session = MagicMock()
        session.get.side_effect = Exception("Connection refused")

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username="admin",
            password="password",
        )

        assert success is False
        assert html is None


class TestAuthHandlerFormAuth:
    """Test FORM_PLAIN strategy."""

    def test_form_auth_submits_form(self):
        """Test form auth submits form data."""
        form_config = {
            "action": "/login",
            "method": "POST",
            "username_field": "user",
            "password_field": "pass",
            "hidden_fields": {"csrf": "token123"},
        }
        handler = AuthHandler(strategy=AuthStrategyType.FORM_PLAIN, form_config=form_config)
        session = MagicMock()

        # Mock post response (after form submission)
        # This response doesn't have a password field, so it's considered success
        post_response = MagicMock()
        post_response.status_code = 302
        post_response.text = "<html>Success Page</html>"

        # Mock get response (not used since form response is already successful)
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.text = "<html>Status Page</html>"

        session.post.return_value = post_response
        session.get.return_value = get_response

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username="admin",
            password="password",
        )

        assert success is True
        # Form response is NOT returned - let scraper fetch data pages
        assert html is None

        # Verify form was submitted correctly
        session.post.assert_called_once()
        call_args = session.post.call_args
        assert call_args[0][0] == "http://192.168.100.1/login"
        assert call_args[1]["data"]["user"] == "admin"
        assert call_args[1]["data"]["pass"] == "password"
        assert call_args[1]["data"]["csrf"] == "token123"

    def test_form_auth_fails_without_credentials(self):
        """Test form auth fails without credentials."""
        form_config = {
            "action": "/login",
            "method": "POST",
            "username_field": "user",
            "password_field": "pass",
        }
        handler = AuthHandler(strategy=AuthStrategyType.FORM_PLAIN, form_config=form_config)
        session = MagicMock()

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username=None,
            password=None,
        )

        assert success is False
        assert html is None

    def test_form_auth_fails_without_form_config(self):
        """Test form auth fails without form config."""
        handler = AuthHandler(strategy=AuthStrategyType.FORM_PLAIN, form_config=None)
        session = MagicMock()

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username="admin",
            password="password",
        )

        assert success is False
        assert html is None

    def test_form_auth_detects_login_page_failure(self):
        """Test form auth detects when base URL still shows login page after form submission."""
        form_config = {
            "action": "/login",
            "method": "POST",
            "username_field": "user",
            "password_field": "pass",
        }
        handler = AuthHandler(strategy=AuthStrategyType.FORM_PLAIN, form_config=form_config)
        session = MagicMock()

        # Post returns login page again (wrong credentials - modem re-shows login form)
        post_response = MagicMock()
        post_response.status_code = 200
        post_response.text = '<html>Error: Invalid credentials<input type="password"></html>'
        session.post.return_value = post_response

        # Base URL also shows login page
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.text = '<html><form><input type="password" name="pass"></form></html>'
        session.get.return_value = get_response

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username="admin",
            password="wrong",
        )

        assert success is False
        assert html is None

    def test_form_auth_succeeds_when_form_action_has_password_but_base_url_does_not(self):
        """Test form auth succeeds when form action response has password field but base URL doesn't.

        Some modems have this pattern: the login form action returns a page with a password field,
        but after successful login, the data URL shows data without a login form.
        """
        form_config = {
            "action": "/goform/login",
            "method": "POST",
            "username_field": "loginUsername",
            "password_field": "loginPassword",
        }
        handler = AuthHandler(strategy=AuthStrategyType.FORM_PLAIN, form_config=form_config)
        session = MagicMock()

        # Form action response has a password field (status page with form)
        post_response = MagicMock()
        post_response.status_code = 200
        post_response.text = '<html><form><input type="password" name="pwd"></form>Status</html>'
        session.post.return_value = post_response

        # But base URL shows data page (no login form) - this is the real success indicator
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.text = "<html><h1>Modem Status</h1><table>Channel data...</table></html>"
        session.get.return_value = get_response

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1/MotoSwInfo.asp",
            username="admin",
            password="password",
        )

        assert success is True
        assert html is not None
        assert "Modem Status" in html

    def test_form_auth_uses_get_method(self):
        """Test form auth uses GET when method is GET."""
        form_config = {
            "action": "/auth",
            "method": "GET",
            "username_field": "user",
            "password_field": "pass",
        }
        handler = AuthHandler(strategy=AuthStrategyType.FORM_PLAIN, form_config=form_config)
        session = MagicMock()

        get_response = MagicMock()
        get_response.status_code = 200
        get_response.text = "<html>Status Page</html>"
        session.get.return_value = get_response

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username="admin",
            password="password",
        )

        assert success is True
        session.get.assert_called()

    def test_form_auth_base64_encodes_password(self):
        """Test FORM_PLAIN strategy with password_encoding=base64 encodes the password."""
        import base64

        form_config = {
            "action": "/goform/login",
            "method": "POST",
            "username_field": "loginUsername",
            "password_field": "loginPassword",
            "password_encoding": "base64",
        }
        handler = AuthHandler(strategy=AuthStrategyType.FORM_PLAIN, form_config=form_config)
        session = MagicMock()

        # Mock post response
        post_response = MagicMock()
        post_response.status_code = 200
        post_response.text = "<html>Success</html>"

        # Mock get response
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.text = "<html>Status Page</html>"

        session.post.return_value = post_response
        session.get.return_value = get_response

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username="admin",
            password="mypassword",
        )

        assert success is True

        # Verify password was base64-encoded in the form data
        call_args = session.post.call_args
        form_data = call_args[1]["data"]
        expected_encoded = base64.b64encode(b"mypassword").decode("utf-8")
        assert form_data["loginPassword"] == expected_encoded
        assert form_data["loginUsername"] == "admin"

    def test_form_auth_combined_credentials(self):
        """Test FORM_PLAIN strategy with combined credentials (SB6190-style)."""
        import base64
        from urllib.parse import quote

        form_config = {
            "action": "/cgi-bin/adv_pwd_cgi",
            "method": "POST",
            "username_field": None,
            "password_field": None,
            "hidden_fields": {"ar_nonce": "abc123"},
            "credential_field": "arguments",
            "credential_format": "username={username}:password={password}",
            "password_encoding": "base64",
        }
        handler = AuthHandler(strategy=AuthStrategyType.FORM_PLAIN, form_config=form_config)
        session = MagicMock()

        # Mock post response
        post_response = MagicMock()
        post_response.status_code = 200
        post_response.text = "<html>Success</html>"

        # Mock get response
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.text = "<html>Status Page</html>"

        session.post.return_value = post_response
        session.get.return_value = get_response

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username="admin",
            password="secret",
        )

        assert success is True

        # Verify combined credential was encoded correctly
        call_args = session.post.call_args
        form_data = call_args[1]["data"]

        # Expected encoding: url_encode then base64
        expected_cred = "username=admin:password=secret"
        url_encoded = quote(expected_cred, safe="@*_+-./")
        expected_encoded = base64.b64encode(url_encoded.encode("utf-8")).decode("utf-8")

        assert form_data["arguments"] == expected_encoded
        assert form_data["ar_nonce"] == "abc123"
        # Traditional fields should not be present
        assert "username_field" not in form_data
        assert "password_field" not in form_data


class TestAuthHandlerHNAP:
    """Test HNAP_SESSION strategy."""

    def test_hnap_auth_no_credentials(self):
        """Test HNAP strategy returns False without credentials."""
        handler = AuthHandler(strategy=AuthStrategyType.HNAP_SESSION)
        session = MagicMock()

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username=None,
            password=None,
        )

        # HNAP without credentials should fail
        assert success is False
        assert html is None

    def test_hnap_auth_with_credentials(self):
        """Test HNAP strategy authenticates using HNAPJsonRequestBuilder."""
        handler = AuthHandler(
            strategy=AuthStrategyType.HNAP_SESSION,
            hnap_config={
                "endpoint": "/HNAP1/",
                "namespace": "http://purenetworks.com/HNAP1/",
            },
        )

        # Mock the session to simulate HNAP login
        session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = (
            '{"LoginResponse": {"LoginResult": "OK", "Challenge": "abc", ' '"Cookie": "xyz", "PublicKey": "123"}}'
        )
        session.post.return_value = mock_response

        success, _ = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username="admin",
            password="password",
        )

        # With proper mock setup, HNAP should succeed
        assert session.post.called
        # Note: Full HNAP flow requires multiple requests, this tests the handler calls the builder


class TestAuthHandlerURLToken:
    """Test URL_TOKEN_SESSION strategy."""

    def test_url_token_auth_no_credentials(self):
        """Test URL token strategy skips auth without credentials."""
        handler = AuthHandler(strategy=AuthStrategyType.URL_TOKEN_SESSION)
        session = MagicMock()

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username=None,
            password=None,
        )

        # URL token without credentials should succeed (skip auth)
        assert success is True
        assert html is None

    def test_url_token_auth_with_credentials(self):
        """Test URL token strategy authenticates with credentials."""
        handler = AuthHandler(
            strategy=AuthStrategyType.URL_TOKEN_SESSION,
            url_token_config={
                "login_page": "/cmconnectionstatus.html",
                "login_prefix": "login_",
                "session_cookie_name": "credential",
                "data_page": "/cmconnectionstatus.html",
                "token_prefix": "ct_",
                "success_indicator": "Downstream",
            },
        )

        # Mock successful login response
        session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Downstream Channels</html>"
        session.get.return_value = mock_response

        success, html = handler.authenticate(
            session=session,
            base_url="https://192.168.100.1",
            username="admin",
            password="password",
        )

        # Should make GET request with token in URL
        assert session.get.called
        assert success is True


class TestAuthHandlerUnknown:
    """Test UNKNOWN strategy."""

    def test_unknown_returns_true_for_fallback(self):
        """Test unknown strategy returns True to allow fallback."""
        handler = AuthHandler(strategy=AuthStrategyType.UNKNOWN)
        session = MagicMock()

        success, html = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username="admin",
            password="password",
        )

        # Unknown should return True to allow parser fallback
        assert success is True
        assert html is None


class TestFallbackStrategies:
    """Test try-until-success fallback strategies (v3.12+)."""

    def test_init_with_fallback_strategies(self):
        """Test initialization with fallback strategies list."""
        fallback_strategies = [
            {"strategy": "form_plain", "form_config": {"action": "/login"}},
        ]
        handler = AuthHandler(
            strategy=AuthStrategyType.NO_AUTH,
            fallback_strategies=fallback_strategies,
        )
        assert handler.strategy == AuthStrategyType.NO_AUTH
        assert len(handler._fallback_strategies) == 1
        assert handler._fallback_strategies[0]["strategy"] == "form_plain"

    def test_fallback_tried_on_primary_failure(self):
        """Test that fallback strategy is tried when primary fails."""
        # Primary: NO_AUTH - will succeed without doing anything
        # But let's test form fallback when no_auth returns success but we want to verify
        # the fallback mechanism works
        form_config = {
            "action": "/login",
            "method": "POST",
            "username_field": "user",
            "password_field": "pass",
        }
        fallback_strategies = [
            {"strategy": "form_plain", "form_config": form_config},
        ]

        # Create handler with FORM_PLAIN primary that will fail
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={},  # Empty config will cause failure
            fallback_strategies=fallback_strategies,
        )

        session = MagicMock()

        # Mock response - first call (primary) fails, then fallback succeeds
        post_response = MagicMock()
        post_response.status_code = 200
        post_response.text = "<html>Success</html>"
        session.post.return_value = post_response

        # The primary will fail due to missing form_config
        # Fallback should succeed
        result = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username="admin",
            password="password",
        )

        assert result.success is True
        # After success, handler should be updated to fallback strategy
        assert handler.strategy == AuthStrategyType.FORM_PLAIN
        assert handler.form_config == form_config

    def test_fallback_updates_strategy_on_success(self):
        """Test that successful fallback updates the handler's strategy."""
        form_config = {
            "action": "/login",
            "method": "POST",
            "username_field": "user",
            "password_field": "pass",
        }
        fallback_strategies = [
            {"strategy": "form_plain", "form_config": form_config},
        ]

        # Start with NO_AUTH as "primary" but with form fallback
        # NO_AUTH always succeeds, so let's use BASIC_HTTP without creds to fail
        handler = AuthHandler(
            strategy=AuthStrategyType.BASIC_HTTP,  # Will fail without creds verification
            fallback_strategies=fallback_strategies,
        )

        session = MagicMock()

        # Mock basic auth failure (401)
        basic_response = MagicMock()
        basic_response.status_code = 401
        basic_response.text = "Unauthorized"

        # Mock form auth success
        form_response = MagicMock()
        form_response.status_code = 200
        form_response.text = "<html>Success</html>"

        # First get() for basic auth returns 401, then post() for form succeeds
        session.get.return_value = basic_response
        session.post.return_value = form_response

        result = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username="admin",
            password="password",
        )

        # Fallback should have been tried and succeeded
        assert result.success is True
        # Strategy should be updated to the successful fallback
        assert handler.strategy == AuthStrategyType.FORM_PLAIN

    def test_all_strategies_fail(self):
        """Test that failure is returned when all strategies fail."""
        fallback_strategies = [
            {"strategy": "form_plain", "form_config": {}},  # Will fail
        ]

        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={},  # Will fail
            fallback_strategies=fallback_strategies,
        )

        session = MagicMock()

        # Both primary and fallback will fail due to missing form_config
        result = handler.authenticate(
            session=session,
            base_url="http://192.168.100.1",
            username="admin",
            password="password",
        )

        # Should fail since all strategies failed
        assert result.success is False
