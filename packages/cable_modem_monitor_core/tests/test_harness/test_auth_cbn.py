"""Tests for FormCbnAuthHandler — CBN AES-256-CBC mock handler.

Covers the multi-phase login flow (GET login page + POST setter with
fun=N dispatch), token rotation, logout/restart body dispatch,
round-trip encryption verification, and parent class delegation.
"""

from __future__ import annotations

import base64
import hashlib
import re
from typing import Any

from solentlabs.cable_modem_monitor_core.test_harness.auth.cbn import (
    FormCbnAuthHandler,
)


def _make_handler(
    *,
    login_page_path: str = "/common_page/login.html",
    setter_endpoint: str = "/xml/setter.xml",
    getter_endpoint: str = "/xml/getter.xml",
    session_cookie_name: str = "sessionToken",
    login_fun: int = 15,
    logout_fun: int | None = 16,
    restart_fun: int | None = 8,
    har_entries: list[dict[str, Any]] | None = None,
) -> FormCbnAuthHandler:
    """Build a handler with deterministic test parameters."""
    return FormCbnAuthHandler(
        login_page_path=login_page_path,
        setter_endpoint=setter_endpoint,
        getter_endpoint=getter_endpoint,
        session_cookie_name=session_cookie_name,
        login_fun=login_fun,
        logout_fun=logout_fun,
        restart_fun=restart_fun,
        har_entries=har_entries,
    )


def _login_body(fun: int = 15, token: str = "tok") -> bytes:
    """Build a URL-encoded setter POST body."""
    return f"token={token}&fun={fun}&Username=NULL&Password=enc".encode()


# ------------------------------------------------------------------
# Tests — is_login_request (multi-phase detection)
# ------------------------------------------------------------------


class TestIsLoginRequest:
    """CBN login detection — GET login page + POST setter endpoint."""

    def test_get_login_page_is_login(self) -> None:
        """GET to login page path is a login request."""
        handler = _make_handler()
        assert handler.is_login_request("GET", "/common_page/login.html") is True

    def test_post_setter_is_login(self) -> None:
        """POST to setter endpoint is a login request (for body dispatch)."""
        handler = _make_handler()
        assert handler.is_login_request("POST", "/xml/setter.xml") is True

    def test_get_other_path_not_login(self) -> None:
        """GET to a non-login path is not a login request."""
        handler = _make_handler()
        assert handler.is_login_request("GET", "/xml/getter.xml") is False

    def test_post_getter_not_login(self) -> None:
        """POST to getter endpoint is not a login request."""
        handler = _make_handler()
        assert handler.is_login_request("POST", "/xml/getter.xml") is False

    def test_post_other_path_not_login(self) -> None:
        """POST to an unrelated path is not a login request."""
        handler = _make_handler()
        assert handler.is_login_request("POST", "/other") is False


# ------------------------------------------------------------------
# Tests — handle_login GET (login page with sessionToken cookie)
# ------------------------------------------------------------------


class TestHandleLoginPage:
    """GET login page returns HTML with sessionToken cookie."""

    def test_login_page_returns_200(self) -> None:
        """GET to login page returns 200."""
        handler = _make_handler()
        response = handler.handle_login("GET", "/common_page/login.html", b"", {})
        assert response is not None
        assert response.status == 200

    def test_login_page_returns_html(self) -> None:
        """Login page response has text/html content type."""
        handler = _make_handler()
        response = handler.handle_login("GET", "/common_page/login.html", b"", {})
        assert response is not None
        assert any(h[0] == "Content-Type" and "text/html" in h[1] for h in response.headers)

    def test_login_page_sets_session_token_cookie(self) -> None:
        """Login page response sets sessionToken cookie."""
        handler = _make_handler()
        response = handler.handle_login("GET", "/common_page/login.html", b"", {})
        assert response is not None
        cookie_headers = [h for h in response.headers if h[0] == "Set-Cookie"]
        assert len(cookie_headers) == 1
        assert "sessionToken=" in cookie_headers[0][1]

    def test_login_page_token_is_initial(self) -> None:
        """Login page sets the initial deterministic token."""
        handler = _make_handler()
        response = handler.handle_login("GET", "/common_page/login.html", b"", {})
        assert response is not None
        cookie_headers = [h for h in response.headers if h[0] == "Set-Cookie"]
        assert FormCbnAuthHandler._INITIAL_SESSION_TOKEN in cookie_headers[0][1]


# ------------------------------------------------------------------
# Tests — handle_login POST (fun=login_fun → success with SID)
# ------------------------------------------------------------------


class TestHandleLoginPost:
    """POST setter with fun=15 returns success response with SID."""

    def test_login_post_sets_authenticated(self) -> None:
        """Successful login marks handler as authenticated."""
        handler = _make_handler()
        handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=15), {})
        assert handler.is_authenticated({}) is True

    def test_login_post_returns_200(self) -> None:
        """Login POST returns HTTP 200."""
        handler = _make_handler()
        response = handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=15), {})
        assert response is not None
        assert response.status == 200

    def test_login_post_body_contains_successful(self) -> None:
        """Response body contains 'successful' (case-insensitive match by auth manager)."""
        handler = _make_handler()
        response = handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=15), {})
        assert response is not None
        assert "successful" in response.body.lower()

    def test_login_post_body_contains_sid(self) -> None:
        """Response body contains SID=<number> for extraction."""
        handler = _make_handler()
        response = handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=15), {})
        assert response is not None
        assert re.search(r"SID=\d+", response.body) is not None

    def test_login_post_rotates_session_token(self) -> None:
        """Login response sets a new (rotated) sessionToken cookie."""
        handler = _make_handler()
        response = handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=15), {})
        assert response is not None
        cookie_headers = [h for h in response.headers if h[0] == "Set-Cookie"]
        assert len(cookie_headers) == 1
        # Rotated token differs from initial
        assert FormCbnAuthHandler._INITIAL_SESSION_TOKEN not in cookie_headers[0][1]
        assert "sessionToken=" in cookie_headers[0][1]


# ------------------------------------------------------------------
# Tests — handle_login POST (fun=logout → clear session)
# ------------------------------------------------------------------


class TestHandleLogout:
    """POST setter with fun=16 clears session."""

    def test_logout_clears_authenticated(self) -> None:
        """Logout clears the authenticated state."""
        handler = _make_handler()
        handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=15), {})
        assert handler.is_authenticated({}) is True

        response = handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=16), {})
        assert response is not None
        assert handler.is_authenticated({}) is False

    def test_logout_returns_200(self) -> None:
        """Logout returns HTTP 200."""
        handler = _make_handler()
        response = handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=16), {})
        assert response is not None
        assert response.status == 200

    def test_no_logout_when_not_configured(self) -> None:
        """Without logout_fun, fun=16 falls through (returns None)."""
        handler = _make_handler(logout_fun=None)
        response = handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=16), {})
        assert response is None


# ------------------------------------------------------------------
# Tests — handle_login POST (fun=restart → clear session)
# ------------------------------------------------------------------


class TestHandleRestart:
    """POST setter with fun=8 clears session."""

    def test_restart_clears_authenticated(self) -> None:
        """Restart clears the authenticated state."""
        handler = _make_handler()
        handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=15), {})
        assert handler.is_authenticated({}) is True

        response = handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=8), {})
        assert response is not None
        assert handler.is_authenticated({}) is False

    def test_restart_returns_200(self) -> None:
        """Restart returns HTTP 200."""
        handler = _make_handler()
        response = handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=8), {})
        assert response is not None
        assert response.status == 200

    def test_no_restart_when_not_configured(self) -> None:
        """Without restart_fun, fun=8 falls through (returns None)."""
        handler = _make_handler(restart_fun=None)
        response = handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=8), {})
        assert response is None


# ------------------------------------------------------------------
# Tests — body dispatch (fun parameter routing)
# ------------------------------------------------------------------


class TestBodyDispatch:
    """Setter POSTs dispatch by fun parameter in body."""

    def test_unknown_fun_returns_none(self) -> None:
        """Unrecognized fun value falls through."""
        handler = _make_handler()
        response = handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=99), {})
        assert response is None

    def test_no_fun_parameter_returns_none(self) -> None:
        """Missing fun parameter falls through."""
        handler = _make_handler()
        response = handler.handle_login("POST", "/xml/setter.xml", b"token=abc", {})
        assert response is None

    def test_empty_body_returns_none(self) -> None:
        """Empty body falls through."""
        handler = _make_handler()
        response = handler.handle_login("POST", "/xml/setter.xml", b"", {})
        assert response is None


# ------------------------------------------------------------------
# Tests — token rotation (deterministic sequence)
# ------------------------------------------------------------------


class TestTokenRotation:
    """Session tokens rotate deterministically on login responses."""

    def test_initial_token_is_deterministic(self) -> None:
        """Initial token matches the class constant."""
        handler = _make_handler()
        assert handler.current_token == FormCbnAuthHandler._INITIAL_SESSION_TOKEN

    def test_tokens_rotate_on_login(self) -> None:
        """Each login POST issues a different token."""
        handler = _make_handler()
        handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=15), {})
        token_1 = handler.current_token
        handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=15), {})
        token_2 = handler.current_token
        assert token_1 != token_2
        assert token_1 != FormCbnAuthHandler._INITIAL_SESSION_TOKEN

    def test_token_counter_increments(self) -> None:
        """Token counter increments with each login."""
        handler = _make_handler()
        assert handler.current_token == FormCbnAuthHandler._INITIAL_SESSION_TOKEN
        handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=15), {})
        assert "0001" in handler.current_token
        handler.handle_login("POST", "/xml/setter.xml", _login_body(fun=15), {})
        assert "0002" in handler.current_token


# ------------------------------------------------------------------
# Tests — round-trip encryption (compal_encrypt → manual decrypt)
# ------------------------------------------------------------------


class TestRoundTripEncryption:
    """Verify compal_encrypt output can be decrypted with the same token."""

    def test_encrypt_decrypt_round_trip(self) -> None:
        """Encrypt with compal_encrypt, decrypt manually, verify match."""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.padding import PKCS7
        from solentlabs.cable_modem_monitor_core.protocol.cbn import compal_encrypt

        token = FormCbnAuthHandler._INITIAL_SESSION_TOKEN
        password = FormCbnAuthHandler._TEST_PASSWORD

        # Encrypt using the same function the real auth manager uses
        encrypted = compal_encrypt(password, token)

        # Decrypt manually: base64 decode → strip leading ":" → hex decode → AES-CBC
        decoded = base64.b64decode(encrypted).decode("utf-8")
        assert decoded.startswith(":")
        ciphertext = bytes.fromhex(decoded[1:])

        token_bytes = token.encode("utf-8")
        key = hashlib.sha256(token_bytes).digest()
        iv = hashlib.md5(token_bytes).digest()  # noqa: S324

        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder = PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()

        assert plaintext.decode("utf-8") == password


# ------------------------------------------------------------------
# Tests — non-login passthrough
# ------------------------------------------------------------------


class TestNonLoginPassthrough:
    """handle_login returns None for non-setter, non-login-page requests."""

    def test_get_other_path_returns_none(self) -> None:
        """GET to non-login path returns None."""
        handler = _make_handler()
        result = handler.handle_login("GET", "/xml/getter.xml", b"", {})
        assert result is None

    def test_post_getter_returns_none(self) -> None:
        """POST to getter endpoint returns None."""
        handler = _make_handler()
        result = handler.handle_login("POST", "/xml/getter.xml", _login_body(fun=10), {})
        assert result is None


# ------------------------------------------------------------------
# Helper — build HAR entries for route override tests
# ------------------------------------------------------------------


def _har_getter_entry(fun: int, xml_body: str) -> dict[str, Any]:
    """Build a minimal HAR entry for a getter POST with fun=N."""
    return {
        "request": {
            "method": "POST",
            "url": "http://192.168.0.1/xml/getter.xml",
            "postData": {"text": f"token=abc&fun={fun}"},
        },
        "response": {
            "status": 200,
            "headers": [{"name": "Content-Type", "value": "text/xml"}],
            "content": {"text": xml_body},
        },
    }


def _getter_body(fun: int = 10, token: str = "tok") -> bytes:
    """Build a URL-encoded getter POST body."""
    return f"token={token}&fun={fun}".encode()


# ------------------------------------------------------------------
# Tests — get_route_override (getter dispatch by fun)
# ------------------------------------------------------------------


class TestGetRouteOverride:
    """Getter POSTs dispatch by fun from HAR-built lookup."""

    def test_getter_returns_xml_for_known_fun(self) -> None:
        """POST getter with known fun returns the HAR response body."""
        entries = [_har_getter_entry(10, "<downstream_table/>")]
        handler = _make_handler(har_entries=entries)
        response = handler.get_route_override(
            "POST",
            "/xml/getter.xml",
            _getter_body(fun=10),
            {},
        )
        assert response is not None
        assert response.status == 200
        assert "<downstream_table/>" in response.body

    def test_getter_returns_none_for_unknown_fun(self) -> None:
        """POST getter with unrecognized fun returns None."""
        entries = [_har_getter_entry(10, "<data/>")]
        handler = _make_handler(har_entries=entries)
        response = handler.get_route_override(
            "POST",
            "/xml/getter.xml",
            _getter_body(fun=99),
            {},
        )
        assert response is None

    def test_getter_returns_none_for_non_getter_path(self) -> None:
        """POST to non-getter path returns None."""
        entries = [_har_getter_entry(10, "<data/>")]
        handler = _make_handler(har_entries=entries)
        response = handler.get_route_override(
            "POST",
            "/other",
            _getter_body(fun=10),
            {},
        )
        assert response is None

    def test_getter_returns_none_for_get_method(self) -> None:
        """GET to getter endpoint returns None."""
        entries = [_har_getter_entry(10, "<data/>")]
        handler = _make_handler(har_entries=entries)
        response = handler.get_route_override(
            "GET",
            "/xml/getter.xml",
            b"",
            {},
        )
        assert response is None

    def test_getter_rotates_token(self) -> None:
        """Each getter response includes a rotated session token."""
        entries = [_har_getter_entry(10, "<data/>")]
        handler = _make_handler(har_entries=entries)
        r1 = handler.get_route_override(
            "POST",
            "/xml/getter.xml",
            _getter_body(fun=10),
            {},
        )
        r2 = handler.get_route_override(
            "POST",
            "/xml/getter.xml",
            _getter_body(fun=10),
            {},
        )
        assert r1 is not None and r2 is not None
        cookies_1 = [h for h in r1.headers if h[0] == "Set-Cookie"]
        cookies_2 = [h for h in r2.headers if h[0] == "Set-Cookie"]
        assert len(cookies_1) == 1
        assert len(cookies_2) == 1
        assert cookies_1[0][1] != cookies_2[0][1]

    def test_multiple_fun_values(self) -> None:
        """Handler serves different responses for different fun values."""
        entries = [
            _har_getter_entry(10, "<downstream_table/>"),
            _har_getter_entry(11, "<upstream_table/>"),
        ]
        handler = _make_handler(har_entries=entries)
        r10 = handler.get_route_override(
            "POST",
            "/xml/getter.xml",
            _getter_body(fun=10),
            {},
        )
        r11 = handler.get_route_override(
            "POST",
            "/xml/getter.xml",
            _getter_body(fun=11),
            {},
        )
        assert r10 is not None and r11 is not None
        assert "<downstream_table/>" in r10.body
        assert "<upstream_table/>" in r11.body

    def test_empty_har_entries(self) -> None:
        """No HAR entries means no getter responses available."""
        handler = _make_handler(har_entries=[])
        response = handler.get_route_override(
            "POST",
            "/xml/getter.xml",
            _getter_body(fun=10),
            {},
        )
        assert response is None

    def test_no_body_returns_none(self) -> None:
        """Missing fun in body returns None."""
        entries = [_har_getter_entry(10, "<data/>")]
        handler = _make_handler(har_entries=entries)
        response = handler.get_route_override(
            "POST",
            "/xml/getter.xml",
            b"token=abc",
            {},
        )
        assert response is None

    def test_duplicate_fun_keeps_last_200(self) -> None:
        """Duplicate fun entries: last 200-status response wins."""
        entries = [
            _har_getter_entry(10, "<first/>"),
            _har_getter_entry(10, "<second/>"),
        ]
        handler = _make_handler(har_entries=entries)
        response = handler.get_route_override(
            "POST",
            "/xml/getter.xml",
            _getter_body(fun=10),
            {},
        )
        assert response is not None
        assert "<second/>" in response.body
