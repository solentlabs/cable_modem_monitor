"""Tests for HTML Crawler."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from custom_components.cable_modem_monitor.lib.html_crawler import HTMLCrawler


@pytest.fixture
def mock_session():
    """Create a mock requests session."""
    session = MagicMock(spec=requests.Session)
    session.verify = False
    return session


class TestHTMLCrawlerInit:
    """Test HTMLCrawler initialization."""

    def test_init_with_session(self, mock_session):
        """Test initialization with provided session."""
        crawler = HTMLCrawler(mock_session)

        assert crawler.session is mock_session

    def test_init_creates_session(self):
        """Test that crawler creates session if none provided."""
        crawler = HTMLCrawler()

        assert crawler.session is not None
        assert isinstance(crawler.session, requests.Session)


class TestHTMLCrawlerFetch:
    """Test HTML fetching functionality."""

    def test_fetch_success(self, mock_session):
        """Test successful HTML fetch."""
        crawler = HTMLCrawler(mock_session)

        # Mock successful response
        mock_response = MagicMock()
        mock_response.text = "<html>Test Content</html>"
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        html = crawler.fetch("http://192.168.1.1/status.asp")

        assert html == "<html>Test Content</html>"
        mock_session.get.assert_called_once_with("http://192.168.1.1/status.asp", timeout=10)

    def test_fetch_handles_http_error(self, mock_session):
        """Test fetch handles HTTP errors."""
        crawler = HTMLCrawler(mock_session)

        # Mock HTTP error
        mock_session.get.side_effect = requests.HTTPError("404 Not Found")

        html = crawler.fetch("http://192.168.1.1/status.asp")

        assert html is None

    def test_fetch_handles_timeout(self, mock_session):
        """Test fetch handles timeout errors."""
        crawler = HTMLCrawler(mock_session)

        # Mock timeout
        mock_session.get.side_effect = requests.Timeout("Request timeout")

        html = crawler.fetch("http://192.168.1.1/status.asp")

        assert html is None

    def test_fetch_handles_connection_error(self, mock_session):
        """Test fetch handles connection errors."""
        crawler = HTMLCrawler(mock_session)

        # Mock connection error
        mock_session.get.side_effect = requests.ConnectionError("Failed to connect")

        html = crawler.fetch("http://192.168.1.1/status.asp")

        assert html is None

    def test_fetch_uses_custom_timeout(self, mock_session):
        """Test fetch with custom timeout."""
        crawler = HTMLCrawler(mock_session)

        mock_response = MagicMock()
        mock_response.text = "<html>Content</html>"
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        crawler.fetch("http://192.168.1.1/status.asp", timeout=5)

        call_args = mock_session.get.call_args
        assert call_args[1]["timeout"] == 5


class TestHTMLCrawlerSessionManagement:
    """Test session management functionality."""

    def test_session_persistence(self, mock_session):
        """Test that session persists across multiple fetches."""
        crawler = HTMLCrawler(mock_session)

        mock_response = MagicMock()
        mock_response.text = "<html>Content</html>"
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        crawler.fetch("http://192.168.1.1/page1.asp")
        crawler.fetch("http://192.168.1.1/page2.asp")

        # Same session used for both requests
        assert mock_session.get.call_count == 2

    def test_session_cookies_preserved(self, mock_session):
        """Test that session cookies are preserved."""
        crawler = HTMLCrawler(mock_session)

        mock_response = MagicMock()
        mock_response.text = "<html>Content</html>"
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        # Simulate cookie being set
        mock_session.cookies = {"session_id": "abc123"}

        crawler.fetch("http://192.168.1.1/status.asp")

        # Cookies should still be present
        assert mock_session.cookies == {"session_id": "abc123"}
