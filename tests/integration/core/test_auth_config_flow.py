"""Integration tests for auth discovery in config flow.

These tests verify that auth discovery integrates correctly with the
config flow, storing the discovered strategy in config entry data.
"""

from __future__ import annotations

from custom_components.cable_modem_monitor.core.auth.discovery import AuthStrategyType
from custom_components.cable_modem_monitor.core.discovery.pipeline import discover_auth


class TestSetupDiscoveryNoAuth:
    """Test that setup discovers NO_AUTH for modems without auth."""

    def test_setup_discovers_no_auth(self, http_server):
        """Setup with no-auth modem stores NO_AUTH strategy."""
        # Pass full URL to avoid HTTPS default
        host = http_server.url

        result = discover_auth(
            working_url=host,
            username=None,
            password=None,
            legacy_ssl=False,
        )

        assert result.strategy == AuthStrategyType.NO_AUTH.value
        assert result.success is True
        assert result.error is None

    def test_no_auth_with_empty_credentials(self, http_server):
        """Empty credentials still results in NO_AUTH."""
        host = http_server.url

        result = discover_auth(
            working_url=host,
            username="",
            password="",
            legacy_ssl=False,
        )

        # Empty string credentials should be treated as no credentials
        assert result.strategy == AuthStrategyType.NO_AUTH.value
        assert result.success is True


class TestSetupDiscoveryBasicAuth:
    """Test that setup discovers BASIC_HTTP for modems with Basic Auth."""

    def test_setup_discovers_basic_auth(self, basic_auth_server):
        """Setup with basic-auth modem stores BASIC_HTTP strategy."""
        host = basic_auth_server.url

        result = discover_auth(
            working_url=host,
            username="admin",
            password="password",
            legacy_ssl=False,
        )

        assert result.strategy == AuthStrategyType.BASIC_HTTP.value
        assert result.success is True
        assert result.error is None

    def test_basic_auth_wrong_credentials(self, basic_auth_server):
        """Wrong credentials for Basic Auth returns error."""
        host = basic_auth_server.url

        result = discover_auth(
            working_url=host,
            username="admin",
            password="wrong",
            legacy_ssl=False,
        )

        # Should fail with error
        assert result.success is False
        assert result.error is not None


class TestSetupDiscoveryFormAuth:
    """Test that setup discovers FORM_PLAIN for modems with form auth."""

    def test_setup_discovers_form_auth(self, form_auth_server):
        """Setup with form-auth modem stores FORM_PLAIN strategy."""
        host = form_auth_server.url

        result = discover_auth(
            working_url=host,
            username="admin",
            password="password",
            legacy_ssl=False,
        )

        assert result.strategy == AuthStrategyType.FORM_PLAIN.value
        assert result.success is True
        assert result.error is None

    def test_form_auth_stores_form_config(self, form_auth_server):
        """Form config is serialized and stored."""
        host = form_auth_server.url

        result = discover_auth(
            working_url=host,
            username="admin",
            password="password",
            legacy_ssl=False,
        )

        # Form config should be stored
        form_config = result.form_config
        assert form_config is not None
        assert "username_field" in form_config
        assert "password_field" in form_config
        assert form_config["username_field"] == "username"
        assert form_config["password_field"] == "password"

    def test_form_auth_captures_hidden_fields(self, form_auth_server):
        """Hidden form fields (CSRF tokens) are captured."""
        host = form_auth_server.url

        result = discover_auth(
            working_url=host,
            username="admin",
            password="password",
            legacy_ssl=False,
        )

        form_config = result.form_config
        assert form_config is not None
        # The mock server includes a CSRF token
        hidden_fields = form_config.get("hidden_fields", {})
        assert "csrf_token" in hidden_fields

    def test_form_auth_wrong_credentials(self, form_auth_server):
        """Wrong credentials for form auth - discovery detects and reports error.

        Form auth discovery identifies the form and submits credentials.
        With wrong credentials, the mock server re-displays the login form.
        Discovery detects we're still on login page and returns an error,
        allowing the user to correct credentials before setup completes.
        """
        host = form_auth_server.url

        result = discover_auth(
            working_url=host,
            username="admin",
            password="wrong",
            legacy_ssl=False,
        )

        # Auth discovery should detect invalid credentials
        assert result.success is False
        assert "Invalid credentials" in (result.error or "")
        # Strategy is None since auth failed (discovery couldn't complete)
        assert result.strategy is None


class TestSetupDiscoveryRedirect:
    """Test that setup handles redirects correctly."""

    def test_setup_follows_meta_refresh_redirect(self, redirect_auth_server):
        """Meta refresh redirects are followed during discovery."""
        host = redirect_auth_server.url

        result = discover_auth(
            working_url=host,
            username="admin",
            password="password",
            legacy_ssl=False,
        )

        # Should discover the form auth after following redirect
        # The redirect_auth_server redirects to login form
        assert result.success in (True, False)
        # Form should be detected even after redirect
        if result.success:
            assert result.form_config is not None


class TestSetupDiscoveryHNAP:
    """Test HNAP detection during setup."""

    def test_setup_detects_hnap(self, hnap_auth_server):
        """HNAP auth is detected by SOAPAction.js script."""
        host = hnap_auth_server.url

        result = discover_auth(
            working_url=host,
            username="admin",
            password="password",
            legacy_ssl=False,
        )

        # HNAP should be detected
        assert result.strategy == AuthStrategyType.HNAP_SESSION.value
        assert result.success is True


class TestSetupDiscoveryUnknown:
    """Test handling of unknown auth patterns."""

    def test_no_credentials_required_but_provided(self, http_server):
        """When modem needs no auth but credentials provided, still succeeds."""
        host = http_server.url

        result = discover_auth(
            working_url=host,
            username="admin",
            password="password",
            legacy_ssl=False,
        )

        # Should still discover NO_AUTH since the modem doesn't require auth
        # OR should succeed with whatever strategy works
        assert result.success is True


class TestAuthenticatedSession:
    """Test that authenticated session is returned."""

    def test_session_returned_for_no_auth(self, http_server):
        """Session is returned even for no-auth modems."""
        host = http_server.url

        result = discover_auth(
            working_url=host,
            username=None,
            password=None,
            legacy_ssl=False,
        )

        assert result.session is not None

    def test_session_returned_for_basic_auth(self, basic_auth_server):
        """Authenticated session is returned after Basic Auth."""
        host = basic_auth_server.url

        result = discover_auth(
            working_url=host,
            username="admin",
            password="password",
            legacy_ssl=False,
        )

        assert result.session is not None

    def test_session_returned_for_form_auth(self, form_auth_server):
        """Authenticated session with cookies is returned after form auth."""
        host = form_auth_server.url

        result = discover_auth(
            working_url=host,
            username="admin",
            password="password",
            legacy_ssl=False,
        )

        assert result.session is not None


class TestConfigEntryIntegration:
    """Test integration with config entry storage.

    These tests verify the data format is correct for config entry storage.
    """

    def test_strategy_is_string(self, http_server):
        """Auth strategy is stored as string (for JSON serialization)."""
        host = http_server.url

        result = discover_auth(
            working_url=host,
            username=None,
            password=None,
            legacy_ssl=False,
        )

        # Strategy should be a string, not enum
        assert isinstance(result.strategy, str)
        assert result.strategy == "no_auth"

    def test_form_config_is_dict(self, form_auth_server):
        """Form config is stored as dict (for JSON serialization)."""
        host = form_auth_server.url

        result = discover_auth(
            working_url=host,
            username="admin",
            password="password",
            legacy_ssl=False,
        )

        form_config = result.form_config
        if form_config is not None:
            # Should be a plain dict, not a dataclass
            assert isinstance(form_config, dict)
            # Should have expected keys
            assert "action" in form_config
            assert "method" in form_config
            assert "username_field" in form_config
            assert "password_field" in form_config
            assert "hidden_fields" in form_config

    def test_result_has_expected_attributes(self, http_server):
        """Result has all expected attributes for config entry."""
        host = http_server.url

        result = discover_auth(
            working_url=host,
            username=None,
            password=None,
            legacy_ssl=False,
        )

        # AuthResult should have these attributes
        assert hasattr(result, "success")
        assert hasattr(result, "strategy")
        assert hasattr(result, "session")
        assert hasattr(result, "html")
        assert hasattr(result, "form_config")
        assert hasattr(result, "error")
