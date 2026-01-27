"""Integration tests for HTTPS + Form Authentication.

These tests verify that form-based authentication works correctly
over HTTPS connections, including:
1. Self-signed certificate handling
2. Form submission over TLS
3. Cookie security over HTTPS
4. Combined with legacy SSL if needed

This covers modems like newer firmware that use HTTPS + form login.
"""

from __future__ import annotations

import pytest
import requests
import urllib3

from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType

# Suppress InsecureRequestWarning for tests with verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Test timeout constant - matches DEFAULT_TIMEOUT from schema
TEST_TIMEOUT = 10


class TestHTTPSFormAuth:
    """Test form authentication over HTTPS."""

    def test_https_serves_login_form(self, https_form_auth_server):
        """Verify HTTPS server serves login form."""
        session = requests.Session()
        session.verify = False

        response = session.get(https_form_auth_server.url, timeout=TEST_TIMEOUT)

        assert response.status_code == 200
        assert 'type="password"' in response.text.lower()

    def test_https_form_login_success(self, https_form_auth_server):
        """Verify form login works over HTTPS."""
        session = requests.Session()
        session.verify = False

        # Submit login form
        response = session.post(
            f"{https_form_auth_server.url}/login",
            data={"username": "admin", "password": "pw"},
            allow_redirects=True,
            timeout=TEST_TIMEOUT,
        )

        # Should have session cookie and be on data page
        assert len(session.cookies) > 0
        assert "Cable Modem Status" in response.text or response.status_code == 200

    def test_https_form_login_wrong_credentials(self, https_form_auth_server):
        """Verify wrong credentials fail over HTTPS."""
        session = requests.Session()
        session.verify = False

        response = session.post(
            f"{https_form_auth_server.url}/login",
            data={"username": "wrong", "password": "wrong"},
            allow_redirects=True,
            timeout=TEST_TIMEOUT,
        )

        # Should show login form again
        assert 'type="password"' in response.text.lower()

    def test_https_session_cookie_persists(self, https_form_auth_server):
        """Verify session cookie persists for HTTPS requests."""
        session = requests.Session()
        session.verify = False

        # Login
        session.post(
            f"{https_form_auth_server.url}/login",
            data={"username": "admin", "password": "pw"},
            allow_redirects=True,
            timeout=TEST_TIMEOUT,
        )

        # Multiple requests should work
        for i in range(5):
            response = session.get(f"{https_form_auth_server.url}/status.html", timeout=TEST_TIMEOUT)
            assert response.status_code == 200
            assert "Cable Modem Status" in response.text, f"Request {i + 1} failed"


class TestHTTPSAuthHandler:
    """Test AuthHandler with HTTPS + Form auth."""

    def test_auth_handler_https_form(self, https_form_auth_server):
        """Verify AuthHandler works with HTTPS form auth."""
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

        success, html = handler.authenticate(
            session=session,
            base_url=https_form_auth_server.url,
            username="admin",
            password="pw",
        )

        assert success is True
        # Should be able to access data
        response = session.get(f"{https_form_auth_server.url}/status.html", timeout=TEST_TIMEOUT)
        assert "Cable Modem Status" in response.text

    def test_auth_handler_https_form_invalid_creds(self, https_form_auth_server):
        """Verify AuthHandler reports failure for bad HTTPS credentials."""
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

        success, _ = handler.authenticate(
            session=session,
            base_url=https_form_auth_server.url,
            username="wrong",
            password="wrong",
        )

        assert success is False


class TestHTTPSWithModernSSL:
    """Test HTTPS form auth with modern SSL ciphers."""

    def test_modern_ssl_form_login(self, https_modern_server):
        """Verify form-like requests work over modern HTTPS."""
        session = requests.Session()
        session.verify = False

        # Just verify we can connect and get response
        response = session.get(https_modern_server.url, timeout=TEST_TIMEOUT)
        assert response.status_code == 200


class TestHTTPSCertificateHandling:
    """Test certificate handling with HTTPS."""

    def test_self_signed_cert_with_verify_false(self, https_form_auth_server):
        """Verify self-signed cert works with verify=False."""
        session = requests.Session()
        session.verify = False

        response = session.get(https_form_auth_server.url, timeout=TEST_TIMEOUT)
        assert response.status_code == 200

    def test_self_signed_cert_verify_true_fails(self, https_form_auth_server):
        """Verify self-signed cert fails with verify=True."""
        session = requests.Session()
        session.verify = True

        with pytest.raises(requests.exceptions.SSLError):
            session.get(https_form_auth_server.url, timeout=TEST_TIMEOUT)
