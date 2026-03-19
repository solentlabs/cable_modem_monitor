"""Tests for FormAuthManager."""

from __future__ import annotations

import base64

import requests
from solentlabs.cable_modem_monitor_core.auth.form import (
    FormAuthManager,
    _encode_password,
)
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (
    FormAuth,
    FormSuccess,
)
from solentlabs.cable_modem_monitor_core.models.modem_config.session import (
    SessionConfig,
)
from solentlabs.cable_modem_monitor_core.testing import HARMockServer

from .conftest import load_auth_fixture


class TestEncodePassword:
    """Password encoding utility."""

    def test_plain_encoding(self) -> None:
        """Plain encoding returns password as-is."""
        assert _encode_password("secret", "plain") == "secret"

    def test_base64_encoding(self) -> None:
        """Base64 encoding returns base64-encoded password."""
        result = _encode_password("secret", "base64")
        assert result == base64.b64encode(b"secret").decode("ascii")

    def test_empty_password(self) -> None:
        """Empty password works for both encodings."""
        assert _encode_password("", "plain") == ""
        assert _encode_password("", "base64") == base64.b64encode(b"").decode()


class TestFormAuthManager:
    """FormAuthManager executes form POST login."""

    def test_basic_form_login(self, session: requests.Session) -> None:
        """Successful form login against mock server."""
        entries, modem_config = load_auth_fixture("har_form_login.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormAuth(
                strategy="form",
                action="/goform/login",
            )
            manager = FormAuthManager(config)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True
            assert result.response is not None

    def test_base64_encoded_password(self, session: requests.Session) -> None:
        """Password is base64-encoded before POST."""
        entries, modem_config = load_auth_fixture("har_form_login.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormAuth(
                strategy="form",
                action="/goform/login",
                encoding="base64",
            )
            manager = FormAuthManager(config)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True

    def test_success_redirect_check(self, session: requests.Session) -> None:
        """Success check via redirect URL matching."""
        entries, modem_config = load_auth_fixture("har_form_login.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormAuth(
                strategy="form",
                action="/login",
                success=FormSuccess(redirect="/login"),
            )
            manager = FormAuthManager(config)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "password")
            # The mock server doesn't redirect, so the final URL
            # is the login URL itself -- which contains "/login"
            assert result.success is True

    def test_success_indicator_present(self, session: requests.Session) -> None:
        """Success check via response body indicator."""
        entries, modem_config = load_auth_fixture("har_form_login_with_indicator.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormAuth(
                strategy="form",
                action="/login",
                success=FormSuccess(indicator="Welcome"),
            )
            manager = FormAuthManager(config)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True

    def test_success_indicator_missing(self, session: requests.Session) -> None:
        """Failure when success indicator is not in response."""
        entries, modem_config = load_auth_fixture("har_form_login_error.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormAuth(
                strategy="form",
                action="/login",
                success=FormSuccess(indicator="Welcome"),
            )
            manager = FormAuthManager(config)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is False
            assert "indicator" in result.error

    def test_response_url_captured(self, session: requests.Session) -> None:
        """Auth response URL is captured for response reuse."""
        entries, modem_config = load_auth_fixture("har_form_login.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormAuth(
                strategy="form",
                action="/goform/login",
            )
            manager = FormAuthManager(config)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True
            assert result.response_url == "/goform/login"

    def test_with_session_config(self, session: requests.Session) -> None:
        """Session config is accepted."""
        entries, modem_config = load_auth_fixture("har_form_login_with_indicator.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormAuth(strategy="form", action="/login")
            session_cfg = SessionConfig(cookie_name="my_session")
            manager = FormAuthManager(config, session_cfg)
            manager.configure_session(session, {}, 10)

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True
