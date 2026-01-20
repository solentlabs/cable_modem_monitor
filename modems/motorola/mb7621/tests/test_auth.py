"""Integration tests for MB7621 authentication.

These tests verify the MB7621's specific auth behavior:
- Base URL shows login form even after successful authentication
- Verification URL is required for successful auth discovery
- Form-based auth with base64 password encoding

This is a regression test for a bug where auth discovery would check the base URL
after login and incorrectly think auth failed because the login form was still showing.
"""

from __future__ import annotations

import base64
from unittest.mock import MagicMock
from urllib.parse import quote

import pytest
import requests

from custom_components.cable_modem_monitor.core.auth import AuthStrategyType
from custom_components.cable_modem_monitor.core.auth.discovery import AuthDiscovery
from custom_components.cable_modem_monitor.modem_config import load_modem_config
from custom_components.cable_modem_monitor.modem_config.adapter import ModemConfigAuthAdapter


@pytest.fixture
def discovery():
    """Create an AuthDiscovery instance."""
    return AuthDiscovery()


@pytest.fixture
def mb7621_parser(mb7621_modem_server):
    """Create mock parser with MB7621's form hints from modem.yaml."""
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


class TestMB7621VerificationUrl:
    """Test verification_url handling for MB7621.

    Regression tests for bug where auth discovery checked base URL after login,
    but MB7621 shows login form at base URL even after auth.

    The fix requires:
    1. modem.yaml has auth.form.success.redirect
    2. AuthDiscovery uses verification_url parameter
    3. Config flow passes verification_url from modem.yaml hints
    """

    def test_form_auth_succeeds_without_success_redirect_hint(self, discovery, mb7621_modem_server):
        """Test that auth discovery SUCCEEDS even without success_redirect hint.

        Previously, this was a bug scenario where MB7621-style modems would fail
        because discovery checked the base URL after form submission, which showed
        a login form even after successful auth.

        The fix checks the form submission response first - if it's not a login
        form (after following the redirect), auth succeeds immediately without
        needing to check a verification URL.
        """
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
        # MB7621 uses FORM_PLAIN with password_encoding=base64
        assert result.strategy == AuthStrategyType.FORM_PLAIN
        assert result.response_html is not None

    def test_authenticated_session_can_access_protected_page(self, discovery, mb7621_modem_server, mb7621_parser):
        """Verify session cookies persist and allow access to protected pages."""
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


class TestMB7621AuthDiscovery:
    """Auth discovery tests using MockModemServer with MB7621 modem.yaml.

    These tests demonstrate the modem.yaml-driven testing pattern:
    1. Load modem configuration from modem.yaml
    2. Use MockModemServer which serves fixtures
    3. Test auth discovery using config values (not hardcoded)
    """

    def test_auth_discovery_from_config(self, discovery, mb7621_modem_server):
        """Test MB7621 auth discovery using modem.yaml configuration.

        This test reads verification_url and form hints from modem.yaml,
        demonstrating fully config-driven testing.
        """
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

    def test_base_url_shows_login_after_auth(self, mb7621_modem_server):
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
        config = load_modem_config(mb7621_modem_server.modem_path)
        form_config = config.auth.form
        assert form_config is not None, "MB7621 must have form auth"
        assert form_config.success is not None, "MB7621 must have success config"

        # Encode password for MB7621 (base64)
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
