"""Tests for FormNonceAuthManager."""

from __future__ import annotations

import base64
import urllib.parse
from unittest.mock import patch

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.form_nonce import (
    FormNonceAuthManager,
    _analyze_login_form,
    _pack_b64_credentials,
)
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (
    FormNonceAuth,
)
from solentlabs.cable_modem_monitor_core.test_harness import HARMockServer

from .conftest import load_auth_fixture, load_html_fixture


class TestFormNonceAuthManager:
    """FormNonceAuthManager generates nonce and parses text responses."""

    def test_success_prefix_response(self, session: requests.Session) -> None:
        """Parses success prefix and extracts redirect URL."""
        entries, modem_config = load_auth_fixture("har_form_nonce_success.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormNonceAuth(
                strategy="form_nonce",
                action="/cgi-bin/adv_pwd_cgi",
                nonce_field="ar_nonce",
            )
            manager = FormNonceAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "pw")
            assert result.success is True
            # response_url intentionally empty — nonce auth response body
            # is the text prefix, not page content at the redirect target
            assert result.response_url == ""

    def test_error_prefix_response(self, session: requests.Session) -> None:
        """Parses error prefix and reports failure."""
        entries, modem_config = load_auth_fixture("har_form_nonce_error.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormNonceAuth(
                strategy="form_nonce",
                action="/cgi-bin/adv_pwd_cgi",
                nonce_field="ar_nonce",
            )
            manager = FormNonceAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "pw")
            assert result.success is False
            assert "Invalid credentials" in result.error
            assert result.response is not None

    def test_nonce_length_configurable(self, session: requests.Session) -> None:
        """Nonce length is respected."""
        entries, modem_config = load_auth_fixture("har_form_nonce_ok.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormNonceAuth(
                strategy="form_nonce",
                action="/login",
                nonce_field="nonce",
                nonce_length=16,
            )
            manager = FormNonceAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "pass")
            assert result.success is True

    def test_no_prefix_in_response(self, session: requests.Session) -> None:
        """Response without known prefix still succeeds."""
        entries, modem_config = load_auth_fixture("har_form_nonce_plain.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormNonceAuth(
                strategy="form_nonce",
                action="/login",
                nonce_field="nonce",
            )
            manager = FormNonceAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "pass")
            assert result.success is True
            assert result.response_url == ""

    def test_login_post_request_exception(self, session: requests.Session) -> None:
        """Non-connectivity RequestException on login POST returns AuthResult."""
        config = FormNonceAuth(strategy="form_nonce", action="/login", nonce_field="nonce")
        manager = FormNonceAuthManager(config)
        manager.configure_session(session, {})

        with patch.object(session, "post", side_effect=requests.RequestException("redirects")):
            result = manager.authenticate(session, "http://192.168.100.1", "admin", "pw")

        assert result.success is False
        assert "Nonce login POST failed" in result.error

    def test_login_post_connection_error_propagates(self, session: requests.Session) -> None:
        """ConnectionError on login POST propagates for collector to classify."""
        config = FormNonceAuth(strategy="form_nonce", action="/login", nonce_field="nonce")
        manager = FormNonceAuthManager(config)
        manager.configure_session(session, {})

        with (
            patch.object(session, "post", side_effect=requests.ConnectionError("refused")),
            pytest.raises(requests.ConnectionError),
        ):
            manager.authenticate(session, "http://127.0.0.1:1", "admin", "pw")


class TestPackB64Credentials:
    """_pack_b64_credentials produces verified base64 output."""

    def test_simple_credentials(self) -> None:
        """Basic case without special characters."""
        result = _pack_b64_credentials("username", "admin", "password", "test")
        decoded = base64.b64decode(result).decode()
        assert decoded == "username%3Dadmin:password%3Dtest"

    def test_special_characters_in_password(self) -> None:
        """Characters like # are URI-encoded, ! is not (JS encodeURIComponent)."""
        result = _pack_b64_credentials("username", "admin", "password", "p@ss#w!rd")
        decoded = base64.b64decode(result).decode()
        # # → %23, @ → %40, ! stays as !
        assert "password%3Dp%40ss%23w!rd" in decoded

    def test_matches_har_capture(self) -> None:
        """Byte-for-byte match against Winesnob's SB6190 HAR capture."""
        result = _pack_b64_credentials("username", "admin", "password", "yWtMEh#ykl6!3J6kd")
        expected = base64.b64encode(b"username%3Dadmin:password%3DyWtMEh%23ykl6!3J6kd").decode()
        assert result == expected

    def test_roundtrip_decode(self) -> None:
        """Packed value can be decoded back to original fields."""
        result = _pack_b64_credentials("username", "admin", "password", "secret")
        decoded = base64.b64decode(result).decode()
        parts = decoded.split(":")
        assert len(parts) == 2
        assert urllib.parse.unquote(parts[0]) == "username=admin"
        assert urllib.parse.unquote(parts[1]) == "password=secret"


_ANALYZE_CASES = [
    # (id, fixture_or_empty, username_field, nonce_field, expected_encoding, expected_field)
    ("plain_named_inputs", "login_form_plain.html", "username", "ar_nonce", "plain", ""),
    ("b64_packed_hidden", "login_form_b64.html", "username", "ar_nonce", "b64_packed", "arguments"),
    ("empty_html", "", "username", "ar_nonce", "plain", ""),
    ("no_form_tag", "login_form_no_form.html", "username", "ar_nonce", "plain", ""),
    ("no_hidden_fields", "login_form_no_hidden.html", "username", "ar_nonce", "plain", ""),
    ("nonce_only_hidden", "login_form_nonce_only.html", "username", "ar_nonce", "plain", ""),
    ("populated_hidden", "login_form_populated_hidden.html", "username", "ar_nonce", "plain", ""),
    ("custom_field_names", "login_form_custom_fields.html", "loginUser", "my_nonce", "b64_packed", "creds"),
]


class TestAnalyzeLoginForm:
    """_analyze_login_form detects credential encoding from form structure."""

    @pytest.mark.parametrize(
        ("fixture", "username_field", "nonce_field", "expected_encoding", "expected_field"),
        [(f, u, n, enc, fld) for _, f, u, n, enc, fld in _ANALYZE_CASES],
        ids=[case[0] for case in _ANALYZE_CASES],
    )
    def test_encoding_detection(
        self,
        fixture: str,
        username_field: str,
        nonce_field: str,
        expected_encoding: str,
        expected_field: str,
    ) -> None:
        """Detect encoding from login form structure."""
        html = load_html_fixture(fixture) if fixture else ""
        result = _analyze_login_form(html, username_field, nonce_field)
        assert result.encoding == expected_encoding
        assert result.credential_field == expected_field


class TestB64PackedIntegration:
    """Integration tests: full auth flow via HARMockServer."""

    def test_b64_packed_login(self, session: requests.Session) -> None:
        """Auth manager uses b64 encoding when configured."""
        entries, modem_config = load_auth_fixture("har_form_nonce_b64.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormNonceAuth(
                strategy="form_nonce",
                action="/cgi-bin/adv_pwd_cgi",
                nonce_field="ar_nonce",
                cookie_name="credential",
                credential_encoding="b64_packed",
                credential_field="arguments",
            )
            manager = FormNonceAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "pw")
            assert result.success is True

    def test_plain_login_with_prefetch(self, session: requests.Session) -> None:
        """Regression: plain encoding still works when login page is pre-fetched."""
        entries, modem_config = load_auth_fixture("har_form_nonce_plain_prefetch.json")

        with HARMockServer(entries, modem_config=modem_config) as server:
            config = FormNonceAuth(
                strategy="form_nonce",
                action="/cgi-bin/adv_pwd_cgi",
                nonce_field="ar_nonce",
                cookie_name="credential",
            )
            manager = FormNonceAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "pw")
            assert result.success is True
