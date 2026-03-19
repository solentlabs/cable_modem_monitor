"""Tests for UrlTokenAuthManager."""

from __future__ import annotations

import requests
from solentlabs.cable_modem_monitor_core.auth.url_token import UrlTokenAuthManager
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import UrlTokenAuth
from solentlabs.cable_modem_monitor_core.models.modem_config.session import (
    SessionConfig,
)
from solentlabs.cable_modem_monitor_core.testing import HARMockServer

from .conftest import load_auth_fixture


class TestUrlTokenAuthManager:
    """UrlTokenAuthManager encodes credentials in URL."""

    def test_basic_login(self, session: requests.Session) -> None:
        """Successful login sets session cookie."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                success_indicator="Downstream Bonded Channels",
            )
            session_config = SessionConfig(
                cookie_name="sessionId",
                token_prefix="ct_",
            )
            manager = UrlTokenAuthManager(config, session_config)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True

    def test_url_token_extracted_from_cookie(self, session: requests.Session) -> None:
        """URL token is extracted from session cookie."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
            )
            session_config = SessionConfig(
                cookie_name="sessionId",
                token_prefix="ct_",
            )
            manager = UrlTokenAuthManager(config, session_config)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True
            assert result.url_token == "tok_abc123"

    def test_login_prefix_in_url(self, session: requests.Session) -> None:
        """Login prefix is prepended to base64 credential."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                login_prefix="login_",
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True

    def test_success_indicator_missing_fails(self, session: requests.Session) -> None:
        """Failure when success indicator is not in response."""
        entries, _ = load_auth_fixture("har_url_token_login_error.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                success_indicator="Downstream Bonded Channels",
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is False
            assert "indicator" in result.error

    def test_ajax_login_header(self, session: requests.Session) -> None:
        """AJAX login adds X-Requested-With header."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                ajax_login=True,
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True

    def test_auth_header_data_sets_basic_auth(self, session: requests.Session) -> None:
        """auth_header_data sets Basic auth on the session."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                auth_header_data=True,
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True
            assert session.auth == ("admin", "password")

    def test_response_url_captured(self, session: requests.Session) -> None:
        """Response URL path is captured for auth response reuse."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True
            assert result.response_url == "/login.html"

    def test_no_cookie_name_empty_token(self, session: requests.Session) -> None:
        """Without cookie_name, url_token is empty."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
            )
            # No session config -- no cookie_name
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True
            assert result.url_token == ""
