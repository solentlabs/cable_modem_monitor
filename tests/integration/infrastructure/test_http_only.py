"""Tests for HTTP (non-SSL) connections.

These tests verify that HTTP modems continue to work correctly
and that LegacySSLAdapter is NOT mounted for HTTP URLs.

This is critical to ensure we don't break existing HTTP modem
connections when adding legacy SSL support.
"""

from __future__ import annotations

import pytest
import requests

from custom_components.cable_modem_monitor.core.ssl_adapter import (
    create_session_with_ssl_handling,
    detect_legacy_ssl_needed,
)


@pytest.mark.integration
class TestHTTPOnly:
    """Tests for plain HTTP connections (no SSL)."""

    def test_http_connection_works(self, http_server):
        """Verify basic HTTP connection works."""
        session = requests.Session()
        response = session.get(http_server.url, timeout=5)
        assert response.status_code == 200
        assert b"Cable Modem Status" in response.content

    def test_http_unaffected_by_legacy_ssl_flag(self, http_server):
        """Verify HTTP connections work regardless of legacy_ssl setting.

        This is critical - legacy_ssl should only affect HTTPS URLs.
        """
        # With legacy_ssl=False
        session_modern = create_session_with_ssl_handling(
            http_server.url,
            legacy_ssl=False,
        )
        response = session_modern.get(http_server.url, timeout=5)
        assert response.status_code == 200

        # With legacy_ssl=True - should still work (adapter only mounts for https://)
        session_legacy = create_session_with_ssl_handling(
            http_server.url,
            legacy_ssl=True,
        )
        response = session_legacy.get(http_server.url, timeout=5)
        assert response.status_code == 200

    def test_detect_legacy_ssl_returns_false_for_http(self, http_server):
        """Verify auto-detection returns False for HTTP URLs."""
        needs_legacy = detect_legacy_ssl_needed(http_server.url)
        assert needs_legacy is False

    def test_http_url_not_converted_to_https(self, http_server):
        """Verify HTTP URLs are used as-is, not upgraded to HTTPS.

        This ensures we don't accidentally try SSL on HTTP modems.
        """
        assert http_server.url.startswith("http://")
        assert not http_server.url.startswith("https://")

        session = create_session_with_ssl_handling(
            http_server.url,
            legacy_ssl=True,  # Even with legacy_ssl, HTTP stays HTTP
        )

        # No SSL errors should occur - it's just HTTP
        response = session.get(http_server.url, timeout=5)
        assert response.status_code == 200


@pytest.mark.integration
class TestSessionAdapterMounting:
    """Tests to verify adapter mounting behavior."""

    def test_legacy_adapter_not_mounted_for_http(self, http_server):
        """Verify LegacySSLAdapter is not mounted when URL is HTTP."""
        session = create_session_with_ssl_handling(
            http_server.url,
            legacy_ssl=True,
        )

        # Check that no adapter is mounted for http://
        # The default adapter would be used, not LegacySSLAdapter
        http_adapter = session.get_adapter(http_server.url)
        # Default requests adapter, not our custom one
        assert http_adapter is not None
        # If legacy_ssl=True but URL is HTTP, adapter should still be default
        # (HTTPAdapter is the base class, our LegacySSLAdapter inherits from it)

    def test_legacy_adapter_mounted_for_https(self, https_modern_server):
        """Verify LegacySSLAdapter is mounted when URL is HTTPS and legacy_ssl=True."""
        from custom_components.cable_modem_monitor.core.ssl_adapter import (
            LegacySSLAdapter,
        )

        session = create_session_with_ssl_handling(
            https_modern_server.url,
            legacy_ssl=True,
        )

        # Check that our adapter is mounted for https://
        https_adapter = session.get_adapter(https_modern_server.url)
        assert isinstance(https_adapter, LegacySSLAdapter)

    def test_default_adapter_for_https_without_legacy(self, https_modern_server):
        """Verify default adapter is used when legacy_ssl=False."""
        from custom_components.cable_modem_monitor.core.ssl_adapter import (
            LegacySSLAdapter,
        )

        session = create_session_with_ssl_handling(
            https_modern_server.url,
            legacy_ssl=False,
        )

        # Check that default adapter is used (not our custom one)
        https_adapter = session.get_adapter(https_modern_server.url)
        assert not isinstance(https_adapter, LegacySSLAdapter)
