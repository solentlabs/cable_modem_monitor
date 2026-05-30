"""Tests for UrlTokenAuthManager."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.url_token import UrlTokenAuthManager
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import UrlTokenAuth
from solentlabs.cable_modem_monitor_core.test_harness import HARMockServer

from .conftest import load_auth_fixture

# Expected token extracted from har_url_token_login_body_token fixture response body.
_BODY_TOKEN = "ddgFdG7bqJDDJIBXNfyMSPfDdgjG8PC"

# Extra UrlTokenAuth fields needed for the body-token variant (prefix in URL and on data requests).
_BODY_TOKEN_AUTH_CONFIG = {"login_prefix": "login_", "token_prefix": "ct_"}

# Credentials used across all url_token auth tests.
_USERNAME = "admin"
_PASSWORD = "password"
_BTOA_CREDENTIAL = base64.b64encode(f"{_USERNAME}:{_PASSWORD}".encode()).decode("ascii")


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
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, _USERNAME, _PASSWORD)
            assert result.success is True

    def test_session_cookie_set_after_login(self, session: requests.Session) -> None:
        """Session cookie is set after successful login for runner to extract."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, _USERNAME, _PASSWORD)
            assert result.success is True
            # Runner extracts URL token from session cookies, not auth_context
            assert session.cookies.get("sessionId") == "tok_abc123"

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
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, _USERNAME, _PASSWORD)
            assert result.success is True

    def test_success_indicator_absent_extracts_body_as_token(self, session: requests.Session) -> None:
        """Body without success_indicator is treated as session token.

        success_indicator is a response type discriminator:
        - Present → body is data page
        - Absent → body is the token string
        """
        entries, _ = load_auth_fixture("har_url_token_login_error.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                success_indicator="Downstream Bonded Channels",
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, _USERNAME, _PASSWORD)
            # New behavior: body without indicator = token extraction (not failure)
            assert result.success is True
            assert result.auth_context.url_token == "Error: bad credentials"

    def test_token_branch_does_not_advertise_reuse(self, session: requests.Session) -> None:
        """Token-extraction branch must NOT populate response/response_url.

        Per AuthResult contract (auth/base.py) and RESOURCE_LOADING_SPEC.md
        § Auth Response Reuse, ``response`` and ``response_url`` exist solely
        to flag a login response that landed on a data page so the loader
        can skip re-fetching. When the body is just a session token, the
        login URL still resolves to a parser-configured path (e.g.,
        ``/cmconnectionstatus.html`` for SB8200) — but the body is not the
        data page. Advertising it as reusable causes the loader to decode
        the token string as HTML and skip the real data fetch.

        Regression: SB8200 #81 (dtaubert v3.14.0-beta.2 — 0/0 channels).
        """
        entries, _ = load_auth_fixture("har_url_token_login_body_token.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                login_prefix="login_",
                success_indicator="Downstream Bonded Channels",
                token_prefix="ct_",
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, _USERNAME, _PASSWORD)

            assert result.success is True
            assert result.auth_context.url_token == _BODY_TOKEN
            # Contract: token branch does not advertise reuse
            assert result.response is None
            assert result.response_url == ""

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
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, _USERNAME, _PASSWORD)
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
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, _USERNAME, _PASSWORD)
            assert result.success is True
            assert session.auth == (_USERNAME, _PASSWORD)

    def test_data_page_branch_advertises_reuse(self, session: requests.Session) -> None:
        """Data-page branch populates response/response_url for loader reuse.

        Per RESOURCE_LOADING_SPEC.md § Auth Response Reuse, when the login
        response body IS the data page (success_indicator present), the
        AuthResult carries the response so the loader can skip re-fetching.
        Pairs with test_token_branch_does_not_advertise_reuse.
        """
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                success_indicator="Downstream Bonded Channels",
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, _USERNAME, _PASSWORD)
            assert result.success is True
            assert result.response is not None
            assert result.response_url == "/login.html"

    def test_cookies_available_for_runner(self, session: requests.Session) -> None:
        """Session cookies are available for runner to extract url_token."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, _USERNAME, _PASSWORD)
            assert result.success is True
            # Cookies are on the session — runner reads them via cookie_name
            assert len(session.cookies) > 0

    @pytest.mark.parametrize(
        "fixture,extra_config,expect_btoa_cookie,expect_url_token",
        [
            ("har_url_token_login_empty_body.json", {}, True, ""),
            ("har_url_token_login_body_token.json", _BODY_TOKEN_AUTH_CONFIG, False, _BODY_TOKEN),
        ],
        ids=["empty-body-injects-btoa", "body-token-skips-injection"],
    )
    def test_inject_credential_cookie(
        self,
        session: requests.Session,
        fixture: str,
        extra_config: dict,
        expect_btoa_cookie: bool,
        expect_url_token: str,
    ) -> None:
        """inject_credential_cookie fires only when no body token was extracted.

        When the auth response body is empty, the firmware JS would call
        createCookie("credential", btoa(user+":"+pass)) client-side — Core
        replicates this with inject_credential_cookie. When a server-issued
        body token is present, it goes to auth_context.url_token and the
        credential injection is skipped to avoid overwriting the server's token.
        """
        entries, _ = load_auth_fixture(fixture)
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                ajax_login=True,
                inject_credential_cookie=True,
                cookie_name="credential",
                **extra_config,
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, _USERNAME, _PASSWORD)

            assert result.success is True
            assert result.auth_context.url_token == expect_url_token
            if expect_btoa_cookie:
                assert session.cookies.get("credential") == _BTOA_CREDENTIAL
                assert result.response is None
                assert result.response_url == ""
            else:
                assert session.cookies.get("credential") is None

    def test_login_non_200(self, session: requests.Session) -> None:
        """Reports error when login GET returns non-200, attaches response."""
        config = UrlTokenAuth(strategy="url_token", login_page="/login.html")
        manager = UrlTokenAuthManager(config)
        manager.configure_session(session, {})

        resp = MagicMock()
        resp.status_code = 500
        with patch.object(session, "get", return_value=resp):
            result = manager.authenticate(session, "http://192.168.100.1", _USERNAME, _PASSWORD)

        assert result.success is False
        assert "500" in result.error
        assert result.response is resp

    def test_login_request_exception(self, session: requests.Session) -> None:
        """Non-connectivity RequestException returns AuthResult; ConnectionError propagates."""
        config = UrlTokenAuth(strategy="url_token", login_page="/login.html")
        manager = UrlTokenAuthManager(config)
        manager.configure_session(session, {})

        with patch.object(session, "get", side_effect=requests.RequestException("redirects")):
            result = manager.authenticate(session, "http://192.168.100.1", _USERNAME, _PASSWORD)

        assert result.success is False
        assert "URL token login failed" in result.error

    def test_login_connection_error_propagates(self, session: requests.Session) -> None:
        """ConnectionError on login GET propagates for collector to classify."""
        config = UrlTokenAuth(strategy="url_token", login_page="/login.html")
        manager = UrlTokenAuthManager(config)
        manager.configure_session(session, {})

        with (
            patch.object(session, "get", side_effect=requests.ConnectionError("refused")),
            pytest.raises(requests.ConnectionError),
        ):
            manager.authenticate(session, "http://127.0.0.1:1", _USERNAME, _PASSWORD)
