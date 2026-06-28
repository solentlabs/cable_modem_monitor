"""Tests for v3.13→v3.14 gap analysis fixes (G-1, G-2, G-3, G-6, G-9).

Covers:
- G-1: url_token body token extraction with success_indicator guard
- G-2: Pre-login cookie clearing
- G-3: Form auth Referer header
- G-6: HNAP header parsing warning filter
- G-9: Auth log_level parameter

G-7 (HNAP auth diagnostics) was retired: ``HnapAuthDiagnostics`` is
replaced by the generic on-demand adapter-based auth capture in
``auth/http_capture.py``. See tests/auth/test_http_capture.py for the
replacement coverage.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.form import FormAuthManager
from solentlabs.cable_modem_monitor_core.auth.url_token import UrlTokenAuthManager
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (
    FormAuth,
    UrlTokenAuth,
)
from solentlabs.cable_modem_monitor_core.test_harness import HARMockServer

from .conftest import load_auth_fixture

# ┌────────────────────────────────────────────────────────────────────┐
# │ G-1: url_token body token extraction                              │
# ├────────────────────────┬───────────────────────┬──────────────────┤
# │ scenario               │ indicator in body?    │ expected         │
# ├────────────────────────┼───────────────────────┼──────────────────┤
# │ data page response     │ yes                   │ token=""         │
# │ token string response  │ no                    │ token=body       │
# │ empty body, has cookie │ no                    │ token=cookie     │
# │ empty body, no cookie  │ no                    │ token=""         │
# └────────────────────────┴───────────────────────┴──────────────────┘
#
_IND = "Downstream Bonded Channels"

# fmt: off
G1_BODY_TOKEN_CASES = [
    # (desc,                      body,                       indicator, cookie,      expected)
    ("data page response",        f"{_IND} <table>data</table>", _IND,  "",          ""),
    ("token string response",     "tok_abc123",                  _IND,  "",          "tok_abc123"),
    ("empty body cookie fallback", "",                           _IND,  "tok_cookie", "tok_cookie"),
    ("empty body no cookie",      "",                            _IND,  "",          ""),
]
# fmt: on


class TestG1BodyTokenExtraction:
    """G-1: url_token extracts session token from response body."""

    @pytest.mark.parametrize(
        "desc, body, indicator, cookie_val, expected_token",
        G1_BODY_TOKEN_CASES,
        ids=[c[0] for c in G1_BODY_TOKEN_CASES],
    )
    def test_body_token_extraction(
        self,
        session: requests.Session,
        desc: str,
        body: str,
        indicator: str,
        cookie_val: str,
        expected_token: str,
    ) -> None:
        """success_indicator discriminates between data page and token."""
        entries = [
            {
                "request": {"method": "GET", "url": "http://192.168.100.1/login.html"},
                "response": {
                    "status": 200,
                    "headers": (
                        [{"name": "Set-Cookie", "value": f"sessionId={cookie_val}; Path=/"}] if cookie_val else []
                    ),
                    "content": {"text": body},
                },
            }
        ]
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                success_indicator=indicator,
                cookie_name="sessionId",
            )
            manager = UrlTokenAuthManager(config)
            result = manager.authenticate(session, server.base_url, "admin", "pw")
            assert result.success is True
            assert result.auth_context.url_token == expected_token

    def test_data_page_returns_response_for_reuse(self, session: requests.Session) -> None:
        """When body is data page, response is returned for auth response reuse."""
        entries = [
            {
                "request": {"method": "GET", "url": "http://192.168.100.1/login.html"},
                "response": {
                    "status": 200,
                    "headers": [],
                    "content": {"text": "Downstream Bonded Channels <table>data</table>"},
                },
            }
        ]
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                success_indicator="Downstream Bonded Channels",
            )
            manager = UrlTokenAuthManager(config)
            result = manager.authenticate(session, server.base_url, "admin", "pw")
            assert result.success is True
            assert result.response is not None
            assert "Downstream Bonded Channels" in result.response.text


# ┌────────────────────────────────────────────────────────────────────┐
# │ G-2: Pre-login cookie clearing                                    │
# └────────────────────────────────────────────────────────────────────┘


class TestG2PreLoginCookieClearing:
    """G-2: url_token clears stale session cookie before login."""

    def test_stale_cookie_cleared_before_login(self, session: requests.Session) -> None:
        """Existing session cookie is deleted before the login request."""
        entries = [
            {
                "request": {"method": "GET", "url": "http://192.168.100.1/login.html"},
                "response": {
                    "status": 200,
                    "headers": [{"name": "Set-Cookie", "value": "sessionId=new_token; Path=/"}],
                    "content": {"text": "tok_fresh"},
                },
            }
        ]
        # Set stale cookie before login
        session.cookies.set("sessionId", "stale_token")

        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                cookie_name="sessionId",
            )
            manager = UrlTokenAuthManager(config)
            result = manager.authenticate(session, server.base_url, "admin", "pw")
            assert result.success is True
            # New cookie set by server, not the stale one
            assert session.cookies.get("sessionId") == "new_token"

    def test_no_clear_when_no_cookie_name(self, session: requests.Session) -> None:
        """No clearing when cookie_name is not configured."""
        entries = [
            {
                "request": {"method": "GET", "url": "http://192.168.100.1/login.html"},
                "response": {
                    "status": 200,
                    "headers": [],
                    "content": {"text": "tok_abc"},
                },
            }
        ]
        session.cookies.set("sessionId", "existing")

        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                cookie_name="",
            )
            manager = UrlTokenAuthManager(config)
            result = manager.authenticate(session, server.base_url, "admin", "pw")
            assert result.success is True
            # Old cookie is still there — not cleared
            assert session.cookies.get("sessionId") == "existing"


# ┌────────────────────────────────────────────────────────────────────┐
# │ G-3: Form auth Referer header                                     │
# └────────────────────────────────────────────────────────────────────┘


class TestG3FormRefererHeader:
    """G-3: FormAuthManager sends Referer header on login POST."""

    def test_referer_header_sent(self, session: requests.Session) -> None:
        """Login POST includes Referer: {base_url}.

        Verified by hooking into session.request to capture the headers
        that were actually sent.
        """
        entries, _ = load_auth_fixture("har_form_login.json")
        sent_headers: dict[str, str] = {}
        original_request = session.request

        def capturing_request(*args: Any, **kwargs: Any) -> requests.Response:
            """Capture headers from the request call."""
            hdrs = kwargs.get("headers", {})
            if isinstance(hdrs, dict):
                sent_headers.update(hdrs)
            return original_request(*args, **kwargs)

        session.request = capturing_request  # type: ignore[assignment]

        with HARMockServer(entries) as server:
            config = FormAuth(
                strategy="form",
                action="/goform/login",
            )
            manager = FormAuthManager(config)
            result = manager.authenticate(session, server.base_url, "admin", "pw")
            assert result.success is True
            assert "Referer" in sent_headers
            assert server.base_url in sent_headers["Referer"]


# G-6 (HNAP header parsing warning filter) was consolidated. The
# ``_HNAPHeaderParsingFilter`` on the ``urllib3.connectionpool`` logger
# is replaced by ``log_filters.SuppressHeaderParsingWarning``, which
# covers both the connection and connectionpool loggers (urllib3 moved
# the warning between 1.26 and 2.x — see issue #98). Coverage lives in
# ``tests/test_log_filters.py``.


# G-7 (HNAP auth diagnostics) was retired. The per-strategy
# ``HnapAuthDiagnostics`` dataclass is replaced by the adapter-based
# on-demand capture in ``auth/http_capture.py``; see
# ``tests/auth/test_http_capture.py`` for coverage.


# ┌────────────────────────────────────────────────────────────────────┐
# │ G-9: Auth log_level parameter                                      │
# ├──────────────────┬─────────────────┬───────────────────────────────┤
# │ strategy         │ log_level       │ expected behavior             │
# ├──────────────────┼─────────────────┼───────────────────────────────┤
# │ form             │ INFO            │ success log at INFO           │
# │ form             │ DEBUG           │ success log at DEBUG          │
# │ url_token        │ INFO            │ success log at INFO           │
# └──────────────────┴─────────────────┴───────────────────────────────┘


class TestG9AuthLogLevel:
    """G-9: Auth managers respect log_level parameter.

    Auth success logging was moved from individual auth managers to the
    collector (which logs with [MODEL] prefix). The log_level parameter
    remains on the base interface for error/warning logging.
    """

    def test_form_auth_succeeds_without_logging(
        self, session: requests.Session, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Form auth success is silent — collector handles the log."""
        entries, _ = load_auth_fixture("har_form_login.json")
        with HARMockServer(entries) as server:
            config = FormAuth(
                strategy="form",
                action="/goform/login",
            )
            manager = FormAuthManager(config)
            with caplog.at_level(logging.DEBUG):
                result = manager.authenticate(
                    session,
                    server.base_url,
                    "admin",
                    "pw",
                )
            assert result.success is True
            auth_logs = [r for r in caplog.records if "login succeeded" in r.message.lower()]
            assert len(auth_logs) == 0
