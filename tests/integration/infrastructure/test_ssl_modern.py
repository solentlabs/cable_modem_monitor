"""Tests for HTTPS connections with modern SSL ciphers.

These tests verify that the default SSL behavior works correctly
for modems with modern firmware.
"""

from __future__ import annotations

import pytest
import requests

from custom_components.cable_modem_monitor.core.ssl_adapter import (
    LegacySSLAdapter,
    create_session_with_ssl_handling,
    detect_legacy_ssl_needed,
)


@pytest.mark.integration
class TestModernSSL:
    """Tests for HTTPS with modern SSL ciphers."""

    def test_modern_ssl_connection_succeeds(self, https_modern_server):
        """Verify connection to HTTPS server with modern ciphers works."""
        session = requests.Session()
        response = session.get(
            https_modern_server.url,
            timeout=5,
            verify=False,  # Self-signed cert
        )
        assert response.status_code == 200
        assert b"Cable Modem Status" in response.content

    def test_modern_ssl_without_legacy_adapter(self, https_modern_server):
        """Verify modern SSL works without LegacySSLAdapter mounted."""
        session = create_session_with_ssl_handling(
            https_modern_server.url,
            legacy_ssl=False,
        )
        response = session.get(
            https_modern_server.url,
            timeout=5,
            verify=False,
        )
        assert response.status_code == 200

    def test_modern_ssl_with_legacy_adapter_still_works(self, https_modern_server):
        """Verify that mounting LegacySSLAdapter doesn't break modern connections.

        The adapter should be backwards compatible - it allows legacy ciphers
        but should still work with modern ones.
        """
        session = requests.Session()
        session.mount("https://", LegacySSLAdapter())
        response = session.get(
            https_modern_server.url,
            timeout=5,
            verify=False,
        )
        assert response.status_code == 200

    def test_detect_legacy_ssl_returns_false_for_modern_server(self, https_modern_server):
        """Verify auto-detection correctly identifies modern SSL servers."""
        needs_legacy = detect_legacy_ssl_needed(https_modern_server.url)
        assert needs_legacy is False

    def test_create_session_respects_legacy_ssl_flag(self, https_modern_server):
        """Verify create_session_with_ssl_handling honors the legacy_ssl parameter."""
        # With legacy_ssl=False, should work on modern server
        session = create_session_with_ssl_handling(
            https_modern_server.url,
            legacy_ssl=False,
        )
        response = session.get(
            https_modern_server.url,
            timeout=5,
            verify=False,
        )
        assert response.status_code == 200

        # With legacy_ssl=True, should also work (backwards compatible)
        session_legacy = create_session_with_ssl_handling(
            https_modern_server.url,
            legacy_ssl=True,
        )
        response = session_legacy.get(
            https_modern_server.url,
            timeout=5,
            verify=False,
        )
        assert response.status_code == 200
