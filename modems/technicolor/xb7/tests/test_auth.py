"""Integration tests for Technicolor XB7 form-based authentication.

This test validates the XB7 auth flow works correctly with our mock server
and the auth adapter changes.

## Auth Flow (CONFIRMED from Issue #2 - @esand)
==============================================
Source: https://github.com/solentlabs/cable_modem_monitor/issues/2

1. User accesses any protected page (e.g., /network_setup.jst)
2. Modem redirects to login page (/login.jst)
3. Login form has fields: id="username", id="password"
4. Form POSTs to /check.jst
5. On SUCCESS: Server returns 302 redirect to /at_a_glance.jst with Set-Cookie
6. On FAILURE: Server shows login page again
7. Authenticated session can then access /network_setup.jst

User quote from issue #2:
> "The form itself submits to `check.jst`. Upon successful authentication,
> it sends a Location redirect to `at_a_glance.jst`."

## What This Test Validates
===========================
1. Mock server correctly implements the XB7 auth flow
2. AuthHandler with form_plain strategy can authenticate
3. success_redirect check passes when redirect URL matches
4. Authenticated session can fetch data page
5. Parser can extract channel data from fixture

## Assumptions (Document Any Guesses)
=====================================
- CONFIRMED: Login form POSTs to /check.jst (from @esand in issue #2)
- CONFIRMED: Success redirects to /at_a_glance.jst (from @esand in issue #2)
- CONFIRMED: Data page is /network_setup.jst (from @esand in issue #2)
- IMPLICIT: Session cookie name - requests.Session() handles whatever cookie the server sets.
            In v3.11, the parser's login() method used requests.Session() internally.
            modem.yaml has "session" as cookie_name but this is only used by mock server.
- ASSUMED: Form field names are "username" and "password" (standard, user mentioned ids match)
"""

from pathlib import Path

import pytest
import requests

from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType
from tests.integration.mock_handlers.form import TEST_PASSWORD, TEST_USERNAME
from tests.integration.mock_modem_server import MockModemServer

# Test timeout constant - matches DEFAULT_TIMEOUT from schema
TEST_TIMEOUT = 10

# Path to XB7 modem config
XB7_MODEM_PATH = Path("modems/technicolor/xb7")


class TestXB7FormAuth:
    """Test XB7 form-based authentication flow."""

    def test_mock_server_serves_login_page_for_protected_path(self) -> None:
        """Unauthenticated request to protected path returns login page."""
        with MockModemServer.from_modem_path(XB7_MODEM_PATH) as server:
            response = requests.get(f"{server.url}/network_setup.jst", timeout=5)

            assert response.status_code == 200
            # Should get login page, not data page
            assert "form" in response.text.lower()
            assert "password" in response.text.lower()

    def test_mock_server_login_with_valid_credentials(self) -> None:
        """Valid credentials should authenticate and redirect."""
        with MockModemServer.from_modem_path(XB7_MODEM_PATH) as server:
            session = requests.Session()

            # POST to login endpoint
            response = session.post(
                f"{server.url}/check.jst",
                data={"username": TEST_USERNAME, "password": TEST_PASSWORD},
                allow_redirects=False,
                timeout=5,
            )

            # Should get 302 redirect to /at_a_glance.jst
            assert response.status_code == 302
            assert "/at_a_glance.jst" in response.headers.get("Location", "")

            # Session should have cookie set
            assert len(session.cookies) > 0

    def test_mock_server_login_with_invalid_credentials(self) -> None:
        """Invalid credentials should return login page."""
        with MockModemServer.from_modem_path(XB7_MODEM_PATH) as server:
            session = requests.Session()

            response = session.post(
                f"{server.url}/check.jst",
                data={"username": "wrong", "password": "wrong"},
                allow_redirects=False,
                timeout=5,
            )

            # Should get login page (200), not redirect
            assert response.status_code == 200
            assert "form" in response.text.lower()

    def test_mock_server_authenticated_access_to_data_page(self) -> None:
        """Authenticated session can access data page."""
        with MockModemServer.from_modem_path(XB7_MODEM_PATH) as server:
            session = requests.Session()

            # Login first
            session.post(
                f"{server.url}/check.jst",
                data={"username": TEST_USERNAME, "password": TEST_PASSWORD},
                allow_redirects=True,
                timeout=5,
            )

            # Now access data page
            response = session.get(f"{server.url}/network_setup.jst", timeout=5)

            assert response.status_code == 200
            # Should get actual data page content (from fixture)
            assert "Rogers" in response.text or "Channel" in response.text

    def test_auth_handler_form_plain_strategy(self) -> None:
        """AuthHandler with form_plain strategy authenticates successfully."""
        with MockModemServer.from_modem_path(XB7_MODEM_PATH) as server:
            session = requests.Session()

            # Create AuthHandler with XB7's form config
            handler = AuthHandler(
                strategy=AuthStrategyType.FORM_PLAIN,
                form_config={
                    "action": "/check.jst",
                    "method": "POST",
                    "username_field": "username",
                    "password_field": "password",
                    "success_redirect": "/at_a_glance.jst",
                },
                timeout=TEST_TIMEOUT,
            )

            # Authenticate
            result = handler.authenticate(
                session=session,
                base_url=server.url,
                username=TEST_USERNAME,
                password=TEST_PASSWORD,
                verbose=True,
            )

            assert result.success, f"Auth failed: {result.error_message}"

    def test_auth_handler_with_wrong_redirect_soft_fails(self) -> None:
        """AuthHandler with wrong redirect URL soft-fails to is_login_page check.

        This tests the soft-fail behavior added to prevent breaking modems
        where the redirect URL in modem.yaml is incorrect (guessed, not verified).
        """
        with MockModemServer.from_modem_path(XB7_MODEM_PATH) as server:
            session = requests.Session()

            # Create AuthHandler with WRONG redirect URL
            handler = AuthHandler(
                strategy=AuthStrategyType.FORM_PLAIN,
                form_config={
                    "action": "/check.jst",
                    "method": "POST",
                    "username_field": "username",
                    "password_field": "password",
                    "success_redirect": "/wrong_page.jst",  # Wrong!
                },
                timeout=TEST_TIMEOUT,
            )

            # Authenticate - should soft-fail to is_login_page() check
            result = handler.authenticate(
                session=session,
                base_url=server.url,
                username=TEST_USERNAME,
                password=TEST_PASSWORD,
                verbose=True,
            )

            # Should still succeed via fallback (redirect page is not a login page)
            assert result.success, f"Auth should soft-fail and succeed: {result.error_message}"

    def test_full_flow_auth_and_parse(self) -> None:
        """Full integration: authenticate and parse channel data."""
        with MockModemServer.from_modem_path(XB7_MODEM_PATH) as server:
            session = requests.Session()

            # Create AuthHandler from modem.yaml config
            handler = AuthHandler.from_modem_config(server.config)

            # Authenticate
            result = handler.authenticate(
                session=session,
                base_url=server.url,
                username=TEST_USERNAME,
                password=TEST_PASSWORD,
                verbose=True,
            )
            assert result.success, f"Auth failed: {result.error_message}"

            # Fetch data page
            response = session.get(f"{server.url}/network_setup.jst", timeout=5)
            assert response.status_code == 200

            # Parse with XB7 parser
            from bs4 import BeautifulSoup

            from custom_components.cable_modem_monitor.modems.technicolor.xb7.parser import (
                TechnicolorXB7Parser,
            )

            parser = TechnicolorXB7Parser()
            soup = BeautifulSoup(response.text, "html.parser")
            resources = {"/network_setup.jst": soup}

            data = parser.parse_resources(resources)
            # Verify parser ran without error - actual channel extraction is tested elsewhere
            # (Parser returns {'downstream': [...], 'upstream': [...], 'system_info': {...}})
            assert "downstream" in data and "upstream" in data, "Parser should return expected structure"


class TestXB7AuthRedirectValidation:
    """Test the success_redirect validation specifically.

    These tests validate the soft-fail behavior that was added to prevent
    breaking modems where the modem.yaml redirect URL is an unverified guess.
    """

    def test_correct_redirect_passes(self) -> None:
        """Correct redirect URL in config should pass validation."""
        with MockModemServer.from_modem_path(XB7_MODEM_PATH) as server:
            session = requests.Session()

            handler = AuthHandler(
                strategy=AuthStrategyType.FORM_PLAIN,
                form_config={
                    "action": "/check.jst",
                    "username_field": "username",
                    "password_field": "password",
                    "success_redirect": "/at_a_glance.jst",  # Correct!
                },
                timeout=TEST_TIMEOUT,
            )

            result = handler.authenticate(
                session=session,
                base_url=server.url,
                username=TEST_USERNAME,
                password=TEST_PASSWORD,
            )

            assert result.success

    def test_wrong_redirect_soft_fails_to_fallback(self, caplog: pytest.LogCaptureFixture) -> None:
        """Wrong redirect URL should log warning and fall back.

        This captures logs to verify the INFO message is emitted,
        which will help us identify incorrect modem.yaml configs
        from user diagnostics.
        """
        import logging

        with MockModemServer.from_modem_path(XB7_MODEM_PATH) as server:
            session = requests.Session()

            handler = AuthHandler(
                strategy=AuthStrategyType.FORM_PLAIN,
                form_config={
                    "action": "/check.jst",
                    "username_field": "username",
                    "password_field": "password",
                    "success_redirect": "/totally_wrong.jst",  # Wrong!
                },
                timeout=TEST_TIMEOUT,
            )

            with caplog.at_level(logging.INFO):
                result = handler.authenticate(
                    session=session,
                    base_url=server.url,
                    username=TEST_USERNAME,
                    password=TEST_PASSWORD,
                )

            # Should succeed via fallback
            assert result.success

            # Should have logged the redirect mismatch
            assert any("expected redirect to" in record.message.lower() for record in caplog.records)

    def test_no_redirect_config_uses_login_page_check(self) -> None:
        """No success_redirect config should use is_login_page() check."""
        with MockModemServer.from_modem_path(XB7_MODEM_PATH) as server:
            session = requests.Session()

            handler = AuthHandler(
                strategy=AuthStrategyType.FORM_PLAIN,
                form_config={
                    "action": "/check.jst",
                    "username_field": "username",
                    "password_field": "password",
                    # No success_redirect - rely on is_login_page()
                },
                timeout=TEST_TIMEOUT,
            )

            result = handler.authenticate(
                session=session,
                base_url=server.url,
                username=TEST_USERNAME,
                password=TEST_PASSWORD,
            )

            assert result.success
