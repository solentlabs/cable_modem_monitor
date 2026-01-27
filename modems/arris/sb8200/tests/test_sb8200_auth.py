"""Integration tests for SB8200 authentication using mock server.

These tests verify the AuthHandler works correctly with both firmware variants:
- Tim's variant: HTTP, no auth required (older firmware)
- Travis's variant: HTTPS, URL-based auth (firmware 1.01.009.47+)

As of v3.12.0, authentication is handled by AuthHandler, not parser.login().
"""

import requests

from custom_components.cable_modem_monitor.core.auth import AuthHandler, AuthStrategyType
from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher
from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser
from custom_components.cable_modem_monitor.modems.arris.sb8200.parser import ArrisSB8200Parser

# Test timeout constant - matches DEFAULT_TIMEOUT from schema
TEST_TIMEOUT = 10


def _get_sb8200_js_auth_hints() -> dict:
    """Get JS auth hints for SB8200 from modem.yaml."""
    adapter = get_auth_adapter_for_parser("ArrisSB8200Parser")
    if adapter:
        hints = adapter.get_js_auth_hints()
        if hints:
            return hints
    raise ValueError("SB8200 js_auth_hints not found in modem.yaml")


class TestSB8200AuthNoAuthServer:
    """Test SB8200 authentication with no-auth server (Tim's variant)."""

    def test_no_auth_strategy_succeeds(self, sb8200_modem_server_noauth):
        """Test NO_AUTH strategy succeeds on no-auth server."""
        handler = AuthHandler(strategy=AuthStrategyType.NO_AUTH, timeout=TEST_TIMEOUT)
        session = requests.Session()

        success, html = handler.authenticate(session, sb8200_modem_server_noauth.url, None, None)

        assert success is True
        assert html is None  # NO_AUTH returns no HTML

    def test_url_token_without_credentials_succeeds(self, sb8200_modem_server_noauth):
        """Test URL token strategy succeeds without credentials."""
        handler = AuthHandler(
            strategy=AuthStrategyType.URL_TOKEN_SESSION,
            url_token_config=_get_sb8200_js_auth_hints(),
            timeout=TEST_TIMEOUT,
        )
        session = requests.Session()

        success, html = handler.authenticate(session, sb8200_modem_server_noauth.url, None, None)

        assert success is True  # Skips auth without credentials


class TestSB8200AuthServer:
    """Test SB8200 authentication with auth server (Travis's variant)."""

    def test_url_token_with_valid_credentials_succeeds(self, sb8200_modem_server_auth):
        """Test URL token auth succeeds with valid credentials."""
        handler = AuthHandler(
            strategy=AuthStrategyType.URL_TOKEN_SESSION,
            url_token_config=_get_sb8200_js_auth_hints(),
            timeout=TEST_TIMEOUT,
        )
        session = requests.Session()

        success, html = handler.authenticate(session, sb8200_modem_server_auth.url, "admin", "password")

        assert success is True
        # Should return HTML containing success indicator
        if html:
            assert isinstance(html, str)

    def test_url_token_without_credentials_skips_auth(self, sb8200_modem_server_auth):
        """Test URL token auth skips when no credentials provided.

        AuthHandler returns success without credentials to allow detection phase.
        """
        handler = AuthHandler(
            strategy=AuthStrategyType.URL_TOKEN_SESSION,
            url_token_config=_get_sb8200_js_auth_hints(),
            timeout=TEST_TIMEOUT,
        )
        session = requests.Session()

        success, html = handler.authenticate(session, sb8200_modem_server_auth.url, None, None)

        # Should succeed (skip auth) for detection to work
        assert success is True


class TestSB8200AuthHTTPS:
    """Test SB8200 auth with HTTPS + auth (full Travis scenario)."""

    def test_url_token_over_https_with_valid_credentials(self, sb8200_modem_server_auth_https):
        """Test authentication works over HTTPS with self-signed cert."""
        handler = AuthHandler(
            strategy=AuthStrategyType.URL_TOKEN_SESSION,
            url_token_config=_get_sb8200_js_auth_hints(),
            timeout=TEST_TIMEOUT,
        )
        session = requests.Session()
        session.verify = False  # Allow self-signed cert

        success, html = handler.authenticate(session, sb8200_modem_server_auth_https.url, "admin", "password")

        assert success is True
        # Should return HTML containing success indicator
        if html:
            assert isinstance(html, str)


class TestSB8200ParserIntegration:
    """Test SB8200 parser integration with authenticated session."""

    def test_parser_can_detect_sb8200(self, sb8200_modem_server_noauth):
        """Test parser can detect SB8200 from server response via HintMatcher."""
        session = requests.Session()
        response = session.get(f"{sb8200_modem_server_noauth.url}/cmconnectionstatus.html")

        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(response.text)
        assert any(m.parser_name == "ArrisSB8200Parser" for m in matches)

    def test_parser_parses_channel_data(self, sb8200_modem_server_noauth):
        """Test parser can parse channel data from server."""
        from bs4 import BeautifulSoup

        session = requests.Session()
        response = session.get(f"{sb8200_modem_server_noauth.url}/cmconnectionstatus.html")

        soup = BeautifulSoup(response.text, "html.parser")
        parser = ArrisSB8200Parser()
        data = parser.parse(soup, session=session, base_url=sb8200_modem_server_noauth.url)

        assert "downstream" in data
        assert "upstream" in data
        assert "system_info" in data
