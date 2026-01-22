"""Integration tests for HTTP redirect handling.

These tests verify proper handling of:
1. HTTP 302 redirects (Location header)
2. Meta refresh redirects
3. Redirect chains
4. Cookie persistence through redirects

This is important for modems that redirect unauthenticated requests to login.
"""

from __future__ import annotations

import requests


class TestHTTP302Redirects:
    """Test HTTP 302 redirect handling."""

    def test_302_redirect_to_login(self, http_302_redirect_server):
        """Verify 302 redirect to login page."""
        session = requests.Session()
        session.verify = False

        # Request root without auth - should redirect to /login
        response = session.get(
            http_302_redirect_server.url,
            allow_redirects=False,
            timeout=10,
        )

        assert response.status_code == 302
        assert response.headers.get("Location") == "/login"

    def test_302_redirect_followed_to_login(self, http_302_redirect_server):
        """Verify following 302 redirect lands on login page."""
        session = requests.Session()
        session.verify = False

        # Request root, follow redirects
        response = session.get(
            http_302_redirect_server.url,
            allow_redirects=True,
            timeout=10,
        )

        assert response.status_code == 200
        assert 'type="password"' in response.text.lower()

    def test_302_redirect_after_login(self, http_302_redirect_server):
        """Verify 302 redirect to data page after login."""
        session = requests.Session()
        session.verify = False

        # Login
        response = session.post(
            f"{http_302_redirect_server.url}/login",
            data={"username": "admin", "password": "pw"},
            allow_redirects=False,
            timeout=10,
        )

        assert response.status_code == 302
        assert response.headers.get("Location") == "/data"
        # Should have session cookie
        assert "session=" in response.headers.get("Set-Cookie", "")

    def test_302_redirect_with_cookies_to_data(self, http_302_redirect_server):
        """Verify redirect to data page with session cookie."""
        session = requests.Session()
        session.verify = False

        # Login with follow redirects
        response = session.post(
            f"{http_302_redirect_server.url}/login",
            data={"username": "admin", "password": "pw"},
            allow_redirects=True,
            timeout=10,
        )

        # Should end up on data page
        assert response.status_code == 200
        assert "Cable Modem Status" in response.text

    def test_302_wrong_credentials_redirects_to_login(self, http_302_redirect_server):
        """Verify wrong credentials redirect back to login."""
        session = requests.Session()
        session.verify = False

        response = session.post(
            f"{http_302_redirect_server.url}/login",
            data={"username": "wrong", "password": "wrong"},
            allow_redirects=False,
            timeout=10,
        )

        assert response.status_code == 302
        assert "login" in response.headers.get("Location", "")
        assert "error" in response.headers.get("Location", "")


class TestMetaRefreshRedirects:
    """Test meta refresh redirect handling."""

    def test_meta_refresh_detected(self, redirect_auth_server):
        """Verify meta refresh redirect is present in response."""
        session = requests.Session()
        session.verify = False

        response = session.get(
            redirect_auth_server.url,
            timeout=10,
        )

        assert response.status_code == 200
        assert 'http-equiv="refresh"' in response.text.lower()
        assert "url=/login" in response.text.lower()

    def test_meta_refresh_to_login_form(self, redirect_auth_server):
        """Verify following meta refresh leads to login form."""
        session = requests.Session()
        session.verify = False

        # Get initial page with meta refresh
        response = session.get(redirect_auth_server.url, timeout=10)
        assert "url=/login" in response.text.lower()

        # Manually follow redirect
        response = session.get(f"{redirect_auth_server.url}/login", timeout=10)
        assert response.status_code == 200
        assert 'type="password"' in response.text.lower()

    def test_login_after_meta_refresh(self, redirect_auth_server):
        """Verify login works after following meta refresh."""
        session = requests.Session()
        session.verify = False

        # Follow redirect to login
        session.get(f"{redirect_auth_server.url}/login", timeout=10)

        # Login (session cookies are what matters, not response)
        _ = session.post(
            f"{redirect_auth_server.url}/login",
            data={"user": "admin", "pass": "pw"},
            allow_redirects=True,
            timeout=10,
        )

        # Should have session cookie
        assert len(session.cookies) > 0

        # Access data
        response = session.get(f"{redirect_auth_server.url}/status", timeout=10)
        assert "Cable Modem Status" in response.text


class TestRedirectChains:
    """Test handling of redirect chains."""

    def test_cookie_persistence_through_redirects(self, http_302_redirect_server):
        """Verify cookies persist through redirect chain."""
        session = requests.Session()
        session.verify = False

        # Login (sets cookie) -> redirects to /data
        session.post(
            f"{http_302_redirect_server.url}/login",
            data={"username": "admin", "password": "pw"},
            allow_redirects=True,
            timeout=10,
        )

        # Cookies should be preserved
        assert len(session.cookies) > 0

        # Subsequent requests should work
        response = session.get(f"{http_302_redirect_server.url}/data", timeout=10)
        assert "Cable Modem Status" in response.text

    def test_redirect_to_protected_page(self, http_302_redirect_server):
        """Verify redirect from protected page to login and back."""
        session = requests.Session()
        session.verify = False

        # Try to access /data - should redirect to login
        response = session.get(
            f"{http_302_redirect_server.url}/data",
            allow_redirects=True,
            timeout=10,
        )
        assert 'type="password"' in response.text.lower()

        # Login
        session.post(
            f"{http_302_redirect_server.url}/login",
            data={"username": "admin", "password": "pw"},
            allow_redirects=True,
            timeout=10,
        )

        # Now /data should work
        response = session.get(f"{http_302_redirect_server.url}/data", timeout=10)
        assert "Cable Modem Status" in response.text


class TestRedirectLoopPrevention:
    """Test that redirect loops are handled properly."""

    def test_requests_handles_redirect_limit(self, http_302_redirect_server):
        """Verify requests library handles excessive redirects."""
        session = requests.Session()
        session.verify = False
        session.max_redirects = 5

        # This shouldn't hang or cause issues
        response = session.get(
            http_302_redirect_server.url,
            allow_redirects=True,
            timeout=10,
        )

        # Should end up somewhere valid
        assert response.status_code == 200
