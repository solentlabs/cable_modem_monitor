"""Tests for HAR mock server — PBKDF2 auth handler and integration.

Validates the multi-round PBKDF2 challenge-response protocol: CSRF
init, salt trigger, key derivation, and login validation.

HTTP auth handler and server tests live in ``test_har_mock_server.py``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import requests
from solentlabs.cable_modem_monitor_core.test_harness.auth.form_pbkdf2 import (
    FormPbkdf2AuthHandler,
)
from solentlabs.cable_modem_monitor_core.test_harness.server import HARMockServer

from tests._helpers import load_fixture

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# csrf_source: cookie makes the firmware reject a data request whose CSRF
# header is missing or is not the session cookie's value (#227). The mock's
# session cookie is "mock-session-token".
#
# ┌───────────────────────┬───────────────────────┬───────────────┐
# │ description           │ csrf header sent      │ authenticated │
# ├───────────────────────┼───────────────────────┼───────────────┤
# │ header_missing        │ none                  │ False         │
# │ header_wrong_value    │ not the cookie value  │ False         │
# │ header_is_cookie      │ the cookie value      │ True          │
# └───────────────────────┴───────────────────────┴───────────────┘
# fmt: off
_CSRF_COOKIE_GATE_CASES = [
    # (description,         request headers,                               authenticated)
    ("header_missing",      {},                                            False),
    ("header_wrong_value",  {"x-csrf-token": "0000"},                      False),
    ("header_is_cookie",    {"x-csrf-token": "mock-session-token"},        True),
]
# fmt: on


def _load_entries(name: str) -> list[dict[str, Any]]:
    """Load HAR entries from a fixture file."""
    data = load_fixture(FIXTURES_DIR / name)
    return list(data["_entries"])


def _make_config(data: dict[str, Any]) -> Any:
    """Validate a raw modem config dict into a ModemConfig instance."""
    from solentlabs.cable_modem_monitor_core.config_loader import validate_modem_config

    defaults = {
        "manufacturer": "Solent Labs",
        "model": "T100",
        "transport": "http",
        "default_host": "192.168.100.1",
        "status": "unsupported",
        "auth": {"strategy": "none"},
    }
    return validate_modem_config({**defaults, **data})


def _derive_key(password: str, salt: str, iterations: int, key_length_bits: int) -> str:
    """Derive a key using PBKDF2-HMAC-SHA256, returned as hex."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
        dklen=key_length_bits // 8,
    )
    return dk.hex()


# ---------------------------------------------------------------------------
# Handler unit tests
# ---------------------------------------------------------------------------


class TestExtractField:
    """FormPbkdf2AuthHandler._extract_field body parsing.

    The handler accepts both JSON and form-encoded POST bodies.
    """

    # ┌────────────────────────────────────────────────┬────────────┬────────────────┬─────────────────────┐
    # │ body                                           │ field      │ expected       │ description         │
    # ├────────────────────────────────────────────────┼────────────┼────────────────┼─────────────────────┤
    # │ b'{"password": "seeksalthash"}'                │ "password" │ "seeksalthash" │ JSON body           │
    # │ b'password=seeksalthash&username=admin'        │ "password" │ "seeksalthash" │ form-encoded body   │
    # │ b'{"username": "admin"}'                       │ "password" │ ""             │ JSON missing field  │
    # │ b'username=admin'                              │ "password" │ ""             │ form missing field  │
    # │ b'\xff\xfe'                                    │ "password" │ ""             │ invalid bytes       │
    # │ b''                                            │ "password" │ ""             │ empty body          │
    # └────────────────────────────────────────────────┴────────────┴────────────────┴─────────────────────┘
    #
    # fmt: off
    EXTRACT_CASES = [
        (b'{"password": "seeksalthash"}',          "password", "seeksalthash", "JSON body"),
        (b'password=seeksalthash&username=admin',   "password", "seeksalthash", "form-encoded body"),
        (b'{"username": "admin"}',                  "password", "",             "JSON missing field"),
        (b'username=admin',                         "password", "",             "form missing field"),
        (b'\xff\xfe',                               "password", "",             "invalid bytes"),
        (b'',                                       "password", "",             "empty body"),
    ]
    # fmt: on

    @pytest.mark.parametrize(
        "body,field,expected,desc",
        EXTRACT_CASES,
        ids=[c[3] for c in EXTRACT_CASES],
    )
    def test_extract_field(
        self,
        body: bytes,
        field: str,
        expected: str,
        desc: str,
    ) -> None:
        """Extracts field from body or returns empty string."""
        result = FormPbkdf2AuthHandler._extract_field(body, field)
        assert result == expected


class TestFormPbkdf2AuthHandler:
    """Unit tests for PBKDF2 auth handler phases."""

    @pytest.fixture()
    def handler(self) -> FormPbkdf2AuthHandler:
        """Handler with double-hash and CSRF enabled."""
        return FormPbkdf2AuthHandler(
            login_endpoint="/api/v1/session/login",
            salt_trigger="seeksalthash",
            pbkdf2_iterations=1000,
            pbkdf2_key_length=128,
            double_hash=True,
            csrf_init_endpoint="/api/v1/session/language",
            csrf_header="X-CSRF-TOKEN",
            cookie_name="PHPSESSID",
        )

    @pytest.fixture()
    def handler_no_csrf(self) -> FormPbkdf2AuthHandler:
        """Handler without CSRF."""
        return FormPbkdf2AuthHandler(
            login_endpoint="/api/v1/session/login",
            salt_trigger="seeksalthash",
            pbkdf2_iterations=1000,
            pbkdf2_key_length=128,
            double_hash=False,
        )

    def test_csrf_init_is_login_request(self, handler: FormPbkdf2AuthHandler) -> None:
        """GET to CSRF init endpoint is recognized as login request."""
        assert handler.is_login_request("GET", "/api/v1/session/language")

    def test_login_post_is_login_request(self, handler: FormPbkdf2AuthHandler) -> None:
        """POST to login endpoint is recognized as login request."""
        assert handler.is_login_request("POST", "/api/v1/session/login")

    def test_data_page_not_login_request(self, handler: FormPbkdf2AuthHandler) -> None:
        """GET to data page is not a login request."""
        assert not handler.is_login_request("GET", "/api/v1/modem/")

    def test_csrf_init_returns_token(self, handler: FormPbkdf2AuthHandler) -> None:
        """CSRF init returns token in both body and header."""
        result = handler.handle_login("GET", "/api/v1/session/language", b"", {})
        assert result is not None
        assert result.status == 200
        body = json.loads(result.body)
        assert "token" in body
        csrf_headers = dict(result.headers)
        assert "X-CSRF-TOKEN" in csrf_headers

    def test_salt_trigger_returns_salts(self, handler: FormPbkdf2AuthHandler) -> None:
        """POST with salt trigger returns salt JSON."""
        body = json.dumps({"username": "admin", "password": "seeksalthash"}).encode()
        result = handler.handle_login("POST", "/api/v1/session/login", body, {})
        assert result is not None
        assert result.status == 200
        salts = json.loads(result.body)
        assert "salt" in salts
        assert "saltwebui" in salts

    def test_correct_derived_key_accepted(self, handler: FormPbkdf2AuthHandler) -> None:
        """Login with correctly derived PBKDF2 key is accepted."""
        # Derive key the same way the real auth manager would
        derived = _derive_key("pw", handler._TEST_SALT, 1000, 128)
        derived = _derive_key(derived, handler._TEST_SALT_WEBUI, 1000, 128)

        body = json.dumps({"username": "admin", "password": derived}).encode()
        result = handler.handle_login("POST", "/api/v1/session/login", body, {})
        assert result is not None
        assert result.status == 200
        assert handler._authenticated

    def test_wrong_derived_key_rejected(self, handler: FormPbkdf2AuthHandler) -> None:
        """Login with wrong derived key is rejected."""
        body = json.dumps({"username": "admin", "password": "wronghexkey"}).encode()
        result = handler.handle_login("POST", "/api/v1/session/login", body, {})
        assert result is not None
        assert result.status == 200  # 200 with error body, not 401
        body_data = json.loads(result.body)
        assert body_data.get("error") == "LoginIncorrect"
        assert not handler._authenticated

    def test_single_hash_derivation(self, handler_no_csrf: FormPbkdf2AuthHandler) -> None:
        """Single-hash derivation (no double_hash) computes correctly."""
        derived = _derive_key("pw", handler_no_csrf._TEST_SALT, 1000, 128)

        body = json.dumps({"username": "admin", "password": derived}).encode()
        result = handler_no_csrf.handle_login("POST", "/api/v1/session/login", body, {})
        assert result is not None
        assert handler_no_csrf._authenticated

    def test_data_pages_gated_before_login(self, handler: FormPbkdf2AuthHandler) -> None:
        """Data pages require auth."""
        assert not handler.is_authenticated({})

    def test_data_pages_accessible_after_login(self, handler: FormPbkdf2AuthHandler) -> None:
        """Data pages accessible after successful login."""
        derived = _derive_key("pw", handler._TEST_SALT, 1000, 128)
        derived = _derive_key(derived, handler._TEST_SALT_WEBUI, 1000, 128)
        body = json.dumps({"username": "admin", "password": derived}).encode()
        handler.handle_login("POST", "/api/v1/session/login", body, {})

        assert handler.is_authenticated({})


# ---------------------------------------------------------------------------
# Server integration tests
# ---------------------------------------------------------------------------


class TestHARMockServerPbkdf2Auth:
    """Integration tests for mock server with PBKDF2 auth.

    Exercises the real auth manager flow against the mock server:
    CSRF init → salt trigger → derive key → login → data page.
    """

    @pytest.fixture()
    def entries(self) -> list[dict[str, Any]]:
        """Load no-auth entries as data page fixtures."""
        return _load_entries("har_entries_no_auth.json")

    @pytest.fixture()
    def config(self) -> Any:
        """Modem config with PBKDF2 auth."""
        return _make_config(
            {
                "auth": {
                    "strategy": "form_pbkdf2",
                    "login_endpoint": "/api/v1/session/login",
                    "salt_trigger": "seeksalthash",
                    "pbkdf2_iterations": 1000,
                    "pbkdf2_key_length": 128,
                    "double_hash": True,
                    "csrf_init_endpoint": "/api/v1/session/language",
                    "csrf_header": "X-CSRF-TOKEN",
                    "cookie_name": "PHPSESSID",
                },
            }
        )

    def test_data_pages_require_auth(self, entries: list[dict[str, Any]], config: Any) -> None:
        """Data pages return 401 before login."""
        with HARMockServer(entries, modem_config=config) as server:
            resp = requests.get(f"{server.base_url}/status.html")
            assert resp.status_code == 401

    def test_full_pbkdf2_flow(self, entries: list[dict[str, Any]], config: Any) -> None:
        """Full PBKDF2 flow: CSRF → salt → derive → login → data."""
        with HARMockServer(entries, modem_config=config) as server:
            session = requests.Session()
            base = server.base_url

            # Step 1: CSRF init
            csrf_resp = session.get(f"{base}/api/v1/session/language")
            assert csrf_resp.status_code == 200
            csrf_token = csrf_resp.headers.get("X-CSRF-TOKEN", "")
            assert csrf_token
            session.headers["X-CSRF-TOKEN"] = csrf_token

            # Step 2: Salt trigger
            salt_resp = session.post(
                f"{base}/api/v1/session/login",
                json={"username": "admin", "password": "seeksalthash"},
            )
            assert salt_resp.status_code == 200
            salts = salt_resp.json()
            assert "salt" in salts

            # Step 3: Derive key (double-hash)
            derived = _derive_key("pw", salts["salt"], 1000, 128)
            derived = _derive_key(derived, salts["saltwebui"], 1000, 128)

            # Step 4: Login
            login_resp = session.post(
                f"{base}/api/v1/session/login",
                json={"username": "admin", "password": derived},
            )
            assert login_resp.status_code == 200

            # Step 5: Data page accessible
            data_resp = session.get(f"{base}/status.html")
            assert data_resp.status_code == 200
            assert data_resp.text == "<html>DS data</html>"

    def test_wrong_key_rejected(self, entries: list[dict[str, Any]], config: Any) -> None:
        """Login with wrong derived key does not grant access."""
        with HARMockServer(entries, modem_config=config) as server:
            session = requests.Session()
            base = server.base_url

            # Skip CSRF, go straight to login with wrong key
            login_resp = session.post(
                f"{base}/api/v1/session/login",
                json={"username": "admin", "password": "deadbeef"},
            )
            assert login_resp.status_code == 200
            body = login_resp.json()
            assert body.get("error") == "LoginIncorrect"

            # Data page still gated
            data_resp = session.get(f"{base}/status.html")
            assert data_resp.status_code == 401


class TestCsrfCookieGate:
    """csrf_source: cookie — the mock rejects data requests the real firmware would (#227)."""

    @pytest.fixture()
    def logged_in(self) -> FormPbkdf2AuthHandler:
        """Handler with csrf_source: cookie, after an accepted login."""
        handler = FormPbkdf2AuthHandler(
            login_endpoint="/api/v1/session/login",
            salt_trigger="seeksalthash",
            pbkdf2_iterations=1000,
            pbkdf2_key_length=128,
            double_hash=False,
            csrf_header="X-CSRF-TOKEN",
            cookie_name="auth",
            csrf_source="cookie",
        )
        derived = _derive_key("pw", handler._TEST_SALT, 1000, 128)
        body = json.dumps({"username": "admin", "password": derived}).encode()
        handler.handle_login("POST", "/api/v1/session/login", body, {})
        return handler

    @pytest.mark.parametrize(
        "desc,headers,expected",
        _CSRF_COOKIE_GATE_CASES,
        ids=[c[0] for c in _CSRF_COOKIE_GATE_CASES],
    )
    def test_data_request_needs_cookie_value_as_header(
        self,
        logged_in: FormPbkdf2AuthHandler,
        desc: str,
        headers: dict[str, str],
        expected: bool,
    ) -> None:
        """A logged-in session is authenticated only when the header carries the cookie value."""
        assert logged_in.is_authenticated(headers) is expected

    def test_default_source_ignores_header(self) -> None:
        """Without csrf_source: cookie the gate is the session alone, as before."""
        handler = FormPbkdf2AuthHandler(
            login_endpoint="/api/v1/session/login",
            salt_trigger="seeksalthash",
            pbkdf2_iterations=1000,
            pbkdf2_key_length=128,
            double_hash=False,
            csrf_header="X-CSRF-TOKEN",
            cookie_name="auth",
        )
        derived = _derive_key("pw", handler._TEST_SALT, 1000, 128)
        handler.handle_login("POST", "/api/v1/session/login", json.dumps({"password": derived}).encode(), {})
        assert handler.is_authenticated({}) is True

    def test_auth_manager_reads_through_the_gate(self) -> None:
        """The real auth manager logs in and then reads data past a cookie-source gate."""
        from solentlabs.cable_modem_monitor_core.auth.form_pbkdf2 import FormPbkdf2AuthManager

        config = _make_config(
            {
                "auth": {
                    "strategy": "form_pbkdf2",
                    "login_endpoint": "/api/v1/session/login",
                    "pbkdf2_iterations": 1000,
                    "pbkdf2_key_length": 128,
                    "double_hash": False,
                    "csrf_source": "cookie",
                    "csrf_header": "X-CSRF-TOKEN",
                    "cookie_name": "auth",
                },
            }
        )
        entries = _load_entries("har_entries_no_auth.json")
        with HARMockServer(entries, modem_config=config) as server:
            session = requests.Session()
            manager = FormPbkdf2AuthManager(config.auth)
            manager.configure_session(session, {})
            result = manager.authenticate(session, server.base_url, "admin", "pw")
            assert result.success is True

            assert session.get(f"{server.base_url}/status.html").status_code == 200
            # The same session without the header is what beta.6 sent.
            del session.headers["X-CSRF-TOKEN"]
            assert session.get(f"{server.base_url}/status.html").status_code == 401
