"""Tests for v3.13→v3.14 gap analysis fixes (G-1 through G-9).

Covers:
- G-1: url_token body token extraction with success_indicator guard
- G-2: Pre-login cookie clearing
- G-3: Form auth Referer header
- G-6: HNAP header parsing warning filter
- G-7: HNAP auth diagnostics tracking
- G-9: Auth log_level parameter
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests
from requests.cookies import RequestsCookieJar
from solentlabs.cable_modem_monitor_core.auth.form import FormAuthManager
from solentlabs.cable_modem_monitor_core.auth.hnap import (
    HnapAuthDiagnostics,
    HnapAuthManager,
)
from solentlabs.cable_modem_monitor_core.auth.url_token import UrlTokenAuthManager
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (
    FormAuth,
    HnapAuth,
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


# ┌────────────────────────────────────────────────────────────────────┐
# │ G-6: HNAP header parsing warning filter                           │
# └────────────────────────────────────────────────────────────────────┘


class TestG6HNAPWarningFilter:
    """G-6: urllib3 header parsing warnings are suppressed."""

    def test_filter_suppresses_header_parsing_warnings(self) -> None:
        """The filter drops 'Failed to parse headers' log records."""
        from solentlabs.cable_modem_monitor_core.connectivity import (
            _HNAPHeaderParsingFilter,
        )

        filt = _HNAPHeaderParsingFilter()
        record = logging.LogRecord(
            name="urllib3.connectionpool",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="Failed to parse headers (url=http://192.168.100.1/HNAP1/)",
            args=(),
            exc_info=None,
        )
        # Filter should drop (return False)
        assert filt.filter(record) is False

    def test_filter_passes_normal_warnings(self) -> None:
        """Normal warnings pass through the filter."""
        from solentlabs.cable_modem_monitor_core.connectivity import (
            _HNAPHeaderParsingFilter,
        )

        filt = _HNAPHeaderParsingFilter()
        record = logging.LogRecord(
            name="urllib3.connectionpool",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="Connection pool is full, discarding connection",
            args=(),
            exc_info=None,
        )
        # Normal warning should pass (return True)
        assert filt.filter(record) is True

    def test_filter_installed_on_urllib3_logger(self) -> None:
        """Filter is installed on the urllib3.connectionpool logger."""
        logger = logging.getLogger("urllib3.connectionpool")
        filter_types = [type(f).__name__ for f in logger.filters]
        assert "_HNAPHeaderParsingFilter" in filter_types


# ┌────────────────────────────────────────────────────────────────────┐
# │ G-7: HNAP auth diagnostics                                        │
# └────────────────────────────────────────────────────────────────────┘


class TestG7HnapAuthDiagnostics:
    """G-7: HnapAuthManager stores challenge/login diagnostics."""

    def test_diagnostics_none_before_auth(self) -> None:
        """No diagnostics before any auth attempt."""
        config = HnapAuth(strategy="hnap", hmac_algorithm="md5")
        manager = HnapAuthManager(config)
        assert manager.last_auth_diagnostics is None

    def test_diagnostics_populated_after_auth(self) -> None:
        """Diagnostics populated after successful HNAP auth.

        Uses a mock session with sequential responses to simulate
        the two-phase HNAP login (challenge, then login).
        """
        challenge_json = {
            "LoginResponse": {
                "Challenge": "abc123",
                "PublicKey": "pub456",
                "Cookie": "uid_cookie",
                "LoginResult": "",
            }
        }
        login_json = {"LoginResponse": {"LoginResult": "OK"}}

        # Build mock responses for sequential calls
        mock_challenge = MagicMock()
        mock_challenge.json.return_value = challenge_json
        mock_challenge.status_code = 200

        mock_login = MagicMock()
        mock_login.json.return_value = login_json
        mock_login.status_code = 200

        session = MagicMock(spec=requests.Session)
        session.cookies = RequestsCookieJar()
        session.post = MagicMock(side_effect=[mock_challenge, mock_login])

        config = HnapAuth(strategy="hnap", hmac_algorithm="md5")
        manager = HnapAuthManager(config)
        result = manager.authenticate(
            session,
            "http://192.168.100.1",
            "admin",
            "password",
        )

        assert result.success is True
        diag = manager.last_auth_diagnostics
        assert diag is not None
        assert isinstance(diag, HnapAuthDiagnostics)
        # Challenge request has Login action
        assert "Login" in diag.challenge_request
        # Challenge response has LoginResponse
        assert "LoginResponse" in diag.challenge_response
        # Login request has Login action with "login" action
        assert diag.login_request.get("Login", {}).get("Action") == "login"
        # Login response has LoginResult
        assert "LoginResponse" in diag.login_response

    def test_diagnostics_dataclass_fields(self) -> None:
        """HnapAuthDiagnostics has the expected fields."""
        diag = HnapAuthDiagnostics()
        assert diag.challenge_request == {}
        assert diag.challenge_response == {}
        assert diag.login_request == {}
        assert diag.login_response == {}


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
