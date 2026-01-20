"""Integration tests for Auth Discovery with real mock servers.

These tests verify that AuthDiscovery works correctly with actual HTTP servers,
as opposed to the unit tests that use mocked requests.Session.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from custom_components.cable_modem_monitor.core.auth import AuthStrategyType
from custom_components.cable_modem_monitor.core.auth.discovery import AuthDiscovery


@pytest.fixture
def mock_parser():
    """Create a mock parser that can parse the mock modem response."""
    parser = MagicMock()
    parser.name = "Test Parser"
    parser.auth_form_hints = {}
    parser.js_auth_hints = None

    # This parser can parse the MOCK_MODEM_RESPONSE from conftest.py
    def parse_data(soup, session=None, base_url=None):
        # Check if it has the downstream table
        if soup.find("table", {"id": "downstream"}) or soup.find(string=lambda s: "Channel 1" in (s or "")):
            return {"downstream": [{"channel": 1}], "upstream": []}
        return {"downstream": [], "upstream": []}

    parser.parse.side_effect = parse_data
    return parser


@pytest.fixture
def discovery():
    """Create an AuthDiscovery instance."""
    return AuthDiscovery()


class TestBasicAuthIntegration:
    """Test Basic HTTP Auth discovery with real server."""

    def test_basic_auth_without_credentials_returns_401_error(self, discovery, basic_auth_server, mock_parser):
        """Test that 401 without credentials returns appropriate error."""
        session = requests.Session()
        session.verify = False

        result = discovery.discover(
            session=session,
            base_url=basic_auth_server.url,
            data_url=f"{basic_auth_server.url}/status.html",
            username=None,
            password=None,
            parser=mock_parser,
        )

        assert result.success is False
        assert "Authentication required" in result.error_message

    def test_basic_auth_with_valid_credentials(self, discovery, basic_auth_server, mock_parser):
        """Test that valid credentials work with Basic Auth."""
        session = requests.Session()
        session.verify = False

        result = discovery.discover(
            session=session,
            base_url=basic_auth_server.url,
            data_url=f"{basic_auth_server.url}/status.html",
            username="admin",
            password="password",
            parser=mock_parser,
        )

        assert result.success is True
        assert result.strategy == AuthStrategyType.BASIC_HTTP
        assert result.response_html is not None
        assert "Channel 1" in result.response_html

    def test_basic_auth_with_invalid_credentials(self, discovery, basic_auth_server, mock_parser):
        """Test that invalid credentials return error."""
        session = requests.Session()
        session.verify = False

        result = discovery.discover(
            session=session,
            base_url=basic_auth_server.url,
            data_url=f"{basic_auth_server.url}/status.html",
            username="admin",
            password="wrongpassword",
            parser=mock_parser,
        )

        assert result.success is False
        assert "Invalid credentials" in result.error_message


class TestFormAuthIntegration:
    """Test form-based auth discovery with real server."""

    def test_form_auth_detected(self, discovery, form_auth_server, mock_parser):
        """Test that login form is detected."""
        session = requests.Session()
        session.verify = False

        result = discovery.discover(
            session=session,
            base_url=form_auth_server.url,
            data_url=f"{form_auth_server.url}/status.html",
            username=None,
            password=None,
            parser=mock_parser,
        )

        # Without credentials, should detect the form and request creds
        assert result.success is False
        assert "Login form detected" in result.error_message

    def test_form_auth_with_valid_credentials(self, discovery, form_auth_server, mock_parser):
        """Test that valid credentials work with form auth."""
        session = requests.Session()
        session.verify = False

        result = discovery.discover(
            session=session,
            base_url=form_auth_server.url,
            data_url=f"{form_auth_server.url}/status.html",
            username="admin",
            password="password",
            parser=mock_parser,
        )

        assert result.success is True
        assert result.strategy == AuthStrategyType.FORM_PLAIN
        assert result.form_config is not None
        assert result.form_config.username_field == "username"
        assert result.form_config.password_field == "password"
        assert "csrf_token" in result.form_config.hidden_fields
        assert result.response_html is not None
        assert "Channel 1" in result.response_html


class TestHNAPAuthIntegration:
    """Test HNAP detection with real server."""

    def test_hnap_detected_by_script(self, discovery, hnap_auth_server, mock_parser):
        """Test that HNAP is detected via SOAPAction.js script."""
        session = requests.Session()
        session.verify = False

        result = discovery.discover(
            session=session,
            base_url=hnap_auth_server.url,
            data_url=f"{hnap_auth_server.url}/Login.html",
            username="admin",
            password="password",
            parser=mock_parser,
        )

        # HNAP should be detected and returned (actual auth handled by strategy)
        assert result.success is True
        assert result.strategy == AuthStrategyType.HNAP_SESSION


class TestRedirectAuthIntegration:
    """Test redirect handling with real server."""

    def test_meta_refresh_redirect_followed(self, discovery, redirect_auth_server, mock_parser):
        """Test that meta refresh redirect is followed to login form."""
        session = requests.Session()
        session.verify = False

        result = discovery.discover(
            session=session,
            base_url=redirect_auth_server.url,
            data_url=f"{redirect_auth_server.url}/status",
            username=None,
            password=None,
            parser=mock_parser,
        )

        # Should follow redirect and find login form
        assert result.success is False
        assert "Login form detected" in result.error_message

    def test_redirect_then_form_auth(self, discovery, redirect_auth_server, mock_parser):
        """Test that redirect followed by form auth works."""
        session = requests.Session()
        session.verify = False

        result = discovery.discover(
            session=session,
            base_url=redirect_auth_server.url,
            data_url=f"{redirect_auth_server.url}/status",
            username="admin",
            password="password",
            parser=mock_parser,
        )

        # Should follow redirect, authenticate via form, and succeed
        assert result.success is True
        assert result.strategy == AuthStrategyType.FORM_PLAIN
        assert result.form_config is not None


class TestNoAuthIntegration:
    """Test no-auth detection with real server."""

    def test_no_auth_direct_access(self, discovery, http_server, mock_parser):
        """Test that no-auth modem is detected correctly."""
        session = requests.Session()
        session.verify = False

        result = discovery.discover(
            session=session,
            base_url=http_server.url,
            data_url=f"{http_server.url}/status.html",
            username=None,
            password=None,
            parser=mock_parser,
        )

        assert result.success is True
        assert result.strategy == AuthStrategyType.NO_AUTH
        assert result.response_html is not None
        assert "Channel 1" in result.response_html


class TestFormConfigSerialization:
    """Test that form configs survive serialization (for config entry storage)."""

    def test_form_config_roundtrip(self, discovery, form_auth_server, mock_parser):
        """Test form config serialization and deserialization."""
        session = requests.Session()
        session.verify = False

        result = discovery.discover(
            session=session,
            base_url=form_auth_server.url,
            data_url=f"{form_auth_server.url}/status.html",
            username="admin",
            password="password",
            parser=mock_parser,
        )

        assert result.success is True
        assert result.form_config is not None

        # Serialize
        serialized = result.form_config.to_dict()
        assert isinstance(serialized, dict)
        assert "action" in serialized
        assert "username_field" in serialized
        assert "password_field" in serialized

        # Deserialize
        from custom_components.cable_modem_monitor.core.auth.discovery import (
            DiscoveredFormConfig,
        )

        restored = DiscoveredFormConfig.from_dict(serialized)
        assert restored.action == result.form_config.action
        assert restored.username_field == result.form_config.username_field
        assert restored.password_field == result.form_config.password_field
        assert restored.hidden_fields == result.form_config.hidden_fields


class TestSessionPersistence:
    """Test that authenticated sessions work correctly."""

    def test_session_cookies_persist_after_form_auth(self, discovery, form_auth_server, mock_parser):
        """Test that session cookies are maintained after auth."""
        session = requests.Session()
        session.verify = False

        # Discover auth
        result = discovery.discover(
            session=session,
            base_url=form_auth_server.url,
            data_url=f"{form_auth_server.url}/status.html",
            username="admin",
            password="password",
            parser=mock_parser,
        )

        assert result.success is True

        # Session should now have cookies that allow access
        # Make a follow-up request
        response = session.get(f"{form_auth_server.url}/status.html")
        assert response.status_code == 200
        assert "Channel 1" in response.text


class TestConnectionErrors:
    """Test handling of connection errors."""

    def test_connection_refused(self, discovery, mock_parser):
        """Test that connection errors are handled gracefully."""
        session = requests.Session()
        session.verify = False

        result = discovery.discover(
            session=session,
            base_url="http://127.0.0.1:1",  # Invalid port
            data_url="http://127.0.0.1:1/status.html",
            username=None,
            password=None,
            parser=mock_parser,
        )

        assert result.success is False
        assert "Connection failed" in result.error_message


class TestVerificationUrlIntegration:
    """Test verification_url handling with modems that show login at base URL.

    Regression tests for bug where auth discovery checked base URL after login,
    but some modems (MB7621) show login form at base URL even after auth.

    The fix requires:
    1. modem.yaml has auth.form.success.redirect
    2. AuthDiscovery uses verification_url parameter
    3. Config flow passes verification_url from modem.yaml hints

    These tests use mb7621_modem_server (MockModemServer) which reads from
    modem.yaml - demonstrating the modem.yaml-driven testing pattern.
    """

    @pytest.fixture
    def mb7621_parser(self, mb7621_modem_server):
        """Create mock parser with MB7621's form hints from modem.yaml."""
        from unittest.mock import MagicMock

        from custom_components.cable_modem_monitor.modem_config import load_modem_config
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            ModemConfigAuthAdapter,
        )

        config = load_modem_config(mb7621_modem_server.modem_path)
        adapter = ModemConfigAuthAdapter(config)

        parser = MagicMock()
        parser.name = f"{config.manufacturer} {config.model}"
        parser.auth_form_hints = adapter.get_auth_form_hints()
        parser.js_auth_hints = None

        def parse_data(soup, session=None, base_url=None):
            text = soup.get_text()
            if "Downstream" in text or "Upstream" in text:
                return {"downstream": [{"channel": 1}], "upstream": []}
            return {"downstream": [], "upstream": []}

        parser.parse.side_effect = parse_data
        return parser

    def test_form_auth_succeeds_without_success_redirect_hint(self, discovery, mb7621_modem_server):
        """Test that auth discovery SUCCEEDS even without success_redirect hint.

        Previously, this was a bug scenario where MB7621-style modems would fail
        because discovery checked the base URL after form submission, which showed
        a login form even after successful auth.

        The fix checks the form submission response first - if it's not a login
        form (after following the redirect), auth succeeds immediately without
        needing to check a verification URL.
        """
        from unittest.mock import MagicMock

        # Create parser WITHOUT success_redirect hint
        parser_without_hint = MagicMock()
        parser_without_hint.name = "MB7621 (no hint)"
        parser_without_hint.auth_form_hints = {
            "login_url": "/goform/login",
            "username_field": "loginUsername",
            "password_field": "loginPassword",
            "password_encoding": "base64",
            # NO success_redirect - but auth should still work!
        }
        parser_without_hint.js_auth_hints = None

        session = requests.Session()
        session.verify = False

        result = discovery.discover(
            session=session,
            base_url=mb7621_modem_server.url,
            data_url=f"{mb7621_modem_server.url}/",
            username="admin",
            password="password",
            parser=parser_without_hint,
        )

        # Auth succeeds because:
        # 1. Form submission returns 302 redirect to /MotoHome.asp
        # 2. requests follows redirect, response contains the home page
        # 3. Home page is not a login form → auth succeeded
        assert result.success is True
        assert result.strategy == AuthStrategyType.FORM_PLAIN

    def test_auth_succeeds_with_verification_url(self, discovery, mb7621_modem_server, mb7621_parser):
        """Test that auth discovery SUCCEEDS when verification_url is provided.

        This tests the fix: pass verification_url (from modem.yaml success_redirect)
        so auth discovery checks that page instead of base URL.
        """
        from custom_components.cable_modem_monitor.modem_config import load_modem_config

        config = load_modem_config(mb7621_modem_server.modem_path)
        assert config.auth.form is not None, "MB7621 must have form auth"
        assert config.auth.form.success is not None, "MB7621 must have success config"
        verification_url = config.auth.form.success.redirect  # From modem.yaml

        session = requests.Session()
        session.verify = False

        result = discovery.discover(
            session=session,
            base_url=mb7621_modem_server.url,
            data_url=f"{mb7621_modem_server.url}/",  # Base URL still
            username="admin",
            password="password",
            parser=mb7621_parser,
            verification_url=verification_url,
        )

        assert result.success is True
        # MB7621 uses base64 encoding (controlled by password_encoding field)
        assert result.strategy == AuthStrategyType.FORM_PLAIN
        assert result.response_html is not None

    def test_authenticated_session_can_access_protected_page(self, discovery, mb7621_modem_server, mb7621_parser):
        """Verify session cookies persist and allow access to protected pages."""
        from custom_components.cable_modem_monitor.modem_config import load_modem_config

        config = load_modem_config(mb7621_modem_server.modem_path)
        assert config.auth.form is not None, "MB7621 must have form auth"
        assert config.auth.form.success is not None, "MB7621 must have success config"
        verification_url = config.auth.form.success.redirect

        session = requests.Session()
        session.verify = False

        result = discovery.discover(
            session=session,
            base_url=mb7621_modem_server.url,
            data_url=f"{mb7621_modem_server.url}/",
            username="admin",
            password="password",
            parser=mb7621_parser,
            verification_url=verification_url,
        )

        assert result.success is True

        # Session should have cookies - verify we can access protected page
        response = session.get(f"{mb7621_modem_server.url}/MotoHome.asp")
        assert response.status_code == 200

        # Base URL should STILL show login (this is the modem's real behavior)
        response = session.get(f"{mb7621_modem_server.url}/")
        assert 'type="password"' in response.text.lower()


class TestModemYamlDrivenAuthDiscovery:
    """Auth discovery tests using MockModemServer with modem.yaml configuration.

    These tests demonstrate the modem.yaml-driven testing pattern:
    1. Load modem configuration from modem.yaml
    2. Use MockModemServer which serves fixtures
    3. Test auth discovery using config values (not hardcoded)

    This is the preferred pattern for new tests.
    """

    def test_mb7621_auth_discovery_from_config(self, discovery, mb7621_modem_server):
        """Test MB7621 auth discovery using modem.yaml configuration.

        This test reads verification_url and form hints from modem.yaml,
        demonstrating fully config-driven testing.
        """
        from unittest.mock import MagicMock

        from custom_components.cable_modem_monitor.modem_config import load_modem_config
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            ModemConfigAuthAdapter,
        )

        # Load config from the same path MockModemServer uses
        config = load_modem_config(mb7621_modem_server.modem_path)
        adapter = ModemConfigAuthAdapter(config)

        # Get verification URL and form hints from config
        verification_url = None
        if config.auth.form and config.auth.form.success:
            verification_url = config.auth.form.success.redirect

        # Create mock parser with form hints from modem.yaml
        mock_parser = MagicMock()
        mock_parser.name = f"{config.manufacturer} {config.model}"
        mock_parser.auth_form_hints = adapter.get_auth_form_hints()
        mock_parser.js_auth_hints = None

        # Parser should be able to parse the data page
        def parse_data(soup, session=None, base_url=None):
            # Check for MB7621 data indicators
            text = soup.get_text()
            if "Downstream" in text or "Upstream" in text:
                return {"downstream": [{"channel": 1}], "upstream": []}
            return {"downstream": [], "upstream": []}

        mock_parser.parse.side_effect = parse_data

        session = requests.Session()
        session.verify = False

        result = discovery.discover(
            session=session,
            base_url=mb7621_modem_server.url,
            data_url=f"{mb7621_modem_server.url}/",
            username="admin",
            password="password",
            parser=mock_parser,
            verification_url=verification_url,
        )

        # Should succeed with verification_url from modem.yaml
        assert result.success is True
        # MB7621 uses FORM_PLAIN with password_encoding=base64
        assert result.strategy == AuthStrategyType.FORM_PLAIN

    def test_mb7621_base_url_shows_login_after_auth(self, mb7621_modem_server):
        """Verify MB7621's quirk: base URL shows login even after auth.

        This is a regression test for the MB7621 behavior that caused
        auth discovery failures.
        """
        session = requests.Session()

        # Access base URL - should show login form
        response = session.get(f"{mb7621_modem_server.url}/")
        assert response.status_code == 200
        assert 'type="password"' in response.text.lower()

        # Login via form
        from custom_components.cable_modem_monitor.modem_config import load_modem_config

        config = load_modem_config(mb7621_modem_server.modem_path)
        form_config = config.auth.form
        assert form_config is not None, "MB7621 must have form auth"
        assert form_config.success is not None, "MB7621 must have success config"

        # Encode password for MB7621 (base64)
        import base64
        from urllib.parse import quote

        password = "password"
        encoded_password = base64.b64encode(quote(password).encode()).decode()

        login_data = {
            form_config.username_field: "admin",
            form_config.password_field: encoded_password,
        }

        response = session.post(
            f"{mb7621_modem_server.url}{form_config.action}",
            data=login_data,
            allow_redirects=False,
        )

        # Should redirect to success page
        assert response.status_code == 302
        assert response.headers.get("Location") == form_config.success.redirect

        # Follow redirect - should get data
        response = session.get(f"{mb7621_modem_server.url}{form_config.success.redirect}")
        assert response.status_code == 200

        # KEY BEHAVIOR: Base URL should STILL show login
        response = session.get(f"{mb7621_modem_server.url}/")
        assert 'type="password"' in response.text.lower()
