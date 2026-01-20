"""Tests for HTMLLoader."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.loaders.html import HTMLLoader


class TestHTMLLoader:
    """Tests for HTMLLoader."""

    def test_fetches_pages_from_pages_data(self):
        """Fetches all unique paths from pages.data."""
        session = MagicMock()
        response = MagicMock()
        response.ok = True
        response.text = "<html><body>Test</body></html>"
        session.get.return_value = response

        config = {
            "pages": {
                "data": {
                    "downstream_channels": "/page1.html",
                    "upstream_channels": "/page1.html",  # Duplicate
                    "system_info": "/page2.html",
                }
            }
        }

        fetcher = HTMLLoader(
            session=session,
            base_url="http://192.168.100.1",
            modem_config=config,
        )

        resources = fetcher.fetch()

        # Should fetch 2 unique pages (not 3)
        assert session.get.call_count == 2
        assert "/page1.html" in resources
        assert "/page2.html" in resources
        assert isinstance(resources["/page1.html"], BeautifulSoup)

    def test_skips_hnap_endpoints(self):
        """Skips paths containing /HNAP."""
        session = MagicMock()
        response = MagicMock()
        response.ok = True
        response.text = "<html>Test</html>"
        session.get.return_value = response

        config = {
            "pages": {
                "data": {
                    "downstream_channels": "/HNAP1/",
                    "system_info": "/status.html",
                }
            }
        }

        fetcher = HTMLLoader(
            session=session,
            base_url="http://192.168.100.1",
            modem_config=config,
        )

        resources = fetcher.fetch()

        # Should only fetch status.html, not HNAP
        assert session.get.call_count == 1
        assert "/status.html" in resources
        assert "/HNAP1/" not in resources


class TestHTMLLoaderUrlToken:
    """Tests for HTMLLoader URL token authentication."""

    def test_appends_token_to_url(self):
        """Appends session token to URL for url_token auth."""
        session = MagicMock()

        response = MagicMock()
        response.ok = True
        response.text = "<html>Test</html>"
        session.get.return_value = response

        config = {"pages": {"data": {"status": "/status.html"}}}
        url_token_config = {"session_cookie": "sessionId", "token_prefix": "ct_"}

        fetcher = HTMLLoader(
            session=session,
            base_url="http://192.168.100.1",
            modem_config=config,
            url_token_config=url_token_config,
        )

        # Mock get_cookie_safe to return our token
        with patch(
            "custom_components.cable_modem_monitor.core.loaders.html.get_cookie_safe",
            return_value="abc123",
        ):
            fetcher.fetch()

        # Check URL includes token
        session.get.assert_called_once()
        call_url = session.get.call_args[0][0]
        assert "ct_abc123" in call_url

    def test_handles_url_with_existing_query_params(self):
        """Handles URLs that already have query parameters."""
        # Test internal URL building logic
        session = MagicMock()
        session.cookies = []

        config = {"pages": {"data": {}}}
        url_token_config = {"session_cookie": "sessionId", "token_prefix": "ct_"}

        fetcher = HTMLLoader(
            session=session,
            base_url="http://192.168.100.1",
            modem_config=config,
            url_token_config=url_token_config,
        )

        # Without token
        url = fetcher._build_authenticated_url("/page.html?foo=bar")
        assert url == "http://192.168.100.1/page.html?foo=bar"

        # With token - should use & separator
        with patch(
            "custom_components.cable_modem_monitor.core.loaders.html.get_cookie_safe",
            return_value="abc123",
        ):
            url = fetcher._build_authenticated_url("/page.html?foo=bar")
            assert url == "http://192.168.100.1/page.html?foo=bar&ct_abc123"

    def test_no_token_appended_when_cookie_not_found(self):
        """No token appended when session cookie is not found."""
        session = MagicMock()
        session.cookies = []

        response = MagicMock()
        response.ok = True
        response.text = "<html>Test</html>"
        session.get.return_value = response

        config = {"pages": {"data": {"status": "/status.html"}}}
        url_token_config = {"session_cookie": "sessionId", "token_prefix": "ct_"}

        fetcher = HTMLLoader(
            session=session,
            base_url="http://192.168.100.1",
            modem_config=config,
            url_token_config=url_token_config,
        )

        with patch(
            "custom_components.cable_modem_monitor.core.loaders.html.get_cookie_safe",
            return_value=None,
        ):
            fetcher.fetch()

        # URL should not have token
        call_url = session.get.call_args[0][0]
        assert "ct_" not in call_url
