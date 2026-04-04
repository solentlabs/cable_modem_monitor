"""Tests for FormPbkdf2AuthManager."""

from __future__ import annotations

import hashlib
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.form_pbkdf2 import (
    FormPbkdf2AuthManager,
    _derive_key,
    _fetch_csrf_token,
)
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (
    FormPbkdf2Auth,
)
from solentlabs.cable_modem_monitor_core.test_harness import HARMockServer

from .conftest import load_auth_fixture


class TestDeriveKey:
    """PBKDF2 key derivation utility."""

    def test_basic_derivation(self) -> None:
        """Derives a hex key from password and salt."""
        result = _derive_key("password", "salt", 1000, 128)
        # 128 bits = 16 bytes = 32 hex chars
        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self) -> None:
        """Same inputs produce same output."""
        a = _derive_key("password", "salt", 1000, 128)
        b = _derive_key("password", "salt", 1000, 128)
        assert a == b

    def test_different_salt_different_key(self) -> None:
        """Different salt produces different key."""
        a = _derive_key("password", "salt1", 1000, 128)
        b = _derive_key("password", "salt2", 1000, 128)
        assert a != b

    def test_matches_hashlib(self) -> None:
        """Matches hashlib.pbkdf2_hmac directly."""
        expected = hashlib.pbkdf2_hmac("sha256", b"pass", b"salt", 1000, dklen=16).hex()
        result = _derive_key("pass", "salt", 1000, 128)
        assert result == expected


class TestFetchCsrfToken:
    """CSRF token fetch from init endpoint."""

    def test_json_body_token(self) -> None:
        """Extracts CSRF token from JSON response body."""
        entries, _ = load_auth_fixture("har_csrf_json_body.json")
        with HARMockServer(entries) as server:
            session = requests.Session()
            token = _fetch_csrf_token(
                session,
                f"{server.base_url}/api/v1/session/init_page",
                "X-CSRF-TOKEN",
                10,
            )
            assert token == "csrf_abc123"

    def test_header_token(self) -> None:
        """Extracts CSRF token from response header."""
        entries, _ = load_auth_fixture("har_csrf_header.json")
        with HARMockServer(entries) as server:
            session = requests.Session()
            token = _fetch_csrf_token(
                session,
                f"{server.base_url}/api/init",
                "X-CSRF-TOKEN",
                10,
            )
            assert token == "csrf_from_header"

    def test_unreachable_endpoint_propagates(self) -> None:
        """ConnectionError propagates for collector to classify as CONNECTIVITY."""
        session = requests.Session()
        with (
            patch.object(session, "get", side_effect=requests.ConnectionError("refused")),
            pytest.raises(requests.ConnectionError),
        ):
            _fetch_csrf_token(
                session,
                "http://127.0.0.1:1/unreachable",
                "X-CSRF-TOKEN",
                1,
            )

    def test_non_json_no_header(self) -> None:
        """Returns empty string when no token found."""
        entries, _ = load_auth_fixture("har_csrf_no_token.json")
        with HARMockServer(entries) as server:
            session = requests.Session()
            token = _fetch_csrf_token(
                session,
                f"{server.base_url}/api/init",
                "X-CSRF-TOKEN",
                10,
            )
            assert token == ""


class TestFormPbkdf2AuthManager:
    """FormPbkdf2AuthManager multi-round-trip auth.

    PBKDF2 auth makes two POSTs to the same endpoint (salt request,
    then login). The mock server returns the same response for both.
    Use unittest.mock for tests that need different responses per call.
    """

    def _make_config(self, **overrides: Any) -> FormPbkdf2Auth:
        """Build a FormPbkdf2Auth config with defaults."""
        defaults: dict[str, Any] = {
            "strategy": "form_pbkdf2",
            "login_endpoint": "/api/v1/session/login",
            "pbkdf2_iterations": 1000,
            "pbkdf2_key_length": 128,
        }
        defaults.update(overrides)
        return FormPbkdf2Auth.model_validate(defaults)

    def test_successful_login(self, session: requests.Session) -> None:
        """Full PBKDF2 login flow succeeds."""
        config = self._make_config(double_hash=False)
        manager = FormPbkdf2AuthManager(config)
        manager.configure_session(session, {})

        with patch.object(session, "post") as mock_post:
            salt_resp = MagicMock()
            salt_resp.json.return_value = {"salt": "s", "saltwebui": "sw"}
            login_resp = MagicMock()
            login_resp.status_code = 200
            login_resp.json.return_value = {"error": False}
            mock_post.side_effect = [salt_resp, login_resp]

            result = manager.authenticate(session, "http://192.168.100.1", "admin", "password")
            assert result.success is True
            assert mock_post.call_count == 2

    def test_double_hash(self, session: requests.Session) -> None:
        """Double hash mode derives key twice."""
        config = self._make_config(double_hash=True)
        manager = FormPbkdf2AuthManager(config)
        manager.configure_session(session, {})

        with patch.object(session, "post") as mock_post:
            salt_resp = MagicMock()
            salt_resp.json.return_value = {
                "salt": "salt1",
                "saltwebui": "salt2",
            }
            login_resp = MagicMock()
            login_resp.status_code = 200
            login_resp.json.return_value = {"error": False}
            mock_post.side_effect = [salt_resp, login_resp]

            result = manager.authenticate(session, "http://192.168.100.1", "admin", "password")
            assert result.success is True

    def test_with_csrf_endpoint(self, session: requests.Session) -> None:
        """CSRF token is fetched and set on session headers."""
        entries, _ = load_auth_fixture("har_csrf_json_body.json")

        with HARMockServer(entries) as server:
            config = self._make_config(
                csrf_init_endpoint="/api/v1/session/init_page",
                csrf_header="X-CSRF-TOKEN",
            )
            manager = FormPbkdf2AuthManager(config)
            manager.configure_session(session, {})

            with patch.object(session, "post") as mock_post:
                salt_resp = MagicMock()
                salt_resp.json.return_value = {"salt": "s"}
                login_resp = MagicMock()
                login_resp.status_code = 200
                login_resp.json.return_value = {"error": False}
                mock_post.side_effect = [salt_resp, login_resp]

                result = manager.authenticate(session, server.base_url, "admin", "password")
                assert result.success is True
                assert session.headers.get("X-CSRF-TOKEN") == "csrf_abc123"

    def test_salt_request_connection_error_propagates(self, session: requests.Session) -> None:
        """ConnectionError on salt request propagates for collector."""
        config = self._make_config()
        manager = FormPbkdf2AuthManager(config)
        manager.configure_session(session, {})

        with (
            patch.object(session, "post", side_effect=requests.ConnectionError("refused")),
            pytest.raises(requests.ConnectionError),
        ):
            manager.authenticate(session, "http://127.0.0.1:1", "admin", "password")

    def test_salt_response_not_json(self, session: requests.Session) -> None:
        """Reports error when salt response is not JSON."""
        config = self._make_config()
        manager = FormPbkdf2AuthManager(config)
        manager.configure_session(session, {})

        with patch.object(session, "post") as mock_post:
            resp = MagicMock()
            resp.json.side_effect = ValueError("not json")
            mock_post.return_value = resp

            result = manager.authenticate(session, "http://192.168.100.1", "admin", "password")
            assert result.success is False
            assert "json" in result.error.lower()

    def test_no_salt_in_response(self, session: requests.Session) -> None:
        """Reports error when response has no salt field."""
        config = self._make_config()
        manager = FormPbkdf2AuthManager(config)
        manager.configure_session(session, {})

        with patch.object(session, "post") as mock_post:
            resp = MagicMock()
            resp.json.return_value = {"no_salt": True}
            mock_post.return_value = resp

            result = manager.authenticate(session, "http://192.168.100.1", "admin", "password")
            assert result.success is False
            assert "salt" in result.error.lower()

    # ┌────────────────────┬─────────────────────────────────┐
    # │ json_value         │ description                     │
    # ├────────────────────┼─────────────────────────────────┤
    # │ "not a dict"       │ string response                 │
    # │ [1, 2, 3]          │ list response                   │
    # │ 42                 │ integer response                │
    # └────────────────────┴─────────────────────────────────┘
    #
    # fmt: off
    SALT_NOT_DICT_CASES = [
        # (json_value,    description)
        ("not a dict",    "string response"),
        ([1, 2, 3],       "list response"),
        (42,              "integer response"),
    ]
    # fmt: on

    @pytest.mark.parametrize(
        "json_value,desc",
        SALT_NOT_DICT_CASES,
        ids=[c[1] for c in SALT_NOT_DICT_CASES],
    )
    def test_salt_response_not_dict(
        self,
        session: requests.Session,
        json_value: object,
        desc: str,
    ) -> None:
        """Reports error when salt response JSON is not a dict."""
        config = self._make_config()
        manager = FormPbkdf2AuthManager(config)
        manager.configure_session(session, {})

        with patch.object(session, "post") as mock_post:
            resp = MagicMock()
            resp.json.return_value = json_value
            mock_post.return_value = resp

            result = manager.authenticate(session, "http://192.168.100.1", "admin", "password")
            assert result.success is False
            assert "json object" in result.error.lower() or "salt" in result.error.lower()

    # ┌────────────────────┬─────────────────────────────────┐
    # │ json_value         │ description                     │
    # ├────────────────────┼─────────────────────────────────┤
    # │ "ok"               │ string response                 │
    # │ ["error"]          │ list response                   │
    # │ 42                 │ integer response                │
    # └────────────────────┴─────────────────────────────────┘
    #
    # fmt: off
    LOGIN_NOT_DICT_CASES = [
        # (json_value,  description)
        ("ok",          "string response"),
        (["error"],     "list response"),
        (42,            "integer response"),
    ]
    # fmt: on

    @pytest.mark.parametrize(
        "json_value,desc",
        LOGIN_NOT_DICT_CASES,
        ids=[c[1] for c in LOGIN_NOT_DICT_CASES],
    )
    def test_login_response_not_dict(
        self,
        session: requests.Session,
        json_value: object,
        desc: str,
    ) -> None:
        """Does not crash when login response JSON is not a dict.

        Non-dict login JSON has no ``error`` field to check, so the
        code should fall through to the HTTP status code check.
        With a 200 status, that means success.
        """
        config = self._make_config(double_hash=False)
        manager = FormPbkdf2AuthManager(config)
        manager.configure_session(session, {})

        with patch.object(session, "post") as mock_post:
            salt_resp = MagicMock()
            salt_resp.json.return_value = {"salt": "s"}
            login_resp = MagicMock()
            login_resp.status_code = 200
            login_resp.json.return_value = json_value
            mock_post.side_effect = [salt_resp, login_resp]

            result = manager.authenticate(session, "http://192.168.100.1", "admin", "password")
            assert result.success is True

    def test_login_401_failure(self, session: requests.Session) -> None:
        """Reports error when login returns 401."""
        config = self._make_config(double_hash=False)
        manager = FormPbkdf2AuthManager(config)
        manager.configure_session(session, {})

        with patch.object(session, "post") as mock_post:
            salt_resp = MagicMock()
            salt_resp.json.return_value = {"salt": "s", "saltwebui": "sw"}
            login_resp = MagicMock()
            login_resp.status_code = 401
            login_resp.json.side_effect = ValueError("not json")
            mock_post.side_effect = [salt_resp, login_resp]

            result = manager.authenticate(session, "http://192.168.100.1", "admin", "password")
            assert result.success is False
            assert "401" in result.error

    def test_login_error_in_json(self, session: requests.Session) -> None:
        """Reports error when login JSON has error flag."""
        config = self._make_config(double_hash=False)
        manager = FormPbkdf2AuthManager(config)
        manager.configure_session(session, {})

        with patch.object(session, "post") as mock_post:
            salt_resp = MagicMock()
            salt_resp.json.return_value = {"salt": "s"}
            login_resp = MagicMock()
            login_resp.status_code = 200
            login_resp.json.return_value = {
                "error": True,
                "message": "invalid password",
            }
            mock_post.side_effect = [salt_resp, login_resp]

            result = manager.authenticate(session, "http://192.168.100.1", "admin", "password")
            assert result.success is False
            assert "invalid password" in result.error

    def test_login_post_connection_error_propagates(self, session: requests.Session) -> None:
        """ConnectionError on login POST propagates for collector."""
        config = self._make_config(double_hash=False)
        manager = FormPbkdf2AuthManager(config)
        manager.configure_session(session, {})

        with (
            patch.object(session, "post") as mock_post,
            pytest.raises(requests.ConnectionError),
        ):
            salt_resp = MagicMock()
            salt_resp.json.return_value = {"salt": "s"}
            mock_post.side_effect = [
                salt_resp,
                requests.ConnectionError("connection lost"),
            ]

            manager.authenticate(session, "http://192.168.100.1", "admin", "password")
