"""Tests for ModemDataCollector.

Covers signal classification, session lifecycle, logout, and login
page detection. Uses the HAR mock server for integration tests.

Use case coverage (collector level):
- UC-01: First poll — fresh login
- UC-02: Subsequent poll — session reuse
- UC-04: Zero channels with system_info
- UC-06: Single-session modem — logout after poll
- UC-17: LOAD_AUTH — 401 on data page
- UC-19: Login page detection
- UC-30: Connection refused — CONNECTIVITY
- UC-33: Parser error — PARSE_ERROR
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.base import AuthContext, AuthResult
from solentlabs.cable_modem_monitor_core.loaders.fetch_list import ResourceTarget
from solentlabs.cable_modem_monitor_core.loaders.hnap import HNAPLoadError
from solentlabs.cable_modem_monitor_core.loaders.http import (
    HTTPResourceLoader,
    LoginPageDetectedError,
    ResourceLoadError,
)
from solentlabs.cable_modem_monitor_core.orchestration.collector import (
    LoginLockoutError,
    ModemDataCollector,
    _should_detect_login_pages,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    CollectorSignal,
)

# ------------------------------------------------------------------
# Helpers — minimal modem configs as plain objects
# ------------------------------------------------------------------


def _make_config(
    *,
    auth_type: str = "none",
    transport: str = "http",
    cookie_name: str = "",
    max_concurrent: int = 0,
    logout_endpoint: str = "",
    timeout: int = 10,
) -> Any:
    """Build a minimal ModemConfig-like object for testing.

    Uses MagicMock to simulate the Pydantic model without needing
    full validation. Only the fields the collector reads are set.
    """
    config = MagicMock()
    config.transport = transport
    config.timeout = timeout

    # Auth
    if auth_type == "none":
        from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (
            NoneAuth,
        )

        config.auth = NoneAuth(strategy="none")
    elif auth_type == "form":
        config.auth = MagicMock()
        config.auth.strategy = "form"
        config.auth.action = "/login.htm"
        config.auth.username_field = "username"
        config.auth.password_field = "password"
    elif auth_type == "basic":
        from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (
            BasicAuth,
        )

        config.auth = BasicAuth(strategy="basic")
    else:
        config.auth = MagicMock()
        config.auth.strategy = auth_type

    # Session
    if cookie_name or max_concurrent or logout_endpoint:
        config.session = MagicMock()
        config.session.cookie_name = cookie_name
        config.session.max_concurrent = max_concurrent
        config.session.token_prefix = ""
        config.session.headers = {}
    else:
        config.session = None

    # Actions (logout)
    if logout_endpoint:
        from solentlabs.cable_modem_monitor_core.models.modem_config.actions import (
            HttpAction,
        )

        config.actions = MagicMock()
        config.actions.logout = HttpAction(
            type="http",
            method="GET",
            endpoint=logout_endpoint,
        )
    else:
        config.actions = None

    # Behaviors
    config.behaviors = None

    return config


# ------------------------------------------------------------------
# Simple mock server for collector tests
# ------------------------------------------------------------------


class _SimpleHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for collector tests."""

    def do_GET(self) -> None:  # noqa: N802
        """Serve configured responses."""
        server: _SimpleServer = self.server  # type: ignore[assignment]
        path = self.path.split("?")[0]

        response = server.responses.get(path)
        if response is None:
            self.send_response(404)
            self.end_headers()
            return

        status, body = response
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress logging."""


class _SimpleServer(HTTPServer):
    """Test HTTP server with configurable responses."""

    def __init__(self, responses: dict[str, tuple[int, str]]) -> None:
        self.responses = responses
        super().__init__(("127.0.0.1", 0), _SimpleHandler)

    @property
    def base_url(self) -> str:
        """Server base URL."""
        return f"http://127.0.0.1:{self.server_address[1]}"

    def __enter__(self) -> _SimpleServer:
        """Start server in background thread."""
        self._thread = Thread(target=self.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        """Stop server."""
        self.shutdown()
        self._thread.join(timeout=5)
        self.server_close()


# ------------------------------------------------------------------
# HTML test data — named constants, not inline in test methods
# ------------------------------------------------------------------

_LOGIN_PAGE_HTML = '<html><form><input type="password" name="pw"></form></html>'
_DATA_PAGE_HTML = "<html><table><tr><td>data</td></tr></table></html>"


# ------------------------------------------------------------------
# Tests — login page detection utility (table-driven)
# ------------------------------------------------------------------

# ┌────────────┬───────────┬──────────┬──────────────────────┐
# │ auth_type  │ transport │ expected │ description          │
# ├────────────┼───────────┼──────────┼──────────────────────┤
# │ "none"     │ "http"    │ False    │ no-auth              │
# │ "basic"    │ "http"    │ False    │ stateless            │
# │ "form"     │ "http"    │ True     │ form-based           │
# │ "hnap"     │ "hnap"    │ False    │ hnap transport       │
# │ None       │ "http"    │ False    │ no auth config       │
# └────────────┴───────────┴──────────┴──────────────────────┘
#
# fmt: off
LOGIN_PAGE_DETECTION_CASES = [
    # (auth_type,  transport, set_none, expected, description)
    ("none",       "http",    False,    False,    "no-auth — detection disabled"),
    ("basic",      "http",    False,    False,    "stateless — detection disabled"),
    ("form",       "http",    False,    True,     "form-based — detection enabled"),
    ("hnap",       "hnap",    False,    False,    "hnap transport — detection disabled"),
    ("none",       "http",    True,     False,    "no auth config — detection disabled"),
]
# fmt: on


@pytest.mark.parametrize(
    "auth_type,transport,set_none,expected,desc",
    LOGIN_PAGE_DETECTION_CASES,
    ids=[c[4] for c in LOGIN_PAGE_DETECTION_CASES],
)
def test_should_detect_login_pages(auth_type: str, transport: str, set_none: bool, expected: bool, desc: str) -> None:
    """_should_detect_login_pages returns correct value per auth strategy."""
    config = _make_config(auth_type=auth_type, transport=transport)
    if set_none:
        config.auth = None
    assert _should_detect_login_pages(config) is expected


# ------------------------------------------------------------------
# Tests — signal classification (table-driven)
# ------------------------------------------------------------------


def _run_collector_with_failure(
    *,
    auth_side_effect: Any = None,
    auth_return: Any = None,
    load_side_effect: Any = None,
    parse_side_effect: Any = None,
) -> Any:
    """Create a collector and execute with controlled failures.

    Patches each pipeline phase. Phases after the failing one are
    patched with success stubs so the failure is isolated.
    """
    config = _make_config(auth_type="none")
    collector = ModemDataCollector(config, MagicMock(), None, "http://localhost", "", "")

    auth_patch = (
        patch.object(collector, "authenticate", side_effect=auth_side_effect)
        if auth_side_effect
        else patch.object(
            collector,
            "authenticate",
            return_value=auth_return or MagicMock(success=True),
        )
    )
    load_patch = (
        patch.object(collector, "_load_resources", side_effect=load_side_effect)
        if load_side_effect
        else patch.object(collector, "_load_resources", return_value={})
    )
    parse_patch = (
        patch.object(collector, "_parse", side_effect=parse_side_effect)
        if parse_side_effect
        else patch.object(
            collector,
            "_parse",
            return_value={"downstream": [], "upstream": [], "system_info": {}},
        )
    )

    with auth_patch, load_patch, parse_patch:
        return collector.execute()


# ┌──────────┬──────────────────────────┬────────────────┬─────────────────────┐
# │ phase    │ side_effect              │ signal         │ description         │
# ├──────────┼──────────────────────────┼────────────────┼─────────────────────┤
# │ auth     │ AuthResult(False)        │ AUTH_FAILED    │ wrong credentials   │
# │ auth     │ LoginLockoutError        │ AUTH_LOCKOUT   │ firmware lockout    │
# │ load     │ requests.ConnectionError │ CONNECTIVITY   │ connection refused  │
# │ load     │ ResourceLoadError(401)   │ LOAD_AUTH      │ stale session       │
# │ load     │ ResourceLoadError(500)   │ LOAD_ERROR     │ server error        │
# │ load     │ LoginPageDetectedError   │ LOAD_AUTH      │ login page detected │
# │ parse    │ ValueError               │ PARSE_ERROR    │ malformed response  │
# └──────────┴──────────────────────────┴────────────────┴─────────────────────┘
_AUTH_FAIL = {"auth_return": AuthResult(success=False, error="wrong password")}
_AUTH_LOCKOUT = {"auth_side_effect": LoginLockoutError("LOCKUP")}
_LOAD_CONN = {"load_side_effect": requests.ConnectionError("refused")}
_LOAD_401 = {
    "load_side_effect": ResourceLoadError("HTTP 401", status_code=401, path="/d.htm"),
}
_LOAD_500 = {
    "load_side_effect": ResourceLoadError("HTTP 500", status_code=500, path="/d.htm"),
}
_LOAD_LOGIN = {"load_side_effect": LoginPageDetectedError("/d.htm")}
_PARSE_ERR = {"parse_side_effect": ValueError("bad HTML")}

# fmt: off
SIGNAL_CLASSIFICATION_CASES = [
    # (kwargs,       expected_signal,              description)
    (_AUTH_FAIL,     CollectorSignal.AUTH_FAILED,   "wrong credentials"),
    (_AUTH_LOCKOUT,  CollectorSignal.AUTH_LOCKOUT,  "firmware lockout"),
    (_LOAD_CONN,     CollectorSignal.CONNECTIVITY,  "connection refused"),
    (_LOAD_401,      CollectorSignal.LOAD_AUTH,     "stale session (401)"),
    (_LOAD_500,      CollectorSignal.LOAD_ERROR,    "server error (500)"),
    (_LOAD_LOGIN,    CollectorSignal.LOAD_AUTH,     "login page detected"),
    (_PARSE_ERR,     CollectorSignal.PARSE_ERROR,   "malformed response"),
]
# fmt: on


@pytest.mark.parametrize(
    "kwargs,expected_signal,desc",
    SIGNAL_CLASSIFICATION_CASES,
    ids=[c[2] for c in SIGNAL_CLASSIFICATION_CASES],
)
def test_signal_classification(kwargs: dict[str, Any], expected_signal: CollectorSignal, desc: str) -> None:
    """execute() classifies pipeline failures into correct signals."""
    result = _run_collector_with_failure(**kwargs)
    assert result.signal == expected_signal
    assert result.success is False


# ------------------------------------------------------------------
# Tests — HNAP signal classification (table-driven, UC-21/UC-22)
# ------------------------------------------------------------------


def _make_hnap_load_error(
    *,
    status_code: int | None = None,
    cause: Exception | None = None,
) -> HNAPLoadError:
    """Build an HNAPLoadError with controlled attributes."""
    msg = f"HNAP request returned HTTP {status_code}" if status_code else "HNAP request failed"
    err = HNAPLoadError(msg, status_code=status_code)
    if cause is not None:
        err.__cause__ = cause
    return err


def _run_hnap_collector_with_failure(
    *,
    load_error: HNAPLoadError,
    session_reused: bool,
) -> Any:
    """Create an HNAP collector and execute with a controlled HNAP failure.

    Sets _session_reused to simulate whether authenticate() short-circuited.
    Patches _load_resources to raise the given HNAPLoadError.
    """
    config = _make_config(auth_type="hnap", transport="hnap")
    collector = ModemDataCollector(config, MagicMock(), None, "http://localhost", "", "pw")

    with (
        patch.object(
            collector,
            "authenticate",
            return_value=MagicMock(success=True),
        ),
        patch.object(collector, "_load_resources", side_effect=load_error),
        patch.object(
            collector,
            "_parse",
            return_value={"downstream": [], "upstream": [], "system_info": {}},
        ),
    ):
        collector._session_reused = session_reused
        return collector.execute()


# ┌───────────────────────────────────┬──────────────┬────────────────┬───────────────────────────────┐
# │ HNAPLoadError                     │ sess_reused  │ expected       │ description                   │
# ├───────────────────────────────────┼──────────────┼────────────────┼───────────────────────────────┤
# │ status_code=None + ConnError      │ True         │ CONNECTIVITY   │ UC-30: connection refused      │
# │ status_code=None + Timeout        │ True         │ CONNECTIVITY   │ UC-31: timeout                 │
# │ status_code=401, reused           │ True         │ LOAD_AUTH      │ UC-21: stale session (401)     │
# │ status_code=404, reused           │ True         │ LOAD_AUTH      │ UC-21: S33 stale session (404) │
# │ status_code=500, reused           │ True         │ LOAD_AUTH      │ UC-21: server-side expiry      │
# │ status_code=401, fresh            │ False        │ LOAD_ERROR     │ UC-22: fresh session error     │
# │ status_code=500, fresh            │ False        │ LOAD_ERROR     │ UC-22: fresh session error     │
# │ status_code=None + ValueError     │ True         │ LOAD_ERROR     │ JSON parse error               │
# │ status_code=None + ValueError     │ False        │ LOAD_ERROR     │ JSON parse error (fresh)       │
# └───────────────────────────────────┴──────────────┴────────────────┴───────────────────────────────┘
#
_HNAP_CONN = _make_hnap_load_error(cause=requests.ConnectionError("refused"))
_HNAP_TIMEOUT = _make_hnap_load_error(cause=requests.Timeout("timed out"))
_HNAP_401 = _make_hnap_load_error(status_code=401)
_HNAP_404 = _make_hnap_load_error(status_code=404)
_HNAP_500 = _make_hnap_load_error(status_code=500)
_HNAP_JSON = _make_hnap_load_error(cause=ValueError("No JSON"))

# fmt: off
HNAP_SIGNAL_CASES = [
    # (load_error,  reused, expected,                     description)
    (_HNAP_CONN,    True,   CollectorSignal.CONNECTIVITY, "UC-30: conn refused"),
    (_HNAP_TIMEOUT, True,   CollectorSignal.CONNECTIVITY, "UC-31: timeout"),
    (_HNAP_401,     True,   CollectorSignal.LOAD_AUTH,    "UC-21: stale (401)"),
    (_HNAP_404,     True,   CollectorSignal.LOAD_AUTH,    "UC-21: stale (404)"),
    (_HNAP_500,     True,   CollectorSignal.LOAD_AUTH,    "UC-21: stale (500)"),
    (_HNAP_401,     False,  CollectorSignal.LOAD_ERROR,   "UC-22: fresh 401"),
    (_HNAP_500,     False,  CollectorSignal.LOAD_ERROR,   "UC-22: fresh 500"),
    (_HNAP_JSON,    True,   CollectorSignal.LOAD_ERROR,   "JSON parse (reused)"),
    (_HNAP_JSON,    False,  CollectorSignal.LOAD_ERROR,   "JSON parse (fresh)"),
]
# fmt: on


@pytest.mark.parametrize(
    "load_error,session_reused,expected_signal,desc",
    HNAP_SIGNAL_CASES,
    ids=[c[3] for c in HNAP_SIGNAL_CASES],
)
def test_hnap_signal_classification(
    load_error: HNAPLoadError,
    session_reused: bool,
    expected_signal: CollectorSignal,
    desc: str,
) -> None:
    """HNAP errors route to correct signal based on status code + session reuse (UC-21/UC-22)."""
    result = _run_hnap_collector_with_failure(load_error=load_error, session_reused=session_reused)
    assert result.signal == expected_signal
    assert result.success is False


# ------------------------------------------------------------------
# Tests — session lifecycle (behavioral, inline)
# ------------------------------------------------------------------


class TestSessionIsValid:
    """session_is_valid property checks."""

    def test_no_auth_always_valid(self) -> None:
        """No-auth modems are always valid."""
        config = _make_config(auth_type="none")
        collector = ModemDataCollector(config, None, None, "http://localhost", "", "")
        assert collector.session_is_valid is True

    def test_basic_auth_invalid_before_first_auth(self) -> None:
        """Basic auth requires authenticate() to set session.auth."""
        config = _make_config(auth_type="basic")
        collector = ModemDataCollector(config, None, None, "http://localhost", "", "")
        assert collector.session_is_valid is False

    def test_form_auth_invalid_before_login(self) -> None:
        """Form auth is invalid before first authenticate()."""
        config = _make_config(auth_type="form", cookie_name="sid")
        collector = ModemDataCollector(config, None, None, "http://localhost", "", "")
        assert collector.session_is_valid is False

    def test_clear_session_resets(self) -> None:
        """clear_session() invalidates the session."""
        config = _make_config(auth_type="form", cookie_name="sid")
        collector = ModemDataCollector(config, None, None, "http://localhost", "", "")
        # Simulate authenticated state
        collector._auth_context = MagicMock(url_token="", private_key="")
        collector._session.cookies.set("sid", "abc123")
        assert collector.session_is_valid is True

        collector.clear_session()
        assert collector.session_is_valid is False
        assert collector._auth_context is None


# ------------------------------------------------------------------
# Tests — successful collection (behavioral, inline)
# ------------------------------------------------------------------


class TestSuccessfulCollection:
    """execute() returns OK signal with modem data on success."""

    def test_ok_with_channels(self) -> None:
        """Successful parse returns OK with modem data."""
        config = _make_config(auth_type="none")
        collector = ModemDataCollector(config, MagicMock(), None, "http://localhost", "", "")
        modem_data = {
            "downstream": [{"channel_id": 1}],
            "upstream": [{"channel_id": 1}],
            "system_info": {},
        }
        with (
            patch.object(
                collector,
                "authenticate",
                return_value=MagicMock(success=True),
            ),
            patch.object(
                collector,
                "_load_resources",
                return_value={"data": "ok"},
            ),
            patch.object(
                collector,
                "_parse",
                return_value=modem_data,
            ),
        ):
            result = collector.execute()

        assert result.success is True
        assert result.signal == CollectorSignal.OK
        assert result.modem_data is not None
        assert len(result.modem_data["downstream"]) == 1

    def test_ok_with_zero_channels(self) -> None:
        """Zero channels is a valid success (UC-04)."""
        config = _make_config(auth_type="none")
        collector = ModemDataCollector(config, MagicMock(), None, "http://localhost", "", "")
        modem_data = {
            "downstream": [],
            "upstream": [],
            "system_info": {"firmware": "1.0"},
        }
        with (
            patch.object(
                collector,
                "authenticate",
                return_value=MagicMock(success=True),
            ),
            patch.object(
                collector,
                "_load_resources",
                return_value={"data": "ok"},
            ),
            patch.object(
                collector,
                "_parse",
                return_value=modem_data,
            ),
        ):
            result = collector.execute()

        assert result.success is True
        assert result.signal == CollectorSignal.OK
        assert result.modem_data is not None
        assert result.modem_data["downstream"] == []


# ------------------------------------------------------------------
# Tests — logout (behavioral, inline)
# ------------------------------------------------------------------


class TestLogout:
    """Logout execution for single-session modems (UC-06)."""

    def test_logout_called_for_single_session(self) -> None:
        """Logout action fires after successful collection."""
        config = _make_config(
            auth_type="none",
            cookie_name="sid",
            max_concurrent=1,
            logout_endpoint="/logout",
        )
        collector = ModemDataCollector(config, MagicMock(), None, "http://localhost", "", "")
        modem_data = {"downstream": [{"channel_id": 1}], "upstream": [], "system_info": {}}

        with (
            patch.object(
                collector,
                "authenticate",
                return_value=MagicMock(success=True),
            ),
            patch.object(
                collector,
                "_load_resources",
                return_value={},
            ),
            patch.object(
                collector,
                "_parse",
                return_value=modem_data,
            ),
            patch("solentlabs.cable_modem_monitor_core.orchestration.collector.execute_action") as mock_action,
        ):
            result = collector.execute()

        assert result.success is True
        mock_action.assert_called_once()

    def test_no_logout_without_max_concurrent(self) -> None:
        """Logout not called when max_concurrent != 1."""
        config = _make_config(
            auth_type="none",
            cookie_name="sid",
            max_concurrent=0,
            logout_endpoint="/logout",
        )
        collector = ModemDataCollector(config, MagicMock(), None, "http://localhost", "", "")
        modem_data: dict[str, Any] = {"downstream": [], "upstream": [], "system_info": {}}

        with (
            patch.object(
                collector,
                "authenticate",
                return_value=MagicMock(success=True),
            ),
            patch.object(
                collector,
                "_load_resources",
                return_value={},
            ),
            patch.object(
                collector,
                "_parse",
                return_value=modem_data,
            ),
            patch("solentlabs.cable_modem_monitor_core.orchestration.collector.execute_action") as mock_action,
        ):
            collector.execute()

        mock_action.assert_not_called()

    def test_logout_failure_does_not_affect_result(self) -> None:
        """Logout is best-effort — failure doesn't change success."""
        config = _make_config(
            auth_type="none",
            cookie_name="sid",
            max_concurrent=1,
            logout_endpoint="/logout",
        )
        collector = ModemDataCollector(config, MagicMock(), None, "http://localhost", "", "")
        modem_data = {"downstream": [{"channel_id": 1}], "upstream": [], "system_info": {}}

        with (
            patch.object(
                collector,
                "authenticate",
                return_value=MagicMock(success=True),
            ),
            patch.object(
                collector,
                "_load_resources",
                return_value={},
            ),
            patch.object(
                collector,
                "_parse",
                return_value=modem_data,
            ),
            patch(
                "solentlabs.cable_modem_monitor_core.orchestration.collector.execute_action",
                side_effect=RuntimeError("logout failed"),
            ),
        ):
            result = collector.execute()

        assert result.success is True

    def test_logout_clears_session_for_next_poll(self) -> None:
        """After successful logout, session_is_valid returns False.

        Regression test: without session clearing after logout, the
        collector reuses a stale session on the next poll and hits the
        modem's login page instead of the data page (LOAD_AUTH signal).
        """
        config = _make_config(
            auth_type="form",
            cookie_name="",
            max_concurrent=1,
            logout_endpoint="/logout",
        )
        collector = ModemDataCollector(config, MagicMock(), None, "http://localhost", "", "")
        modem_data: dict[str, Any] = {"downstream": [{"channel_id": 1}], "upstream": [], "system_info": {}}

        # Simulate a successful first poll with logout
        auth_result = MagicMock(success=True, auth_context=AuthContext())
        with (
            patch.object(collector, "authenticate", return_value=auth_result),
            patch.object(collector, "_load_resources", return_value={}),
            patch.object(collector, "_parse", return_value=modem_data),
            patch("solentlabs.cable_modem_monitor_core.orchestration.collector.execute_action"),
        ):
            # Set auth context as if authentication succeeded
            collector._auth_context = AuthContext()
            collector._last_auth_result = auth_result

            result = collector.execute()

        assert result.success is True
        # After logout, session should be cleared
        assert collector.session_is_valid is False
        assert collector._auth_context is None


# ------------------------------------------------------------------
# Tests — login page detection (behavioral, inline — server-based)
# ------------------------------------------------------------------


class TestSessionCreation:
    """Verify ModemDataCollector creates session via create_session().

    The collector must use connectivity.create_session() — not bare
    requests.Session() — so that HTTPS modems with self-signed certs
    get verify=False, and legacy-SSL modems get the LegacySSLAdapter.

    HealthMonitor already does this correctly (modem_health.py).

    Use case coverage:
    - UC-82: HTTPS modem with self-signed certificate
    - UC-83: HTTPS modem with legacy SSL firmware
    """

    def test_session_created_via_factory(self) -> None:
        """Default construction uses create_session(legacy_ssl=False).

        Regression: bare requests.Session() has verify=True, which
        breaks HTTPS modems with self-signed certificates (UC-82).
        """
        config = _make_config(auth_type="none")
        with patch(
            "solentlabs.cable_modem_monitor_core.orchestration.collector.create_session",
        ) as mock_cs:
            mock_session = MagicMock(spec=requests.Session)
            mock_session.headers = {}
            mock_cs.return_value = mock_session

            ModemDataCollector(config, None, None, "http://localhost", "", "")

            mock_cs.assert_called_once_with(legacy_ssl=False)

    def test_legacy_ssl_forwarded(self) -> None:
        """legacy_ssl=True is forwarded to create_session() (UC-83).

        HTTPS modems with old firmware need LegacySSLAdapter mounted
        for cipher negotiation to succeed.
        """
        config = _make_config(auth_type="none")
        with patch(
            "solentlabs.cable_modem_monitor_core.orchestration.collector.create_session",
        ) as mock_cs:
            mock_session = MagicMock(spec=requests.Session)
            mock_session.headers = {}
            mock_cs.return_value = mock_session

            ModemDataCollector(
                config,
                None,
                None,
                "https://192.168.100.1",
                "",
                "",
                legacy_ssl=True,
            )

            mock_cs.assert_called_once_with(legacy_ssl=True)


class TestLoginPageDetection:
    """Login page detection in HTTPResourceLoader."""

    def test_login_page_raises(self) -> None:
        """HTML with password input raises LoginPageDetectedError."""
        responses = {"/data.htm": (200, _LOGIN_PAGE_HTML)}

        with _SimpleServer(responses) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(
                session=session,
                base_url=server.base_url,
                detect_login_pages=True,
            )
            targets = [ResourceTarget(path="/data.htm", format="table", encoding="")]

            with pytest.raises(LoginPageDetectedError) as exc_info:
                loader.fetch(targets)

            assert exc_info.value.path == "/data.htm"

    def test_normal_page_passes(self) -> None:
        """HTML without password input passes through normally."""
        responses = {"/data.htm": (200, _DATA_PAGE_HTML)}

        with _SimpleServer(responses) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(
                session=session,
                base_url=server.base_url,
                detect_login_pages=True,
            )
            targets = [ResourceTarget(path="/data.htm", format="table", encoding="")]

            resources = loader.fetch(targets)
            assert "/data.htm" in resources

    def test_detection_disabled_passes_login_page(self) -> None:
        """With detection disabled, login page is treated as data."""
        responses = {"/data.htm": (200, _LOGIN_PAGE_HTML)}

        with _SimpleServer(responses) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(
                session=session,
                base_url=server.base_url,
                detect_login_pages=False,
            )
            targets = [ResourceTarget(path="/data.htm", format="table", encoding="")]

            # Should NOT raise — detection is disabled
            resources = loader.fetch(targets)
            assert "/data.htm" in resources


# ------------------------------------------------------------------
# Tests — ResourceLoadError attributes (table-driven)
# ------------------------------------------------------------------

# ┌────────┬──────────────────────┬─────────────────────────┐
# │ status │ body                 │ description             │
# ├────────┼──────────────────────┼─────────────────────────┤
# │ 401    │ "Unauthorized"       │ stale session           │
# │ 500    │ "Server Error"       │ server error            │
# └────────┴──────────────────────┴─────────────────────────┘
#
# fmt: off
RESOURCE_LOAD_ERROR_CASES = [
    # (status, body,             description)
    (401,      "Unauthorized",   "stale session (401)"),
    (500,      "Server Error",   "server error (500)"),
]
# fmt: on


@pytest.mark.parametrize(
    "status,body,desc",
    RESOURCE_LOAD_ERROR_CASES,
    ids=[c[2] for c in RESOURCE_LOAD_ERROR_CASES],
)
def test_resource_load_error_attributes(status: int, body: str, desc: str) -> None:
    """ResourceLoadError carries status_code and path from HTTP errors."""
    responses = {"/data.htm": (status, body)}

    with _SimpleServer(responses) as server:
        session = requests.Session()
        loader = HTTPResourceLoader(session=session, base_url=server.base_url)
        targets = [ResourceTarget(path="/data.htm", format="table", encoding="")]

        with pytest.raises(ResourceLoadError) as exc_info:
            loader.fetch(targets)

        assert exc_info.value.status_code == status
        assert exc_info.value.path == "/data.htm"


# ------------------------------------------------------------------
# Tests — mock server logout (behavioral, inline)
# ------------------------------------------------------------------


class TestMockServerLogout:
    """Mock server auth handler logout support."""

    def test_form_handler_logout_clears_session(self) -> None:
        """FormAuthHandler clears session on logout request."""
        from solentlabs.cable_modem_monitor_core.test_harness.auth import (
            FormAuthHandler,
        )

        handler = FormAuthHandler(
            login_path="/login.htm",
            cookie_name="sid",
            logout_path="/logout",
        )

        # Authenticate
        handler.handle_login("POST", "/login.htm", b"", {})
        assert handler.is_authenticated({}) is True

        # Logout
        assert handler.is_logout_request("GET", "/logout") is True
        handler.handle_logout()
        assert handler.is_authenticated({}) is False

    def test_base_handler_no_logout(self) -> None:
        """Base AuthHandler has no logout endpoint."""
        from solentlabs.cable_modem_monitor_core.test_harness.auth import AuthHandler

        handler = AuthHandler()
        assert handler.is_logout_request("GET", "/logout") is False

    def test_form_handler_no_logout_path(self) -> None:
        """FormAuthHandler without logout_path returns False."""
        from solentlabs.cable_modem_monitor_core.test_harness.auth import (
            FormAuthHandler,
        )

        handler = FormAuthHandler(login_path="/login.htm")
        assert handler.is_logout_request("GET", "/logout") is False
