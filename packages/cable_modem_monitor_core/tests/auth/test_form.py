"""Tests for FormAuthManager."""

from __future__ import annotations

import base64
from unittest.mock import patch

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.form import (
    FormAuthManager,
    _encode_password,
)
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (
    FormAuth,
    FormSuccess,
)
from solentlabs.cable_modem_monitor_core.test_harness import HARMockServer

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
            manager.configure_session(session, {})

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
            manager.configure_session(session, {})

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
            manager.configure_session(session, {})

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
            manager.configure_session(session, {})

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
            manager.configure_session(session, {})

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
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True
            assert result.response_url == "/goform/login"

    def test_login_with_indicator(self, session: requests.Session) -> None:
        """Login with success indicator in response body."""
        entries, modem_config = load_auth_fixture("har_form_login_with_indicator.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormAuth(strategy="form", action="/login")
            manager = FormAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True

    def test_401_no_success_criteria(self, session: requests.Session) -> None:
        """401 response with no success criteria returns auth failure."""
        entries, modem_config = load_auth_fixture("har_form_login_401.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormAuth(strategy="form", action="/goform/login")
            manager = FormAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is False
            assert "401" in result.error

    def test_redirect_mismatch(self, session: requests.Session) -> None:
        """Redirect mismatch returns auth failure with path details."""
        entries, modem_config = load_auth_fixture("har_form_login_redirect.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormAuth(
                strategy="form",
                action="/goform/login",
                success=FormSuccess(redirect="/dashboard"),
            )
            manager = FormAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is False
            assert "redirect mismatch" in result.error.lower()
            assert "/dashboard" in result.error


# ---------------------------------------------------------------------------
# Network error paths — table-driven
# ---------------------------------------------------------------------------

# ┌──────────────────────────┬─────────────────────────────┬──────────────────────────┐
# │ scenario                 │ config                      │ expected error fragment   │
# ├──────────────────────────┼─────────────────────────────┼──────────────────────────┤
# │ login page prefetch fail │ login_page="/login.html"    │ "pre-fetch failed"       │
# │ login POST fail          │ no login_page               │ "POST failed"            │
# └──────────────────────────┴─────────────────────────────┴──────────────────────────┘

# fmt: off
NETWORK_ERROR_CASES = [
    # (description,               login_page,    mock_method, expected_error)
    ("login_page_prefetch_fail",  "/login.html", "get",       "pre-fetch failed"),
    ("login_post_fail",           "",            "request",   "POST failed"),
]
# fmt: on


@pytest.mark.parametrize(
    "desc,login_page,mock_method,expected_error",
    NETWORK_ERROR_CASES,
    ids=[c[0] for c in NETWORK_ERROR_CASES],
)
def test_network_error_propagates(
    session: requests.Session,
    desc: str,
    login_page: str,
    mock_method: str,
    expected_error: str,
) -> None:
    """ConnectionError propagates for collector to classify as CONNECTIVITY."""
    config = FormAuth(
        strategy="form",
        action="/goform/login",
        login_page=login_page,
    )
    manager = FormAuthManager(config)
    manager.configure_session(session, {})

    with (
        patch.object(
            session,
            mock_method,
            side_effect=requests.ConnectionError("refused"),
        ),
        pytest.raises(requests.ConnectionError),
    ):
        manager.authenticate(
            session,
            "http://192.168.100.1",
            "admin",
            "password",
        )
