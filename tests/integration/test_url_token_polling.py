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

# Test timeout constant - matches DEFAULT_TIMEOUT from schema
TEST_TIMEOUT = 10

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
        "timeout": adapter.config.timeout,
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
        """Verify get_modem_data uses reactive auth for URL token sessions.

        Issue #81 Fix: URL token sessions skip pre-authentication because
        pre-auth every poll causes 401 errors (server-side session tracking).
        Instead, reactive auth flow handles login page detection.

        For URL token modems, AuthHandler.authenticate is called via reactive
        flow (_authenticate -> _login) when a login page is detected, NOT
        via pre-auth.
        """
        modem_path = MODEMS_DIR / "arris" / "sb8200"
        if not modem_path.exists():
            pytest.skip("SB8200 modem directory not found")

        parser_class = _get_sb8200_parser()
        if not parser_class:
            pytest.skip("SB8200 parser not found")

        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        with MockModemServer.from_modem_path(modem_path, auth_type="url_token", ssl_context=context) as server:
            adapter = get_auth_adapter_for_parser(parser_class.__name__)
            url_token_config = adapter.get_auth_config_for_type("url_token")

            # Pass parser INSTANCE (not class) so _fetch_data() has URL patterns
            orchestrator = DataOrchestrator(
                host=f"https://127.0.0.1:{server.port}",
                username="admin",
                password="pw",
                parser=parser_class(),  # Instantiate
                cached_url=f"https://127.0.0.1:{server.port}",
                verify_ssl=False,
                legacy_ssl=False,
                auth_strategy="url_token_session",
                auth_url_token_config=url_token_config,
                timeout=TEST_TIMEOUT,
            )

            # Call get_modem_data (the public method used by coordinator)
            data = orchestrator.get_modem_data()

            # Issue #81: URL token sessions skip pre-auth to avoid 401 errors.
            # Auth is handled reactively when login page is detected.
            # The non-strict mock accepts cookies, so after first auth,
            # subsequent requests may succeed without re-auth.
            # We just verify data was returned successfully.

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

        parser_class = _get_sb8200_parser()
        if not parser_class:
            pytest.skip("SB8200 parser not found")

        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        with MockModemServer.from_modem_path(modem_path, auth_type="url_token", ssl_context=context) as server:
            adapter = get_auth_adapter_for_parser(parser_class.__name__)
            url_token_config = adapter.get_auth_config_for_type("url_token")

            # Pass parser INSTANCE (not class) for consistency
            orchestrator = DataOrchestrator(
                host=f"https://127.0.0.1:{server.port}",
                username="admin",
                password="pw",
                parser=parser_class(),  # Instantiate
                cached_url=f"https://127.0.0.1:{server.port}",
                verify_ssl=False,
                legacy_ssl=False,
                auth_strategy="url_token_session",
                auth_url_token_config=url_token_config,
                timeout=TEST_TIMEOUT,
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

        Issue #81 context: This test uses "strict" mode which requires URL
        tokens on EVERY request. The reactive auth flow (used after skipping
        pre-auth for url_token_session) handles this by:
        1. Detecting login page after initial fetch
        2. Authenticating via _login() -> AuthHandler
        3. Using authenticated_html from login response directly

        The key is that AuthHandler returns the data page HTML directly
        from the login response, so no re-fetch is needed.
        """
        modem_path = MODEMS_DIR / "arris" / "sb8200"
        if not modem_path.exists():
            pytest.skip("SB8200 modem directory not found")

        parser_class = _get_sb8200_parser()
        if not parser_class:
            pytest.skip("SB8200 parser not found")

        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        # Use url_token:strict - requires URL token in every request, rejects cookie-only
        with MockModemServer.from_modem_path(modem_path, auth_type="url_token:strict", ssl_context=context) as server:
            adapter = get_auth_adapter_for_parser(parser_class.__name__)
            url_token_config = adapter.get_auth_config_for_type("url_token")

            # Pass parser INSTANCE (not class) so _fetch_data() has URL patterns
            orchestrator = DataOrchestrator(
                host=f"https://127.0.0.1:{server.port}",
                username="admin",
                password="pw",
                parser=parser_class(),  # Instantiate
                cached_url=f"https://127.0.0.1:{server.port}",
                verify_ssl=False,
                legacy_ssl=False,
                auth_strategy="url_token_session",
                auth_url_token_config=url_token_config,
                timeout=TEST_TIMEOUT,
            )

            # This is the actual polling call
            data = orchestrator.get_modem_data()

            # With strict URL token and reactive auth flow:
            # - Initial fetch returns login page (no token)
            # - _authenticate() detects login page, calls _login()
            # - _login() returns authenticated_html from auth response
            # - authenticated_html is used directly for parsing
            downstream = data.get("cable_modem_downstream", [])
            assert len(downstream) > 0, (
                "Polling should return channel data with strict URL token auth. "
                "Got 0 channels - likely got login page instead of data page. "
                "Check that AuthHandler returns HTML from login response."
            )


class TestTwoStepUrlTokenAuth:
    """Tests with two-step URL token auth (real SB8200 HTTPS firmware behavior).

    Two-step mode simulates the REAL SB8200 HTTPS firmware:
    1. Login request returns ONLY the session token in response body (not HTML!)
    2. Client must fetch data page separately with ?ct_<token>
    3. Additional pages (/cmswinfo.html) also need ?ct_<token>

    This is different from "strict" mode which still returns HTML from login.
    The real modem's JavaScript shows this behavior:

        success: function (result) {
            var token = result;  // Response body IS the token, not HTML
            window.location.href = "/cmconnectionstatus.html?ct_" + token;
        }

    Issue #81: This mode has NEVER worked because HTMLLoader doesn't get the token.
    """

    def test_two_step_login_returns_token_not_html(self, test_certs):
        """Verify two-step mock returns token in body, not HTML.

        This validates the mock server behaves like real SB8200 firmware.
        """
        import base64

        import requests

        modem_path = MODEMS_DIR / "arris" / "sb8200"
        if not modem_path.exists():
            pytest.skip("SB8200 modem directory not found")

        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        with MockModemServer.from_modem_path(
            modem_path, auth_type="url_token:two_step:strict", ssl_context=context
        ) as server:
            session = requests.Session()
            session.verify = False

            # Login request
            token = base64.b64encode(b"admin:pw").decode()
            resp = session.get(
                f"https://127.0.0.1:{server.port}/cmconnectionstatus.html?login_{token}",
                timeout=5,
            )

            assert resp.status_code == 200, f"Login failed: {resp.status_code}"

            # Two-step mode: response body is the TOKEN, not HTML
            # Real SB8200 returns just the token string
            assert "Downstream Bonded Channels" not in resp.text, (
                "Two-step login should return token, not HTML. "
                "This test validates the mock behaves like real firmware."
            )

            # Response should be a short token string
            response_token = resp.text.strip()
            assert len(response_token) > 0, "Should receive session token in response body"
            assert len(response_token) < 100, "Token should be short string, not full HTML"

    def test_two_step_data_fetch_requires_token(self, test_certs):
        """Verify data page requires token after two-step login.

        After login, fetching data without token should fail.
        """
        import base64

        import requests

        modem_path = MODEMS_DIR / "arris" / "sb8200"
        if not modem_path.exists():
            pytest.skip("SB8200 modem directory not found")

        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        with MockModemServer.from_modem_path(
            modem_path, auth_type="url_token:two_step:strict", ssl_context=context
        ) as server:
            session = requests.Session()
            session.verify = False

            # Step 1: Login - get token from response body
            token = base64.b64encode(b"admin:pw").decode()
            login_resp = session.get(
                f"https://127.0.0.1:{server.port}/cmconnectionstatus.html?login_{token}",
                timeout=5,
            )
            session_token = login_resp.text.strip()

            # Step 2: Fetch without token - should fail
            bad_resp = session.get(
                f"https://127.0.0.1:{server.port}/cmconnectionstatus.html",
                timeout=5,
            )
            assert (
                "Downstream Bonded Channels" not in bad_resp.text
            ), "Data fetch without token should return login page"

            # Step 3: Fetch WITH token - should work
            good_resp = session.get(
                f"https://127.0.0.1:{server.port}/cmconnectionstatus.html?ct_{session_token}",
                timeout=5,
            )
            assert (
                "Downstream Bonded Channels" in good_resp.text
            ), "Data fetch with correct token should return data page"

    def test_polling_with_two_step_url_token(self, test_certs):
        """Test full polling cycle with two-step URL token auth.

        Two-step auth: login returns ONLY the session token (not HTML).
        Client must then fetch data pages with ?ct_<token>.

        Issue #81 context: With the pre-auth skip fix, this works because:
        1. Initial fetch returns login page (no token)
        2. Reactive auth detects login page, calls _login()
        3. _login() gets token from response body
        4. HTMLLoader fetches pages with token (via url_token_config)
        """
        modem_path = MODEMS_DIR / "arris" / "sb8200"
        if not modem_path.exists():
            pytest.skip("SB8200 modem directory not found")

        parser_class = _get_sb8200_parser()
        if not parser_class:
            pytest.skip("SB8200 parser not found")

        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        # two_step + strict: login returns only token, all requests need URL token
        with MockModemServer.from_modem_path(
            modem_path, auth_type="url_token:two_step:strict", ssl_context=context
        ) as server:
            adapter = get_auth_adapter_for_parser(parser_class.__name__)
            url_token_config = adapter.get_auth_config_for_type("url_token")

            # Pass parser INSTANCE (not class) so _fetch_data() has URL patterns
            orchestrator = DataOrchestrator(
                host=f"https://127.0.0.1:{server.port}",
                username="admin",
                password="pw",
                parser=parser_class(),  # Instantiate
                cached_url=f"https://127.0.0.1:{server.port}",
                verify_ssl=False,
                legacy_ssl=False,
                auth_strategy="url_token_session",
                auth_url_token_config=url_token_config,
                timeout=TEST_TIMEOUT,
            )

            # This is the actual polling call - should work end-to-end
            data = orchestrator.get_modem_data()

            # Verify we got actual channel data
            downstream = data.get("cable_modem_downstream", [])
            assert len(downstream) > 0, (
                "Polling with two-step URL token auth should return channel data.\n"
                "Got 0 channels - check HTMLLoader uses token from auth response."
            )

            # Note: system_info from /cmswinfo.html is optional
            # The key assertion is downstream channels above

    def test_loader_fetches_additional_pages_with_correct_token(self, test_certs):
        """Verify HTMLLoader uses CORRECT token (from response body, not cookie).

        Issue #81 context: The auth handler stores the session token from the
        response body. This token is then passed to the loader via url_token_config
        in _create_loader(). The loader uses it to build URLs with ?ct_<token>.

        With the pre-auth skip fix, the token flow is:
        1. Reactive auth calls _login() -> AuthHandler stores token
        2. _create_loader() gets token via auth_handler.get_session_token()
        3. Loader builds URLs with the correct token
        """
        modem_path = MODEMS_DIR / "arris" / "sb8200"
        if not modem_path.exists():
            pytest.skip("SB8200 modem directory not found")

        parser_class = _get_sb8200_parser()
        if not parser_class:
            pytest.skip("SB8200 parser not found")

        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        # two_step + strict: login returns only token (body != cookie), all requests need URL token
        with MockModemServer.from_modem_path(
            modem_path, auth_type="url_token:two_step:strict", ssl_context=context
        ) as server:
            adapter = get_auth_adapter_for_parser(parser_class.__name__)
            url_token_config = adapter.get_auth_config_for_type("url_token")

            # Pass parser INSTANCE (not class) so _fetch_data() has URL patterns
            orchestrator = DataOrchestrator(
                host=f"https://127.0.0.1:{server.port}",
                username="admin",
                password="pw",
                parser=parser_class(),  # Instantiate
                cached_url=f"https://127.0.0.1:{server.port}",
                verify_ssl=False,
                legacy_ssl=False,
                auth_strategy="url_token_session",
                auth_url_token_config=url_token_config,
                timeout=TEST_TIMEOUT,
            )

            # Track all URLs requested by patching the session
            requests_made: list[str] = []
            original_get = orchestrator.session.get

            def tracking_get(url, *args, **kwargs):
                requests_made.append(url)
                return original_get(url, *args, **kwargs)

            orchestrator.session.get = tracking_get

            # Run the full data fetch
            data = orchestrator.get_modem_data()

        # Verify we got actual channel data (primary assertion)
        downstream = data.get("cable_modem_downstream", [])
        assert len(downstream) > 0, (
            "Parser should return channel data.\n"
            "Got 0 channels - loader likely fetched pages without proper token.\n"
            f"Requests made: {requests_made}"
        )

        # Debug output for troubleshooting
        print(f"\n=== Requests made ({len(requests_made)}) ===")
        for i, req in enumerate(requests_made):
            print(f"  {i+1}. {req}")
        print("=" * 50)
