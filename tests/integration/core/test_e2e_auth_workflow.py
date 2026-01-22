"""End-to-end integration tests for complete authentication workflows.

These tests verify the full authentication flow from initial connection
through authenticated data access, simulating real polling scenarios:
1. Initial connection to modem
2. Auth type detection (or using stored strategy)
3. Authentication with credentials
4. Multiple data fetches with session persistence
5. Session refresh if needed

This is the closest simulation to real-world usage without HAR captures.
"""

from __future__ import annotations

import requests

from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType


class TestE2ENoAuth:
    """End-to-end tests for NO_AUTH modems."""

    def test_no_auth_workflow(self, http_server):
        """Test complete workflow for modem without authentication."""
        session = requests.Session()
        session.verify = False

        # Step 1: Connect to modem
        response = session.get(http_server.url, timeout=10)
        assert response.status_code == 200

        # Step 2: No auth needed, verify we can get data
        assert "Cable Modem Status" in response.text

        # Step 3: Multiple polling cycles work
        for i in range(5):
            response = session.get(http_server.url, timeout=10)
            assert response.status_code == 200
            assert "Cable Modem Status" in response.text, f"Poll {i + 1} failed"


class TestE2EBasicAuth:
    """End-to-end tests for BASIC_HTTP modems.

    Note: Basic auth handler does NOT return HTML because basic auth is per-request
    (header-based), not session-based. The handler sets session.auth so all subsequent
    requests include the Authorization header. The scraper fetches the actual data page.
    """

    def test_basic_auth_workflow(self, basic_auth_server):
        """Test complete workflow for modem with Basic Auth."""
        # Step 1: Create handler with stored strategy
        handler = AuthHandler(strategy=AuthStrategyType.BASIC_HTTP)

        session = requests.Session()
        session.verify = False

        # Step 2: Authenticate - sets session.auth, does NOT return HTML
        success, html = handler.authenticate(
            session=session,
            base_url=basic_auth_server.url,
            username="admin",
            password="pw",
        )
        assert success is True
        assert html is None  # Basic auth does NOT return HTML
        assert session.auth == ("admin", "pw")

        # Step 3: Multiple polling cycles - now session.auth is set, all requests work
        for i in range(5):
            response = session.get(basic_auth_server.url, timeout=10)
            assert response.status_code == 200
            assert "Cable Modem Status" in response.text, f"Poll {i + 1} failed"

    def test_basic_auth_invalid_then_valid(self, basic_auth_server):
        """Test workflow: invalid credentials, then valid credentials."""
        handler = AuthHandler(strategy=AuthStrategyType.BASIC_HTTP)
        session = requests.Session()
        session.verify = False

        # Failed auth
        success, _ = handler.authenticate(
            session=session,
            base_url=basic_auth_server.url,
            username="wrong",
            password="wrong",
        )
        assert success is False

        # Session should not have auth set after failure
        session.auth = None

        # Successful auth - sets session.auth, does NOT return HTML
        success, html = handler.authenticate(
            session=session,
            base_url=basic_auth_server.url,
            username="admin",
            password="pw",
        )
        assert success is True
        assert html is None  # Basic auth does NOT return HTML
        assert session.auth == ("admin", "pw")

        # Verify we can now fetch data
        response = session.get(basic_auth_server.url, timeout=10)
        assert response.status_code == 200
        assert "Cable Modem Status" in response.text


class TestE2EFormAuth:
    """End-to-end tests for FORM_PLAIN modems."""

    def test_form_auth_workflow(self, form_auth_server):
        """Test complete workflow for modem with form authentication."""
        # Step 1: Create handler with stored strategy and form config
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
                "hidden_fields": {"csrf_token": "test-csrf-token"},
            },
        )

        session = requests.Session()
        session.verify = False

        # Step 2: Verify initial page shows login form
        initial = session.get(form_auth_server.url, timeout=10)
        assert 'type="password"' in initial.text.lower()

        # Step 3: Authenticate
        success, _ = handler.authenticate(
            session=session,
            base_url=form_auth_server.url,
            username="admin",
            password="pw",
        )
        assert success is True
        assert len(session.cookies) > 0, "Should have session cookie"

        # Step 4: Multiple polling cycles
        for i in range(10):
            response = session.get(f"{form_auth_server.url}/status.html", timeout=10)
            assert response.status_code == 200
            assert "Cable Modem Status" in response.text, f"Poll {i + 1} failed"


class TestE2EFormBase64:
    """End-to-end tests for form auth with base64 encoding."""

    def test_form_base64_workflow(self, form_base64_server):
        """Test complete workflow for modem with base64 form auth."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
                "password_encoding": "base64",
            },
        )

        session = requests.Session()
        session.verify = False

        # Authenticate
        success, _ = handler.authenticate(
            session=session,
            base_url=form_base64_server.url,
            username="admin",
            password="p@ss!word",
        )
        assert success is True

        # Multiple polling cycles
        for i in range(5):
            response = session.get(form_base64_server.url, timeout=10)
            assert response.status_code == 200
            assert "Cable Modem Status" in response.text, f"Poll {i + 1} failed"


# NOTE: URL_TOKEN_SESSION E2E tests are in modems/arris/sb8200/tests/test_sb8200_auth.py
# Core tests should use synthetic servers when URL token mechanism tests are needed.


class TestE2ERedirectFlow:
    """End-to-end tests for modems with redirect-based auth."""

    def test_redirect_workflow(self, http_302_redirect_server):
        """Test workflow with 302 redirects to login."""
        session = requests.Session()
        session.verify = False

        # Step 1: Initial access redirects to login
        response = session.get(http_302_redirect_server.url, allow_redirects=True, timeout=10)
        assert 'type="password"' in response.text.lower()

        # Step 2: Submit login
        response = session.post(
            f"{http_302_redirect_server.url}/login",
            data={"username": "admin", "password": "pw"},
            allow_redirects=True,
            timeout=10,
        )
        assert response.status_code == 200

        # Step 3: Access data
        response = session.get(f"{http_302_redirect_server.url}/data", timeout=10)
        assert "Cable Modem Status" in response.text


class TestE2EHTTPSWorkflow:
    """End-to-end tests for HTTPS modems."""

    def test_https_form_workflow(self, https_form_auth_server):
        """Test complete HTTPS + form auth workflow."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
            },
        )

        session = requests.Session()
        session.verify = False  # Self-signed cert

        # Authenticate over HTTPS
        success, _ = handler.authenticate(
            session=session,
            base_url=https_form_auth_server.url,
            username="admin",
            password="pw",
        )
        assert success is True

        # Poll over HTTPS
        for i in range(5):
            response = session.get(f"{https_form_auth_server.url}/status.html", timeout=10)
            assert response.status_code == 200
            assert "Cable Modem Status" in response.text, f"HTTPS poll {i + 1} failed"


class TestE2ESessionExpiry:
    """End-to-end tests for session expiry and re-auth."""

    def test_session_expiry_reauth_workflow(self, session_expiry_server):
        """Test workflow with session expiry and re-authentication."""
        session = requests.Session()
        session.verify = False

        # Initial login
        session.post(
            f"{session_expiry_server.url}/login",
            data={"username": "admin", "password": "password"},
            allow_redirects=True,
            timeout=10,
        )

        # Poll until session expires (max 3 requests)
        for i in range(3):
            response = session.get(f"{session_expiry_server.url}/status", timeout=10)
            assert "Cable Modem Status" in response.text, f"Poll {i + 1} should succeed"

        # 4th request should fail (session expired)
        response = session.get(f"{session_expiry_server.url}/status", timeout=10)
        assert 'type="password"' in response.text.lower(), "Should show login after expiry"

        # Re-authenticate
        session.post(
            f"{session_expiry_server.url}/login",
            data={"username": "admin", "password": "password"},
            allow_redirects=True,
            timeout=10,
        )

        # Should work again
        response = session.get(f"{session_expiry_server.url}/status", timeout=10)
        assert "Cable Modem Status" in response.text, "Should work after re-auth"


class TestE2EMultipleModemTypes:
    """Test workflows for different modem configurations."""

    def test_parallel_sessions(self, http_server, form_auth_server, basic_auth_server):
        """Test handling multiple modem types in parallel (like HA multi-device)."""
        # Modem 1: No auth
        session1 = requests.Session()
        session1.verify = False
        r1 = session1.get(http_server.url, timeout=10)
        assert "Cable Modem Status" in r1.text

        # Modem 2: Form auth
        session2 = requests.Session()
        session2.verify = False
        handler2 = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
            },
        )
        handler2.authenticate(
            session=session2,
            base_url=form_auth_server.url,
            username="admin",
            password="pw",
        )
        r2 = session2.get(f"{form_auth_server.url}/status.html", timeout=10)
        assert "Cable Modem Status" in r2.text

        # Modem 3: Basic auth
        session3 = requests.Session()
        session3.verify = False
        handler3 = AuthHandler(strategy=AuthStrategyType.BASIC_HTTP)
        handler3.authenticate(
            session=session3,
            base_url=basic_auth_server.url,
            username="admin",
            password="pw",
        )
        r3 = session3.get(basic_auth_server.url, timeout=10)
        assert "Cable Modem Status" in r3.text

        # All three should continue working independently
        for _ in range(3):
            assert "Cable Modem Status" in session1.get(http_server.url, timeout=10).text
            assert "Cable Modem Status" in session2.get(f"{form_auth_server.url}/status.html", timeout=10).text
            assert "Cable Modem Status" in session3.get(basic_auth_server.url, timeout=10).text
