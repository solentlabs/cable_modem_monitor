"""Integration tests for session lifecycle management.

These tests verify:
1. Session expiry detection during polling
2. Re-authentication after session timeout
3. Cookie persistence across multiple requests
4. Session refresh handling

This is critical for modems that expire sessions after idle time or N requests.
"""

from __future__ import annotations

import requests

from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType

# Test timeout constant - matches DEFAULT_TIMEOUT from schema
TEST_TIMEOUT = 10


class TestSessionExpiry:
    """Test session expiration detection."""

    def test_session_valid_within_limit(self, session_expiry_server):
        """Verify session remains valid within request limit."""
        session = requests.Session()
        session.verify = False

        # Login first (session state is what matters, not response)
        _ = session.post(
            f"{session_expiry_server.url}/login",
            data={"username": "admin", "password": "password"},
            allow_redirects=True,
            timeout=TEST_TIMEOUT,
        )

        # Make requests within the limit (default 3)
        for i in range(3):
            response = session.get(f"{session_expiry_server.url}/status", timeout=TEST_TIMEOUT)
            assert response.status_code == 200
            # Should get data, not login form
            assert "Cable Modem Status" in response.text, f"Request {i + 1} should get data"

    def test_session_expired_after_limit(self, session_expiry_server):
        """Verify session expires after request limit exceeded."""
        session = requests.Session()
        session.verify = False

        # Login first
        session.post(
            f"{session_expiry_server.url}/login",
            data={"username": "admin", "password": "password"},
            allow_redirects=True,
            timeout=TEST_TIMEOUT,
        )

        # Make requests up to the limit
        for _ in range(3):
            session.get(f"{session_expiry_server.url}/status", timeout=TEST_TIMEOUT)

        # Next request should show login form (session expired)
        response = session.get(f"{session_expiry_server.url}/status", timeout=TEST_TIMEOUT)
        assert 'type="password"' in response.text.lower(), "Should show login form after expiry"

    def test_reauth_after_expiry(self, session_expiry_server):
        """Verify re-authentication works after session expiry."""
        session = requests.Session()
        session.verify = False

        # Login first
        session.post(
            f"{session_expiry_server.url}/login",
            data={"username": "admin", "password": "password"},
            allow_redirects=True,
            timeout=TEST_TIMEOUT,
        )

        # Exhaust session
        for _ in range(4):
            session.get(f"{session_expiry_server.url}/status", timeout=TEST_TIMEOUT)

        # Re-authenticate
        session.post(
            f"{session_expiry_server.url}/login",
            data={"username": "admin", "password": "password"},
            allow_redirects=True,
            timeout=TEST_TIMEOUT,
        )

        # Should work again
        response = session.get(f"{session_expiry_server.url}/status", timeout=TEST_TIMEOUT)
        assert "Cable Modem Status" in response.text


class TestSessionPersistence:
    """Test session cookie persistence across requests."""

    def test_cookies_persist_across_requests(self, form_auth_server):
        """Verify session cookies persist in requests.Session."""
        session = requests.Session()
        session.verify = False

        # Get login form first
        response = session.get(form_auth_server.url, timeout=TEST_TIMEOUT)
        assert 'type="password"' in response.text.lower()

        # Login
        session.post(
            f"{form_auth_server.url}/login",
            data={"username": "admin", "password": "pw"},
            allow_redirects=True,
            timeout=TEST_TIMEOUT,
        )

        # Should have session cookie now
        assert len(session.cookies) > 0, "Should have session cookie after login"

        # Multiple requests should maintain session
        for request_num in range(5):
            response = session.get(f"{form_auth_server.url}/status.html", timeout=TEST_TIMEOUT)
            assert response.status_code == 200
            assert "Cable Modem Status" in response.text, f"Request {request_num + 1} should succeed"

    def test_session_survives_redirect(self, form_auth_server):
        """Verify session cookies survive redirect after login."""
        session = requests.Session()
        session.verify = False

        # Login with redirect
        response = session.post(
            f"{form_auth_server.url}/login",
            data={"username": "admin", "password": "pw"},
            allow_redirects=True,
            timeout=TEST_TIMEOUT,
        )

        # After redirect, should still have cookies
        assert len(session.cookies) > 0
        # And should be on data page
        assert "Cable Modem Status" in response.text or response.url.endswith("status.html")


class TestAuthHandlerReauth:
    """Test AuthHandler re-authentication capability."""

    def test_form_auth_can_reauth(self, form_auth_server):
        """Verify AuthHandler can re-authenticate with form auth."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
            },
            timeout=TEST_TIMEOUT,
        )

        session = requests.Session()
        session.verify = False

        # First auth
        success1, _ = handler.authenticate(
            session=session,
            base_url=form_auth_server.url,
            username="admin",
            password="pw",
        )
        assert success1 is True

        # Clear session cookies (simulate expiry)
        session.cookies.clear()

        # Re-authenticate
        success2, _ = handler.authenticate(
            session=session,
            base_url=form_auth_server.url,
            username="admin",
            password="pw",
        )
        assert success2 is True

        # Should be able to access data
        response = session.get(f"{form_auth_server.url}/status.html", timeout=TEST_TIMEOUT)
        assert "Cable Modem Status" in response.text

    def test_basic_auth_persists(self, basic_auth_server):
        """Verify Basic Auth credentials persist across requests."""
        handler = AuthHandler(strategy=AuthStrategyType.BASIC_HTTP, timeout=TEST_TIMEOUT)

        session = requests.Session()
        session.verify = False

        success, _ = handler.authenticate(
            session=session,
            base_url=basic_auth_server.url,
            username="admin",
            password="pw",
        )
        assert success is True

        # session.auth should be set
        assert session.auth is not None
        assert session.auth == ("admin", "pw")

        # Multiple requests should work
        for _ in range(3):
            response = session.get(basic_auth_server.url, timeout=TEST_TIMEOUT)
            assert response.status_code == 200
            assert "Cable Modem Status" in response.text


class TestPollingSimulation:
    """Test simulated polling with multiple data fetches."""

    def test_multiple_polls_with_form_auth(self, form_auth_server):
        """Simulate multiple polling cycles with form auth."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
            },
            timeout=TEST_TIMEOUT,
        )

        session = requests.Session()
        session.verify = False

        # Authenticate once
        success, _ = handler.authenticate(
            session=session,
            base_url=form_auth_server.url,
            username="admin",
            password="pw",
        )
        assert success is True

        # Simulate 10 polling cycles
        for i in range(10):
            response = session.get(f"{form_auth_server.url}/status.html", timeout=TEST_TIMEOUT)
            assert response.status_code == 200, f"Poll {i + 1} failed"
            assert "Cable Modem Status" in response.text, f"Poll {i + 1} didn't get data"

    def test_polling_detects_session_loss(self, session_expiry_server):
        """Verify polling can detect when session is lost."""
        session = requests.Session()
        session.verify = False

        # Login
        session.post(
            f"{session_expiry_server.url}/login",
            data={"username": "admin", "password": "password"},
            allow_redirects=True,
            timeout=TEST_TIMEOUT,
        )

        # Poll until session expires
        polls_successful = 0
        for _ in range(10):
            response = session.get(f"{session_expiry_server.url}/status", timeout=TEST_TIMEOUT)
            if "Cable Modem Status" in response.text:
                polls_successful += 1
            else:
                # Session expired - login form returned
                break

        # Should have succeeded for first 3 requests (max_requests_per_session)
        assert polls_successful == 3, f"Expected 3 successful polls, got {polls_successful}"
