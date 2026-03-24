"""Tests for FormNonceAuthManager."""

from __future__ import annotations

import requests
from solentlabs.cable_modem_monitor_core.auth.form_nonce import (
    FormNonceAuthManager,
)
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (
    FormNonceAuth,
)
from solentlabs.cable_modem_monitor_core.test_harness import HARMockServer

from .conftest import load_auth_fixture


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

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True
            assert result.response_url == "/cgi-bin/status"

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

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is False
            assert "Invalid credentials" in result.error

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
