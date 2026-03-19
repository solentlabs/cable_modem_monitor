"""Tests for HAR mock server.

Tests cover all three layers: route building, auth handlers, and
HTTP server integration. No modem-specific references.

- Route builder: fixture-driven from JSON HAR entries
- Auth handlers: table-driven for strategy selection
- Server integration: fixture-driven HAR + config
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import requests
from solentlabs.cable_modem_monitor_core.testing.auth import (
    AuthHandler,
    BasicAuthHandler,
    FormAuthHandler,
    create_auth_handler,
)
from solentlabs.cable_modem_monitor_core.testing.routes import (
    build_routes,
    normalize_path,
)
from solentlabs.cable_modem_monitor_core.testing.server import HARMockServer

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_entries(name: str) -> list[dict[str, Any]]:
    """Load HAR entries from a fixture file."""
    data = json.loads((FIXTURES_DIR / name).read_text())
    return list(data["_entries"])


# ---------------------------------------------------------------------------
# Layer 1: Route builder tests (fixture-driven)
# ---------------------------------------------------------------------------


class TestBuildRoutes:
    """Tests for build_routes."""

    def test_basic_route_building(self) -> None:
        """HAR entries produce correct route table."""
        entries = _load_entries("har_entries_no_auth.json")
        routes = build_routes(entries)

        assert ("GET", "/status.html") in routes
        assert ("GET", "/info.html") in routes
        assert routes[("GET", "/status.html")].body == "<html>DS data</html>"
        assert routes[("GET", "/status.html")].status == 200

    def test_post_route(self) -> None:
        """POST entries are routed separately from GET."""
        entries = _load_entries("har_entries_form_auth.json")
        routes = build_routes(entries)

        assert ("POST", "/goform/login") in routes
        assert ("GET", "/status.html") in routes

    def test_duplicate_path_200_wins(self) -> None:
        """For duplicate paths, last 200 response wins."""
        entries = [
            {
                "request": {"method": "GET", "url": "http://192.168.100.1/status.html"},
                "response": {"status": 401, "content": {"text": "Unauthorized"}},
            },
            {
                "request": {"method": "GET", "url": "http://192.168.100.1/status.html"},
                "response": {"status": 200, "content": {"text": "<html>data</html>"}},
            },
        ]
        routes = build_routes(entries)

        assert routes[("GET", "/status.html")].status == 200
        assert routes[("GET", "/status.html")].body == "<html>data</html>"

    def test_non_200_stored_when_no_200(self) -> None:
        """Non-200 response is stored when no 200 exists."""
        entries = [
            {
                "request": {"method": "GET", "url": "http://192.168.100.1/missing.html"},
                "response": {"status": 404, "content": {"text": "Not Found"}},
            },
        ]
        routes = build_routes(entries)

        assert routes[("GET", "/missing.html")].status == 404

    def test_empty_entries(self) -> None:
        """Empty HAR entries produce empty routes."""
        assert build_routes([]) == {}

    def test_entry_without_url(self) -> None:
        """Entries with empty URL are skipped."""
        entries = [{"request": {"method": "GET", "url": ""}, "response": {"status": 200}}]
        assert build_routes(entries) == {}

    def test_response_headers_preserved(self) -> None:
        """Response headers from HAR are preserved in route."""
        entries = _load_entries("har_entries_form_auth.json")
        routes = build_routes(entries)
        headers = routes[("POST", "/goform/login")].headers

        assert ("Set-Cookie", "session=abc123; Path=/") in headers


# ┌──────────────┬──────────────────────┬──────────┐
# │ input        │ expected             │ desc     │
# ├──────────────┼──────────────────────┼──────────┤
# │ /status.html │ /status.html         │ standard │
# │ status.html  │ /status.html         │ no slash │
# │ ""           │ ""                   │ empty    │
# │ /api/data/   │ /api/data/           │ trailing │
# └──────────────┴──────────────────────┴──────────┘
#
# fmt: off
NORMALIZE_PATH_CASES = [
    # (input,         expected,       description)
    ("/status.html",  "/status.html", "standard path"),
    ("status.html",   "/status.html", "missing leading slash"),
    ("",              "",             "empty path"),
    ("/api/data/",    "/api/data/",   "trailing slash preserved"),
]
# fmt: on


@pytest.mark.parametrize("input_path,expected,desc", NORMALIZE_PATH_CASES)
def test_normalize_path(input_path: str, expected: str, desc: str) -> None:
    """Path normalization: {desc}."""
    assert normalize_path(input_path) == expected


# ---------------------------------------------------------------------------
# Layer 2: Auth handler tests (table-driven)
# ---------------------------------------------------------------------------


AUTH_FACTORY_CASES = [
    (None, AuthHandler, FormAuthHandler, "none config"),
    ({"transport": "http"}, AuthHandler, FormAuthHandler, "missing auth key"),
    ({"auth": {"strategy": "none"}}, AuthHandler, FormAuthHandler, "explicit none"),
    ({"auth": {"strategy": "basic"}}, BasicAuthHandler, None, "basic auth"),
    (
        {"auth": {"strategy": "form", "action": "/goform/login"}, "session": {"cookie_name": "session"}},
        FormAuthHandler,
        None,
        "form auth",
    ),
    (
        {"auth": {"strategy": "form", "action": "/goform/login"}},
        FormAuthHandler,
        None,
        "form no session",
    ),
]


@pytest.mark.parametrize("config,expected_type,not_type,desc", AUTH_FACTORY_CASES)
def test_create_auth_handler(
    config: dict[str, Any] | None,
    expected_type: type,
    not_type: type | None,
    desc: str,
) -> None:
    """Auth factory creates correct handler: {desc}."""
    handler = create_auth_handler(config)
    assert isinstance(handler, expected_type)
    if not_type is not None:
        assert not isinstance(handler, not_type)


class TestAuthHandlerNone:
    """Behavioral tests for the base AuthHandler (no auth)."""

    def test_always_authenticated(self) -> None:
        """No-auth handler always reports authenticated."""
        handler = AuthHandler()
        assert handler.is_authenticated({})

    def test_not_login_request(self) -> None:
        """No-auth handler never identifies a login request."""
        assert not AuthHandler().is_login_request("POST", "/login")

    def test_handle_login_returns_none(self) -> None:
        """No-auth handler returns None from handle_login."""
        assert AuthHandler().handle_login("POST", "/login", b"", {}) is None

    def test_set_authenticated_empty(self) -> None:
        """No-auth handler returns no extra headers."""
        assert AuthHandler().set_authenticated() == {}


class TestFormAuthHandler:
    """Behavioral tests for FormAuthHandler."""

    def test_login_request_detection(self) -> None:
        """POST to login path is detected as login request."""
        handler = FormAuthHandler("/goform/login")
        assert handler.is_login_request("POST", "/goform/login")
        assert not handler.is_login_request("GET", "/goform/login")
        assert not handler.is_login_request("POST", "/other")

    def test_unauthenticated_by_default(self) -> None:
        """New handler starts unauthenticated."""
        assert not FormAuthHandler("/goform/login").is_authenticated({})

    def test_login_sets_authenticated(self) -> None:
        """Successful login sets authenticated state."""
        handler = FormAuthHandler("/goform/login")
        handler.handle_login("POST", "/goform/login", b"user=admin", {})
        assert handler.is_authenticated({})

    def test_cookie_session_headers(self) -> None:
        """Cookie-based session sets Set-Cookie header."""
        handler = FormAuthHandler("/goform/login", cookie_name="session")
        extra = handler.set_authenticated()
        assert "Set-Cookie" in extra
        assert "session=" in extra["Set-Cookie"]

    def test_cookie_authenticates_request(self) -> None:
        """Cookie in request headers authenticates the request."""
        handler = FormAuthHandler("/goform/login", cookie_name="session")
        assert not handler.is_authenticated({})
        assert handler.is_authenticated({"cookie": "session=abc123"})

    def test_ip_session_no_cookie(self) -> None:
        """IP-based session (no cookie_name) returns no Set-Cookie."""
        assert FormAuthHandler("/goform/login").set_authenticated() == {}


class TestBasicAuthHandler:
    """Behavioral tests for BasicAuthHandler."""

    def test_authenticated_with_basic_header(self) -> None:
        """Request with Basic auth header is authenticated."""
        assert BasicAuthHandler().is_authenticated({"authorization": "Basic dXNlcjpwYXNz"})

    def test_unauthenticated_without_header(self) -> None:
        """Request without auth header is not authenticated."""
        assert not BasicAuthHandler().is_authenticated({})

    def test_wrong_scheme(self) -> None:
        """Non-Basic auth scheme is not authenticated."""
        assert not BasicAuthHandler().is_authenticated({"authorization": "Bearer token123"})


# ---------------------------------------------------------------------------
# Layer 3: HTTP server integration tests (fixture-driven)
# ---------------------------------------------------------------------------


class TestHARMockServerNoAuth:
    """Integration tests for mock server with no auth."""

    @pytest.fixture()
    def entries(self) -> list[dict[str, Any]]:
        """Load no-auth HAR entries from fixture."""
        return _load_entries("har_entries_no_auth.json")

    def test_serves_har_responses(self, entries: list[dict[str, Any]]) -> None:
        """Mock server serves recorded HAR responses."""
        with HARMockServer(entries) as server:
            resp = requests.get(f"{server.base_url}/status.html")
            assert resp.status_code == 200
            assert resp.text == "<html>DS data</html>"

    def test_multiple_pages(self, entries: list[dict[str, Any]]) -> None:
        """Mock server serves multiple pages."""
        with HARMockServer(entries) as server:
            resp1 = requests.get(f"{server.base_url}/status.html")
            resp2 = requests.get(f"{server.base_url}/info.html")
            assert resp1.status_code == 200
            assert resp2.status_code == 200
            assert "System info" in resp2.text

    def test_404_for_unknown_path(self, entries: list[dict[str, Any]]) -> None:
        """Unknown paths return 404."""
        with HARMockServer(entries) as server:
            resp = requests.get(f"{server.base_url}/unknown.html")
            assert resp.status_code == 404

    def test_base_url_format(self, entries: list[dict[str, Any]]) -> None:
        """base_url is http://127.0.0.1:<port>."""
        with HARMockServer(entries) as server:
            assert server.base_url.startswith("http://127.0.0.1:")


class TestHARMockServerFormAuth:
    """Integration tests for mock server with form auth."""

    @pytest.fixture()
    def entries(self) -> list[dict[str, Any]]:
        """Load form-auth HAR entries from fixture."""
        return _load_entries("har_entries_form_auth.json")

    def test_data_pages_require_auth(self, entries: list[dict[str, Any]]) -> None:
        """Data pages return 401 before login."""
        config = {"auth": {"strategy": "form", "action": "/goform/login"}}
        with HARMockServer(entries, modem_config=config) as server:
            resp = requests.get(f"{server.base_url}/status.html")
            assert resp.status_code == 401

    def test_login_then_data(self, entries: list[dict[str, Any]]) -> None:
        """Login followed by data page request succeeds."""
        config = {"auth": {"strategy": "form", "action": "/goform/login"}}
        with HARMockServer(entries, modem_config=config) as server:
            login_resp = requests.post(
                f"{server.base_url}/goform/login",
                data="username=admin&password=secret",
            )
            assert login_resp.status_code == 200

            data_resp = requests.get(f"{server.base_url}/status.html")
            assert data_resp.status_code == 200
            assert data_resp.text == "<html>DS data</html>"

    def test_cookie_session(self, entries: list[dict[str, Any]]) -> None:
        """Cookie-based session allows auth via cookie header."""
        config = {
            "auth": {"strategy": "form", "action": "/goform/login"},
            "session": {"cookie_name": "session"},
        }
        with HARMockServer(entries, modem_config=config) as server:
            requests.post(
                f"{server.base_url}/goform/login",
                data="username=admin&password=secret",
            )
            session = requests.Session()
            session.cookies.set("session", "mock-session-token")
            data_resp = session.get(f"{server.base_url}/status.html")
            assert data_resp.status_code == 200


class TestHARMockServerBasicAuth:
    """Integration tests for mock server with basic auth."""

    @pytest.fixture()
    def entries(self) -> list[dict[str, Any]]:
        """Load no-auth HAR entries (basic auth doesn't need login entries)."""
        return _load_entries("har_entries_no_auth.json")

    def test_unauthenticated_returns_401(self, entries: list[dict[str, Any]]) -> None:
        """Request without auth header returns 401."""
        config = {"auth": {"strategy": "basic"}}
        with HARMockServer(entries, modem_config=config) as server:
            resp = requests.get(f"{server.base_url}/status.html")
            assert resp.status_code == 401

    def test_basic_auth_succeeds(self, entries: list[dict[str, Any]]) -> None:
        """Request with Basic auth header succeeds."""
        config = {"auth": {"strategy": "basic"}}
        with HARMockServer(entries, modem_config=config) as server:
            resp = requests.get(
                f"{server.base_url}/status.html",
                auth=("admin", "password"),
            )
            assert resp.status_code == 200
