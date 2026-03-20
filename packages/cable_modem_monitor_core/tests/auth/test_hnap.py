"""Tests for HnapAuthManager — HNAP HMAC challenge-response."""

from __future__ import annotations

import hashlib
import hmac
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any
from unittest.mock import patch

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.hnap import (
    HNAP_NAMESPACE,
    HnapAuthManager,
)
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import HnapAuth


def _make_manager(hmac_algorithm: str = "md5") -> HnapAuthManager:
    """Create an HnapAuthManager with the given algorithm."""
    config = HnapAuth(strategy="hnap", hmac_algorithm=hmac_algorithm)
    return HnapAuthManager(config)


def _hmac_md5(key: str, message: str) -> str:
    """Compute HMAC-MD5 matching the auth manager's output."""
    return (
        hmac.new(
            key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.md5,
        )
        .hexdigest()
        .upper()
    )


# --- Mock HNAP Server ---


class _HNAPHandler(BaseHTTPRequestHandler):
    """Minimal HNAP mock server for auth testing."""

    challenge = "test_challenge_abc"
    public_key = "test_public_key_xyz"
    cookie = "test_uid_cookie"
    password = "password"
    login_result = "OK"

    def do_POST(self) -> None:  # noqa: N802
        """Handle HNAP POST requests."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body) if body else {}

        login = data.get("Login", {})
        action = login.get("Action", "")

        if action == "request":
            self._handle_challenge()
        elif action == "login":
            self._handle_login(login)
        else:
            self._respond(400, {"error": "unknown action"})

    def _handle_challenge(self) -> None:
        """Return challenge, public key, and cookie."""
        self._respond(
            200,
            {
                "LoginResponse": {
                    "Challenge": self.challenge,
                    "PublicKey": self.public_key,
                    "Cookie": self.cookie,
                    "LoginResult": "OK",
                },
            },
        )

    def _handle_login(self, login: dict[str, Any]) -> None:
        """Validate login credentials and return result."""
        expected_private_key = _hmac_md5(
            self.public_key + self.password,
            self.challenge,
        )
        expected_login_password = _hmac_md5(
            expected_private_key,
            self.challenge,
        )

        if login.get("LoginPassword") == expected_login_password:
            self._respond(
                200,
                {"LoginResponse": {"LoginResult": self.__class__.login_result}},
            )
        else:
            self._respond(
                200,
                {"LoginResponse": {"LoginResult": "FAILED"}},
            )

    def _respond(self, status: int, data: dict) -> None:
        """Send JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress server log output during tests."""


@pytest.fixture()
def hnap_server():
    """Start a mock HNAP server and yield its base URL."""
    _HNAPHandler.login_result = "OK"
    server = HTTPServer(("127.0.0.1", 0), _HNAPHandler)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


class TestSuccessfulLogin:
    """Test successful HNAP authentication."""

    def test_login_succeeds(self, hnap_server: str) -> None:
        """Full challenge-response login produces AuthResult with private key."""
        manager = _make_manager()
        session = requests.Session()

        result = manager.authenticate(session, hnap_server, "admin", "password")

        assert result.success is True
        assert result.error == ""
        assert result.hnap_private_key != ""

    def test_private_key_is_correct(self, hnap_server: str) -> None:
        """Derived private key matches expected HMAC computation."""
        manager = _make_manager()
        session = requests.Session()

        result = manager.authenticate(session, hnap_server, "admin", "password")

        expected = _hmac_md5(
            _HNAPHandler.public_key + "password",
            _HNAPHandler.challenge,
        )
        assert result.hnap_private_key == expected

    def test_uid_cookie_set(self, hnap_server: str) -> None:
        """Session has uid cookie after successful login."""
        manager = _make_manager()
        session = requests.Session()

        manager.authenticate(session, hnap_server, "admin", "password")

        assert session.cookies.get("uid") == _HNAPHandler.cookie


# ┌──────────────────┬──────────┬─────────────────────────────────┬───────────────────────────┐
# │ login_result     │ password │ expected_error_substring        │ description               │
# ├──────────────────┼──────────┼─────────────────────────────────┼───────────────────────────┤
# │ "OK"             │ wrong    │ incorrect username or password  │ wrong password            │
# │ "LOCKUP"         │ correct  │ LOCKUP                          │ anti-brute-force lockup   │
# │ "REBOOT"         │ correct  │ REBOOT                          │ anti-brute-force reboot   │
# └──────────────────┴──────────┴─────────────────────────────────┴───────────────────────────┘
#
# fmt: off
LOGIN_FAILURE_CASES = [
    # (login_result, password,    error_substring,               description)
    ("OK",           "wrong_pwd", "incorrect username or password", "wrong password"),
    ("LOCKUP",       "password",  "LOCKUP",                        "anti-brute-force lockup"),
    ("REBOOT",       "password",  "REBOOT",                        "anti-brute-force reboot"),
]
# fmt: on


@pytest.mark.parametrize(
    "login_result,password,error_substring,desc",
    LOGIN_FAILURE_CASES,
    ids=[c[3] for c in LOGIN_FAILURE_CASES],
)
def test_login_failure(
    hnap_server: str,
    login_result: str,
    password: str,
    error_substring: str,
    desc: str,
) -> None:
    """Verify login failure cases produce correct error messages."""
    _HNAPHandler.login_result = login_result
    manager = _make_manager()
    session = requests.Session()

    result = manager.authenticate(session, hnap_server, "admin", password)

    assert result.success is False
    assert error_substring in result.error


def test_connection_refused() -> None:
    """Connection error returns failure."""
    manager = _make_manager()
    session = requests.Session()

    result = manager.authenticate(session, "http://127.0.0.1:1", "admin", "password")

    assert result.success is False
    assert "challenge request failed" in result.error


# ┌─────────────┬──────────┬──────────────────────────┐
# │ algorithm   │ hex_len  │ description              │
# ├─────────────┼──────────┼──────────────────────────┤
# │ md5         │ 32       │ MD5 produces 32 hex      │
# │ sha256      │ 64       │ SHA256 produces 64 hex   │
# └─────────────┴──────────┴──────────────────────────┘
#
# fmt: off
HMAC_ALGORITHM_CASES = [
    # (algorithm, hex_len, description)
    ("md5",    32, "MD5 produces 32 hex chars"),
    ("sha256", 64, "SHA256 produces 64 hex chars"),
]
# fmt: on


@pytest.mark.parametrize(
    "algorithm,hex_len,desc",
    HMAC_ALGORITHM_CASES,
    ids=[c[2] for c in HMAC_ALGORITHM_CASES],
)
def test_hmac_algorithm_output(algorithm: str, hex_len: int, desc: str) -> None:
    """Verify HMAC algorithm produces correct output length."""
    manager = _make_manager(hmac_algorithm=algorithm)
    result = manager._hmac_hex("test_key", "test_message")
    assert len(result) == hex_len
    assert result == result.upper()


class TestAuthHeader:
    """Test HNAP_AUTH header computation."""

    @patch("solentlabs.cable_modem_monitor_core.auth.hnap.time")
    def test_header_format(self, mock_time: Any) -> None:
        """HNAP_AUTH header has correct format: 'HMAC_HEX TIMESTAMP'."""
        mock_time.time.return_value = 1708960420.646
        manager = _make_manager()

        header = manager._compute_auth_header("withoutloginkey", "Login")

        parts = header.split(" ")
        assert len(parts) == 2
        hmac_hex, timestamp = parts
        assert len(hmac_hex) == 32
        assert hmac_hex == hmac_hex.upper()
        assert timestamp.isdigit()

    @patch("solentlabs.cable_modem_monitor_core.auth.hnap.time")
    def test_timestamp_modulo(self, mock_time: Any) -> None:
        """Timestamp uses modulo 2_000_000_000_000."""
        mock_time.time.return_value = 2_500_000_000.123
        manager = _make_manager()

        header = manager._compute_auth_header("key", "Action")

        timestamp = int(header.split(" ")[1])
        expected = 2_500_000_000_123 % 2_000_000_000_000
        assert timestamp == expected

    @patch("solentlabs.cable_modem_monitor_core.auth.hnap.time")
    def test_hmac_includes_quoted_namespace(self, mock_time: Any) -> None:
        """HMAC message includes quoted SOAP namespace URI."""
        mock_time.time.return_value = 1.0
        manager = _make_manager()

        header = manager._compute_auth_header("test_key", "Login")

        timestamp = "1000"
        soap_uri = f'"{HNAP_NAMESPACE}Login"'
        expected_hmac = _hmac_md5("test_key", timestamp + soap_uri)
        assert header == f"{expected_hmac} {timestamp}"
