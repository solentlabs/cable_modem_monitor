"""Tests for URL token authentication during polling cycle.

These tests verify:
1. Config flow works with URL token auth
2. DataOrchestrator uses AuthHandler during get_modem_data()
3. Strict URL token validation works (cookies alone rejected)
"""

from __future__ import annotations

import ssl
from pathlib import Path
from unittest.mock import patch

import pytest

from custom_components.cable_modem_monitor.core.auth.workflow import AUTH_TYPE_TO_STRATEGY
from custom_components.cable_modem_monitor.core.data_orchestrator import DataOrchestrator
from custom_components.cable_modem_monitor.core.parser_registry import get_parser_by_name
from custom_components.cable_modem_monitor.core.setup import setup_modem
from custom_components.cable_modem_monitor.modem_config import get_auth_adapter_for_parser

from .mock_modem_server import MockModemServer

MODEMS_DIR = Path(__file__).parent.parent.parent / "modems"


def _get_sb8200_parser():
    """Get SB8200 parser class."""
    return get_parser_by_name("ARRIS SB8200")


def _build_sb8200_url_token_config():
    """Build static auth config for SB8200 with URL token auth."""
    parser = _get_sb8200_parser()
    adapter = get_auth_adapter_for_parser(parser.__name__)
    type_config = adapter.get_auth_config_for_type("url_token")

    return {
        "auth_strategy": AUTH_TYPE_TO_STRATEGY.get("url_token"),
        "auth_url_token_config": type_config,
    }


class TestConfigFlowVsPolling:
    """Compare config flow behavior vs polling behavior for URL token auth."""

    def test_config_flow_works_with_url_token(self, test_certs):
        """Config flow successfully authenticates with URL token auth.

        This test verifies that setup_modem (used by config flow) correctly
        uses URL token authentication. This should PASS.
        """
        modem_path = MODEMS_DIR / "arris" / "sb8200"
        if not modem_path.exists():
            pytest.skip("SB8200 modem directory not found")

        parser = _get_sb8200_parser()
        if not parser:
            pytest.skip("SB8200 parser not found")

        # Use HTTPS (SB8200 URL token auth typically uses HTTPS)
        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        with MockModemServer.from_modem_path(modem_path, auth_type="url_token", ssl_context=context) as server:
            auth_config = _build_sb8200_url_token_config()

            # Config flow path - uses setup_modem
            result = setup_modem(
                host=f"https://127.0.0.1:{server.port}",
                parser_class=parser,
                static_auth_config=auth_config,
                username="admin",
                password="pw",
            )

            # Config flow should work
            assert result.success, f"Config flow failed: {result.error}"
            assert result.modem_data is not None
            downstream = result.modem_data.get("downstream", [])
            assert len(downstream) > 0, "Config flow should return channel data"


class TestAuthHandlerUsage:
    """Tests verifying AuthHandler is used during data fetch."""

    def test_get_modem_data_uses_auth_handler(self, test_certs):
        """Verify get_modem_data pre-authenticates before fetching.

        When an auth strategy is configured, get_modem_data() calls _login()
        (which uses AuthHandler) BEFORE _fetch_data(). This ensures modems
        that return 401/403 without auth get properly authenticated.
        """
        modem_path = MODEMS_DIR / "arris" / "sb8200"
        if not modem_path.exists():
            pytest.skip("SB8200 modem directory not found")

        parser = _get_sb8200_parser()
        if not parser:
            pytest.skip("SB8200 parser not found")

        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        with MockModemServer.from_modem_path(modem_path, auth_type="url_token", ssl_context=context) as server:
            adapter = get_auth_adapter_for_parser(parser.__name__)
            url_token_config = adapter.get_auth_config_for_type("url_token")

            orchestrator = DataOrchestrator(
                host=f"https://127.0.0.1:{server.port}",
                username="admin",
                password="pw",
                parser=parser,
                cached_url=f"https://127.0.0.1:{server.port}",
                verify_ssl=False,
                legacy_ssl=False,
                auth_strategy="url_token_session",
                auth_url_token_config=url_token_config,
            )

            # Patch AuthHandler.authenticate to track calls
            with patch.object(
                orchestrator._auth_handler, "authenticate", wraps=orchestrator._auth_handler.authenticate
            ) as mock_auth:
                # Call get_modem_data (the public method used by coordinator)
                data = orchestrator.get_modem_data()

                # FIXED: AuthHandler.authenticate IS now called during get_modem_data
                assert mock_auth.called, (
                    "AuthHandler.authenticate should be called during get_modem_data "
                    "when auth strategy is configured"
                )

                # Verify we got actual data
                downstream = data.get("cable_modem_downstream", [])
                assert len(downstream) > 0, "Should return channel data after authentication"

    def test_login_uses_auth_handler(self, test_certs):
        """Verify _login() uses AuthHandler.

        Confirms the authentication flow goes through AuthHandler.authenticate().
        """
        modem_path = MODEMS_DIR / "arris" / "sb8200"
        if not modem_path.exists():
            pytest.skip("SB8200 modem directory not found")

        parser = _get_sb8200_parser()
        if not parser:
            pytest.skip("SB8200 parser not found")

        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        with MockModemServer.from_modem_path(modem_path, auth_type="url_token", ssl_context=context) as server:
            adapter = get_auth_adapter_for_parser(parser.__name__)
            url_token_config = adapter.get_auth_config_for_type("url_token")

            orchestrator = DataOrchestrator(
                host=f"https://127.0.0.1:{server.port}",
                username="admin",
                password="pw",
                parser=parser,
                cached_url=f"https://127.0.0.1:{server.port}",
                verify_ssl=False,
                legacy_ssl=False,
                auth_strategy="url_token_session",
                auth_url_token_config=url_token_config,
            )

            # Patch AuthHandler.authenticate to track calls
            with patch.object(
                orchestrator._auth_handler, "authenticate", wraps=orchestrator._auth_handler.authenticate
            ) as mock_auth:
                # Call _login() - this SHOULD use AuthHandler
                orchestrator._login()

                # _login() should use AuthHandler
                assert mock_auth.called, "_login() should use AuthHandler.authenticate"


class TestUrlTokenAuthRequirement:
    """Tests verifying URL token auth works correctly."""

    def test_authenticated_request_succeeds(self, test_certs):
        """Verify mock server works with correct URL token auth.

        This ensures the mock server correctly handles URL token auth
        when credentials are provided in the URL.
        """
        import base64

        import requests

        modem_path = MODEMS_DIR / "arris" / "sb8200"
        if not modem_path.exists():
            pytest.skip("SB8200 modem directory not found")

        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        with MockModemServer.from_modem_path(modem_path, auth_type="url_token", ssl_context=context) as server:
            session = requests.Session()
            session.verify = False

            # URL token auth: login_<base64(user:pass)>
            token = base64.b64encode(b"admin:pw").decode()
            resp = session.get(
                f"https://127.0.0.1:{server.port}/cmconnectionstatus.html?login_{token}",
                timeout=5,
            )

            assert resp.status_code == 200, f"Auth failed: {resp.status_code}"
            assert "Downstream Bonded Channels" in resp.text, "Should get data page after URL token auth"


class TestStrictUrlTokenAuth:
    """Tests with strict URL token validation (cookies alone don't work).

    Some firmware requires the session token in EVERY URL query string.
    Cookies alone are NOT sufficient for authentication.

    This simulates that real modem behavior more accurately than the default
    mock handler, which accepts either cookies OR URL tokens.

    The strict mock validates that the orchestrator works correctly when
    the modem requires URL tokens on every request.
    """

    def test_cookies_alone_are_rejected(self, test_certs):
        """Verify that cookies alone don't authenticate - URL token required.

        This simulates the real SB8200 behavior where you MUST include
        the session token in the URL query string, not just in cookies.
        """
        import base64

        import requests

        modem_path = MODEMS_DIR / "arris" / "sb8200"
        if not modem_path.exists():
            pytest.skip("SB8200 modem directory not found")

        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        # Use url_token:strict - requires URL token in every request, rejects cookie-only
        with MockModemServer.from_modem_path(modem_path, auth_type="url_token:strict", ssl_context=context) as server:
            session = requests.Session()
            session.verify = False

            # Step 1: Login to get session cookie
            token = base64.b64encode(b"admin:pw").decode()
            login_resp = session.get(
                f"https://127.0.0.1:{server.port}/cmconnectionstatus.html?login_{token}",
                timeout=5,
            )
            assert login_resp.status_code == 200, "Login should succeed"
            assert "sessionId" in session.cookies, "Session cookie should be set"

            # Step 2: Try to fetch page with cookie only (no URL token)
            # This should FAIL because strict mode requires URL token
            data_resp = session.get(
                f"https://127.0.0.1:{server.port}/cmswinfo.html",
                timeout=5,
            )

            # With strict validation, cookie-only requests get login page
            assert (
                "Downstream Bonded Channels" not in data_resp.text
            ), "Strict URL token auth should reject cookie-only requests"

            # Step 3: With URL token, it should work
            session_token = session.cookies.get("sessionId")
            data_resp_with_token = session.get(
                f"https://127.0.0.1:{server.port}/cmconnectionstatus.html?ct_{session_token}",
                timeout=5,
            )
            assert data_resp_with_token.status_code == 200
            assert "Downstream Bonded Channels" in data_resp_with_token.text, "With URL token, should get data page"

    def test_polling_with_strict_url_token_server(self, test_certs):
        """Test that polling works with strict URL token validation.

        With strict URL token validation (simulating real firmware that
        rejects cookie-only auth), the orchestrator should:
        1. Authenticate with URL token and get session
        2. Use the data returned directly from login
        3. Successfully parse the data

        The implementation works because login returns the data page directly.
        """
        modem_path = MODEMS_DIR / "arris" / "sb8200"
        if not modem_path.exists():
            pytest.skip("SB8200 modem directory not found")

        parser = _get_sb8200_parser()
        if not parser:
            pytest.skip("SB8200 parser not found")

        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        # Use url_token:strict - requires URL token in every request, rejects cookie-only
        with MockModemServer.from_modem_path(modem_path, auth_type="url_token:strict", ssl_context=context) as server:
            adapter = get_auth_adapter_for_parser(parser.__name__)
            url_token_config = adapter.get_auth_config_for_type("url_token")

            orchestrator = DataOrchestrator(
                host=f"https://127.0.0.1:{server.port}",
                username="admin",
                password="pw",
                parser=parser,
                cached_url=f"https://127.0.0.1:{server.port}",
                verify_ssl=False,
                legacy_ssl=False,
                auth_strategy="url_token_session",
                auth_url_token_config=url_token_config,
            )

            # This is the actual polling call
            data = orchestrator.get_modem_data()

            # Verify we got actual channel data (not login page)
            downstream = data.get("cable_modem_downstream", [])
            assert len(downstream) > 0, (
                "Polling should return channel data with strict URL token auth. "
                "Got 0 channels - likely got login page instead of data page. "
                "This indicates _fetch_data or HTMLLoader isn't using URL tokens."
            )
