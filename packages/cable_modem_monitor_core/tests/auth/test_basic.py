"""Tests for BasicAuthManager."""

from __future__ import annotations

import requests
from solentlabs.cable_modem_monitor_core.auth.basic import BasicAuthManager
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import BasicAuth
from solentlabs.cable_modem_monitor_core.testing import HARMockServer

from .conftest import load_auth_fixture


class TestBasicAuthManager:
    """BasicAuthManager sets credentials on the session."""

    def test_sets_session_auth(self, session: requests.Session) -> None:
        """Session.auth is set to (username, password)."""
        config = BasicAuth(strategy="basic")
        manager = BasicAuthManager(config)

        result = manager.authenticate(session, "http://192.168.100.1", "admin", "secret")
        assert result.success is True
        assert session.auth == ("admin", "secret")

    def test_no_challenge_cookie_no_request(self, session: requests.Session) -> None:
        """Without challenge_cookie, no HTTP request is made."""
        config = BasicAuth(strategy="basic", challenge_cookie=False)
        manager = BasicAuthManager(config)

        result = manager.authenticate(session, "http://192.168.100.1", "admin", "secret")
        assert result.success is True
        # No response since no HTTP request was made
        assert result.response is None

    def test_challenge_cookie_fetches_page(self, session: requests.Session) -> None:
        """With challenge_cookie, an initial request is made."""
        entries, modem_config = load_auth_fixture("har_basic_auth.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = BasicAuth(strategy="basic", challenge_cookie=True)
            manager = BasicAuthManager(config)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "secret")
            assert result.success is True

    def test_no_url_token(self, session: requests.Session) -> None:
        """Basic auth doesn't produce a URL token."""
        config = BasicAuth(strategy="basic")
        manager = BasicAuthManager(config)

        result = manager.authenticate(session, "http://192.168.100.1", "admin", "secret")
        assert result.url_token == ""
