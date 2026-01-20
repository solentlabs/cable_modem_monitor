"""Tests for HTTPS connections requiring legacy SSL ciphers.

These tests verify that LegacySSLAdapter correctly handles connections
to servers (modems) that only support legacy TLS ciphers.

This simulates the behavior of older modem firmware
that triggers SSLV3_ALERT_HANDSHAKE_FAILURE with modern Python.

Note: Some tests depend on the system's OpenSSL configuration. Tests that
require a truly legacy-only server may be skipped on systems where modern
clients can still negotiate with legacy ciphers.
"""

from __future__ import annotations

import pytest
import requests

from custom_components.cable_modem_monitor.core.ssl_adapter import (
    LegacySSLAdapter,
    create_session_with_ssl_handling,
    detect_legacy_ssl_needed,
    is_ssl_handshake_error,
)


def _legacy_server_rejects_modern_client(url: str) -> bool:
    """Check if legacy server actually rejects modern SSL clients.

    This varies by OpenSSL configuration. Returns True if the server
    properly rejects modern clients (needed for certain tests).
    """
    session = requests.Session()
    try:
        session.get(url, timeout=5, verify=False)
        return False  # Server accepted modern client
    except requests.exceptions.SSLError:
        return True  # Server rejected modern client


@pytest.mark.integration
class TestLegacySSL:
    """Tests for HTTPS with legacy-only SSL ciphers."""

    def test_legacy_server_fails_with_modern_ssl(self, https_legacy_server):
        """Verify connection fails with default SSL settings.

        This confirms our test server correctly simulates legacy modem behavior.
        Skipped if system OpenSSL still negotiates with legacy ciphers.
        """
        if not _legacy_server_rejects_modern_client(https_legacy_server.url):
            pytest.skip("System OpenSSL negotiates with legacy ciphers; " "cannot test rejection scenario")

        session = requests.Session()
        with pytest.raises(requests.exceptions.SSLError) as exc_info:
            session.get(
                https_legacy_server.url,
                timeout=5,
                verify=False,
            )

        # Verify it's a handshake error, not some other SSL issue
        assert is_ssl_handshake_error(exc_info.value)

    def test_legacy_server_succeeds_with_legacy_adapter(self, https_legacy_server):
        """Verify LegacySSLAdapter allows connection to legacy servers."""
        session = requests.Session()
        session.mount("https://", LegacySSLAdapter())

        response = session.get(
            https_legacy_server.url,
            timeout=5,
            verify=False,
        )
        assert response.status_code == 200
        assert b"Cable Modem Status" in response.content

    def test_detect_legacy_ssl_returns_true_for_legacy_server(self, https_legacy_server):
        """Verify auto-detection correctly identifies legacy SSL servers.

        Skipped if system OpenSSL still negotiates with legacy ciphers.
        """
        if not _legacy_server_rejects_modern_client(https_legacy_server.url):
            pytest.skip("System OpenSSL negotiates with legacy ciphers; " "cannot test detection scenario")

        needs_legacy = detect_legacy_ssl_needed(https_legacy_server.url)
        assert needs_legacy is True

    def test_create_session_with_legacy_flag_works(self, https_legacy_server):
        """Verify create_session_with_ssl_handling works with legacy_ssl=True."""
        session = create_session_with_ssl_handling(
            https_legacy_server.url,
            legacy_ssl=True,
        )
        response = session.get(
            https_legacy_server.url,
            timeout=5,
            verify=False,
        )
        assert response.status_code == 200

    def test_create_session_without_legacy_flag_fails(self, https_legacy_server):
        """Verify create_session_with_ssl_handling fails without legacy_ssl=True.

        Skipped if system OpenSSL still negotiates with legacy ciphers.
        """
        if not _legacy_server_rejects_modern_client(https_legacy_server.url):
            pytest.skip("System OpenSSL negotiates with legacy ciphers; " "cannot test rejection scenario")

        session = create_session_with_ssl_handling(
            https_legacy_server.url,
            legacy_ssl=False,
        )
        with pytest.raises(requests.exceptions.SSLError):
            session.get(
                https_legacy_server.url,
                timeout=5,
                verify=False,
            )


@pytest.mark.integration
class TestSSLErrorDetection:
    """Tests for is_ssl_handshake_error helper function."""

    def test_detects_handshake_in_error(self):
        """Verify detection of 'handshake' keyword."""
        error = Exception("SSL handshake failed")
        assert is_ssl_handshake_error(error) is True

    def test_detects_sslv3_in_error(self):
        """Verify detection of 'sslv3' keyword."""
        error = Exception("SSLV3_ALERT_HANDSHAKE_FAILURE")
        assert is_ssl_handshake_error(error) is True

    def test_detects_cipher_in_error(self):
        """Verify detection of 'cipher' keyword."""
        error = Exception("no shared cipher")
        assert is_ssl_handshake_error(error) is True

    def test_detects_ssl_error_in_error(self):
        """Verify detection of 'ssl_error' keyword."""
        error = Exception("SSL_ERROR_SSL")
        assert is_ssl_handshake_error(error) is True

    def test_detects_alert_in_error(self):
        """Verify detection of 'alert' keyword."""
        error = Exception("ssl alert number 40")
        assert is_ssl_handshake_error(error) is True

    def test_ignores_unrelated_ssl_errors(self):
        """Verify non-handshake SSL errors are not flagged."""
        error = Exception("certificate verify failed")
        assert is_ssl_handshake_error(error) is False

    def test_ignores_non_ssl_errors(self):
        """Verify general errors are not flagged."""
        error = Exception("Connection refused")
        assert is_ssl_handshake_error(error) is False
