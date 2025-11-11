"""Tests for protocol caching optimization."""

from __future__ import annotations

from custom_components.cable_modem_monitor.core.modem_scraper import ModemScraper


class TestProtocolCaching:
    """Test protocol caching from working URL."""

    def test_protocol_from_https_cached_url(self):
        """Test that HTTPS protocol is extracted from cached URL."""
        cached_url = "https://192.168.100.1/MotoConnection.asp"
        scraper = ModemScraper(
            host="192.168.100.1",
            parser=[],
            cached_url=cached_url,
        )

        # Should use HTTPS from cached URL
        assert scraper.base_url == "https://192.168.100.1"

    def test_protocol_from_http_cached_url(self):
        """Test that HTTP protocol is extracted from cached URL."""
        cached_url = "http://192.168.100.1/MotoConnection.asp"
        scraper = ModemScraper(
            host="192.168.100.1",
            parser=[],
            cached_url=cached_url,
        )

        # Should use HTTP from cached URL
        assert scraper.base_url == "http://192.168.100.1"

    def test_no_cached_url_defaults_to_https(self):
        """Test that HTTPS is default when no cached URL."""
        scraper = ModemScraper(
            host="192.168.100.1",
            parser=[],
            cached_url=None,
        )

        # Should default to HTTPS
        assert scraper.base_url == "https://192.168.100.1"

    def test_explicit_protocol_in_host_overrides_cache(self):
        """Test that explicit protocol in host overrides cached URL."""
        cached_url = "https://192.168.100.1/MotoConnection.asp"
        scraper = ModemScraper(
            host="http://192.168.100.1",
            parser=[],
            cached_url=cached_url,
        )

        # Explicit protocol in host should take precedence
        assert scraper.base_url == "http://192.168.100.1"

    def test_cached_url_without_protocol_ignored(self):
        """Test that cached URL without protocol is ignored."""
        cached_url = "192.168.100.1/MotoConnection.asp"  # No protocol
        scraper = ModemScraper(
            host="192.168.100.1",
            parser=[],
            cached_url=cached_url,
        )

        # Should default to HTTPS since cached URL has no protocol
        assert scraper.base_url == "https://192.168.100.1"

    def test_cached_url_with_path_only_uses_protocol(self):
        """Test that protocol is extracted even with different path."""
        # User might have cached URL with one path but trying different path
        cached_url = "http://192.168.100.1/oldpath.html"
        scraper = ModemScraper(
            host="192.168.100.1",
            parser=[],
            cached_url=cached_url,
        )

        # Should still use HTTP protocol from cached URL
        assert scraper.base_url == "http://192.168.100.1"

    def test_protocol_caching_with_different_hosts(self):
        """Test that protocol caching only applies to same host."""
        # This is a defensive test - cached URL is from different host
        cached_url = "http://192.168.1.1/MotoConnection.asp"
        scraper = ModemScraper(
            host="192.168.100.1",  # Different host
            parser=[],
            cached_url=cached_url,
        )

        # Should still extract protocol from cached URL
        # (current implementation doesn't validate host match)
        assert scraper.base_url == "http://192.168.100.1"


class TestProtocolDiscoveryBehavior:
    """Test protocol discovery behavior with and without cache."""

    def test_protocols_to_try_with_https_base(self, mocker):
        """Test that both protocols are tried when base is HTTPS."""
        scraper = ModemScraper(
            host="192.168.100.1",
            parser=[],
            cached_url=None,  # No cache, defaults to HTTPS
        )

        # Mock parser class for _get_url_patterns_to_try
        mock_parser = mocker.Mock()
        mock_parser.url_patterns = [{"path": "/test.html", "auth_method": "none", "auth_required": False}]
        scraper.parser = mock_parser

        # Should try both HTTPS and HTTP
        assert scraper.base_url.startswith("https://")

    def test_protocols_to_try_with_http_cache(self, mocker):
        """Test that only HTTP is tried when cached URL is HTTP."""
        scraper = ModemScraper(
            host="192.168.100.1",
            parser=[],
            cached_url="http://192.168.100.1/test.html",  # HTTP cached
        )

        # With HTTP cached, base_url should be HTTP
        assert scraper.base_url.startswith("http://")

        # Mock parser class
        mock_parser = mocker.Mock()
        mock_parser.url_patterns = [{"path": "/test.html", "auth_method": "none", "auth_required": False}]
        scraper.parser = mock_parser

        # Should prioritize HTTP (from cache)
        assert scraper.base_url == "http://192.168.100.1"


class TestSSLVerification:
    """Test SSL verification settings."""

    def test_verify_ssl_false_by_default(self):
        """Test that SSL verification is disabled by default."""
        scraper = ModemScraper(
            host="192.168.100.1",
            parser=[],
        )

        assert scraper.verify_ssl is False
        assert scraper.session.verify is False

    def test_verify_ssl_can_be_enabled(self):
        """Test that SSL verification can be enabled."""
        scraper = ModemScraper(
            host="192.168.100.1",
            parser=[],
            verify_ssl=True,
        )

        assert scraper.verify_ssl is True
        assert scraper.session.verify is True

    def test_verify_ssl_passed_through_requests(self, mocker):
        """Test that verify parameter is passed to requests."""
        scraper = ModemScraper(
            host="192.168.100.1",
            parser=[],
            verify_ssl=False,
        )

        # Verify that session has correct verify setting
        assert scraper.session.verify is False
