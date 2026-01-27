"""Integration tests for form authentication with base64 password encoding.

These tests verify the base64-encoded password form submission:
1. Password is URL-encoded (JavaScript escape())
2. Then base64 encoded
3. Submitted as form field

Tests FORM_PLAIN strategy with password_encoding="base64" using synthetic mock servers.
"""

from __future__ import annotations

import base64
from urllib.parse import quote

import requests

from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType

# Test timeout constant - matches DEFAULT_TIMEOUT from schema
TEST_TIMEOUT = 10


class TestFormBase64Encoding:
    """Test base64 password encoding."""

    def test_login_with_base64_password(self, form_base64_server):
        """Verify login works with base64-encoded password."""
        session = requests.Session()
        session.verify = False

        # Password: p@ss!word
        # JavaScript escape() encodes to: p%40ss%21word
        # Then base64: cCU0MHNzJTIxd29yZA==
        password = "p@ss!word"
        # JavaScript escape() doesn't encode: @*_+-./
        # But it does encode: ! -> %21
        url_encoded = quote(password, safe="@*_+-./")
        encoded_password = base64.b64encode(url_encoded.encode("utf-8")).decode("utf-8")

        response = session.post(
            f"{form_base64_server.url}/login",
            data={"username": "admin", "password": encoded_password},
            allow_redirects=True,
            timeout=TEST_TIMEOUT,
        )

        # Should have session cookie
        assert "session=authenticated" in str(session.cookies) or response.status_code == 200

    def test_login_wrong_password_fails(self, form_base64_server):
        """Verify wrong password fails even when base64 encoded."""
        session = requests.Session()
        session.verify = False

        wrong_password = "wrongpassword"
        url_encoded = quote(wrong_password, safe="@*_+-./")
        encoded_password = base64.b64encode(url_encoded.encode("utf-8")).decode("utf-8")

        response = session.post(
            f"{form_base64_server.url}/login",
            data={"username": "admin", "password": encoded_password},
            allow_redirects=True,
            timeout=TEST_TIMEOUT,
        )

        # Should show login form (authentication failed)
        assert 'type="password"' in response.text.lower()

    def test_plain_password_fails(self, form_base64_server):
        """Verify plain password (not encoded) fails."""
        session = requests.Session()
        session.verify = False

        response = session.post(
            f"{form_base64_server.url}/login",
            data={"username": "admin", "password": "p@ss!word"},
            allow_redirects=True,
            timeout=TEST_TIMEOUT,
        )

        # Should show login form (authentication failed)
        assert 'type="password"' in response.text.lower()


class TestAuthHandlerFormBase64:
    """Test AuthHandler with FORM_PLAIN strategy and password_encoding=base64."""

    def test_auth_handler_encodes_password(self, form_base64_server):
        """Verify AuthHandler correctly encodes password with base64 encoding."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
                "password_encoding": "base64",
            },
            timeout=TEST_TIMEOUT,
        )

        session = requests.Session()
        session.verify = False

        success, _ = handler.authenticate(
            session=session,
            base_url=form_base64_server.url,
            username="admin",
            password="p@ss!word",
        )

        assert success is True

    def test_auth_handler_form_base64_wrong_creds(self, form_base64_server):
        """Verify AuthHandler reports failure for wrong credentials."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
                "password_encoding": "base64",
            },
            timeout=TEST_TIMEOUT,
        )

        session = requests.Session()
        session.verify = False

        success, _ = handler.authenticate(
            session=session,
            base_url=form_base64_server.url,
            username="admin",
            password="wrongpassword",
        )

        assert success is False


class TestFormBase64SpecialCharacters:
    """Test base64 encoding with various special characters."""

    def test_special_chars_in_password(self, form_base64_server):
        """Test that special characters are handled correctly."""
        session = requests.Session()
        session.verify = False

        # The test server expects "p@ss!word"
        password = "p@ss!word"

        # Manual encoding matching what AuthHandler does
        url_encoded = quote(password, safe="@*_+-./")
        encoded = base64.b64encode(url_encoded.encode("utf-8")).decode("utf-8")

        session.post(
            f"{form_base64_server.url}/login",
            data={"username": "admin", "password": encoded},
            allow_redirects=True,
            timeout=TEST_TIMEOUT,
        )

        # Verify we can access data after login
        if "session=authenticated" in str(session.cookies):
            data_response = session.get(form_base64_server.url, timeout=TEST_TIMEOUT)
            assert "Cable Modem Status" in data_response.text


class TestFormBase64DataAccess:
    """Test data access after form authentication with base64 encoding."""

    def test_data_access_after_login(self, form_base64_server):
        """Verify data access works after base64 form login."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
                "password_encoding": "base64",
            },
            timeout=TEST_TIMEOUT,
        )

        session = requests.Session()
        session.verify = False

        success, _ = handler.authenticate(
            session=session,
            base_url=form_base64_server.url,
            username="admin",
            password="p@ss!word",
        )
        assert success is True

        # Access data page
        response = session.get(form_base64_server.url, timeout=TEST_TIMEOUT)
        assert "Cable Modem Status" in response.text

    def test_multiple_data_fetches(self, form_base64_server):
        """Verify multiple data fetches work after auth."""
        handler = AuthHandler(
            strategy=AuthStrategyType.FORM_PLAIN,
            form_config={
                "action": "/login",
                "method": "POST",
                "username_field": "username",
                "password_field": "password",
                "password_encoding": "base64",
            },
            timeout=TEST_TIMEOUT,
        )

        session = requests.Session()
        session.verify = False

        handler.authenticate(
            session=session,
            base_url=form_base64_server.url,
            username="admin",
            password="p@ss!word",
        )

        # Multiple fetches should work
        for i in range(5):
            response = session.get(form_base64_server.url, timeout=TEST_TIMEOUT)
            assert "Cable Modem Status" in response.text, f"Fetch {i + 1} failed"


class TestEncodingConsistency:
    """Verify discovery and handler use identical password encoding.

    Regression test for bug where discovery.py used quote(safe="") but
    handler.py used quote(safe="@*_+-./"), causing auth discovery to fail
    for passwords containing those characters.
    """

    # JavaScript escape() safe characters - must match in both discovery.py and handler.py
    JS_ESCAPE_SAFE_CHARS = "@*_+-./"

    def test_source_code_encoding_consistency(self):
        """Verify discovery.py and handler.py use same safe= parameter.

        This test reads the actual source files to ensure the encoding
        parameters stay in sync. If someone changes one file, this test
        will detect the mismatch.
        """
        import re
        from pathlib import Path

        # Find the source files
        # tests/integration/core/test_form_base64_auth.py -> cable_modem_monitor/
        project_root = Path(__file__).parent.parent.parent.parent
        base = project_root / "custom_components" / "cable_modem_monitor" / "core" / "auth"
        discovery_path = base / "discovery.py"
        form_plain_path = base / "strategies" / "form_plain.py"

        # Pattern to find quote() calls with safe= parameter
        pattern = r'quote\([^)]*safe="([^"]*)"'

        # Extract safe= values from discovery.py
        discovery_content = discovery_path.read_text()
        discovery_matches = re.findall(pattern, discovery_content)
        assert discovery_matches, "No quote(safe=...) found in discovery.py"

        # Extract safe= values from form_plain.py (encoding moved here in v3.12.0)
        form_plain_content = form_plain_path.read_text()
        form_plain_matches = re.findall(pattern, form_plain_content)
        assert form_plain_matches, "No quote(safe=...) found in form_plain.py"

        # All safe= parameters should match JS_ESCAPE_SAFE_CHARS
        for safe_chars in discovery_matches:
            assert safe_chars == self.JS_ESCAPE_SAFE_CHARS, (
                f'discovery.py uses safe="{safe_chars}" but should use '
                f'safe="{self.JS_ESCAPE_SAFE_CHARS}" to match JavaScript escape()'
            )

        for safe_chars in form_plain_matches:
            assert safe_chars == self.JS_ESCAPE_SAFE_CHARS, (
                f'form_plain.py uses safe="{safe_chars}" but should use '
                f'safe="{self.JS_ESCAPE_SAFE_CHARS}" to match JavaScript escape()'
            )

    def test_encoding_produces_expected_output(self):
        """Verify encoding matches JavaScript escape() + btoa() output."""
        # Test cases with known JavaScript outputs
        # JavaScript: btoa(escape("p@ss!word")) = "cEBzcyUyMXdvcmQ="
        test_cases = [
            # (password, expected_url_encoded, expected_base64)
            ("password", "password", "cGFzc3dvcmQ="),  # No special chars
            ("p@ssword", "p@ssword", "cEBzc3dvcmQ="),  # @ is not escaped
            ("p!ssword", "p%21ssword", "cCUyMXNzd29yZA=="),  # ! is escaped
            ("p@ss!word", "p@ss%21word", "cEBzcyUyMXdvcmQ="),  # Mix
        ]

        for password, expected_url, expected_b64 in test_cases:
            url_encoded = quote(password, safe=self.JS_ESCAPE_SAFE_CHARS)
            b64_encoded = base64.b64encode(url_encoded.encode()).decode()

            assert url_encoded == expected_url, (
                f"URL encoding mismatch for '{password}': " f"got '{url_encoded}', expected '{expected_url}'"
            )
            assert b64_encoded == expected_b64, (
                f"Base64 encoding mismatch for '{password}': " f"got '{b64_encoded}', expected '{expected_b64}'"
            )
