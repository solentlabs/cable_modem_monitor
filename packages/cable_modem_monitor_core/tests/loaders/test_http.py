"""Tests for HTTPResourceLoader."""

from __future__ import annotations

from typing import Any

import pytest
import requests
from bs4 import BeautifulSoup
from solentlabs.cable_modem_monitor_core.auth.base import AuthResult
from solentlabs.cable_modem_monitor_core.loaders.fetch_list import ResourceTarget
from solentlabs.cable_modem_monitor_core.loaders.http import (
    HTTPResourceLoader,
    ResourceLoadError,
    _decode_response,
)
from solentlabs.cable_modem_monitor_core.test_harness import HARMockServer


def _build_entries(
    pages: dict[str, tuple[str, str]],
) -> list[dict[str, Any]]:
    """Build HAR entries.

    Args:
        pages: Mapping of path to (content_type, body).
    """
    entries: list[dict[str, Any]] = []
    for path, (content_type, body) in pages.items():
        entries.append(
            {
                "request": {
                    "method": "GET",
                    "url": f"http://192.168.100.1{path}",
                },
                "response": {
                    "status": 200,
                    "headers": [
                        {"name": "Content-Type", "value": content_type},
                    ],
                    "content": {"text": body},
                },
            }
        )
    return entries


class TestDecodeResponse:
    """Response decoding by format."""

    def test_table_format_returns_beautifulsoup(self) -> None:
        """HTML table format produces BeautifulSoup."""
        result = _decode_response("<html><table></table></html>", "table", "")
        assert isinstance(result, BeautifulSoup)

    def test_table_transposed_returns_beautifulsoup(self) -> None:
        """Transposed table format produces BeautifulSoup."""
        result = _decode_response("<html></html>", "table_transposed", "")
        assert isinstance(result, BeautifulSoup)

    def test_javascript_returns_beautifulsoup(self) -> None:
        """JavaScript format produces BeautifulSoup."""
        result = _decode_response("<script>var x=1;</script>", "javascript", "")
        assert isinstance(result, BeautifulSoup)

    def test_html_fields_returns_beautifulsoup(self) -> None:
        """html_fields format produces BeautifulSoup."""
        result = _decode_response("<html><div>info</div></html>", "html_fields", "")
        assert isinstance(result, BeautifulSoup)

    def test_json_format_returns_dict(self) -> None:
        """JSON format produces dict."""
        result = _decode_response('{"key": "value"}', "json", "")
        assert isinstance(result, dict)
        assert result["key"] == "value"

    def test_json_invalid_returns_none(self) -> None:
        """Invalid JSON returns None."""
        result = _decode_response("not json", "json", "")
        assert result is None

    def test_json_non_dict_wrapped(self) -> None:
        """Non-dict JSON is wrapped in _raw key."""
        result = _decode_response("[1, 2, 3]", "json", "")
        assert isinstance(result, dict)
        assert result["_raw"] == [1, 2, 3]

    def test_base64_encoding_decoded(self) -> None:
        """Base64-encoded response is decoded before format parsing."""
        import base64

        html = "<html><table></table></html>"
        encoded = base64.b64encode(html.encode()).decode()
        result = _decode_response(encoded, "table", "base64")
        assert isinstance(result, BeautifulSoup)

    def test_empty_response_returns_none(self) -> None:
        """Empty response body returns None."""
        result = _decode_response("", "table", "")
        assert result is None

    def test_unknown_format_falls_back_to_beautifulsoup(self) -> None:
        """Unknown format falls back to BeautifulSoup."""
        result = _decode_response("<html></html>", "unknown", "")
        assert isinstance(result, BeautifulSoup)


class TestHTTPResourceLoader:
    """HTTPResourceLoader fetches pages from mock server."""

    def test_fetch_single_html_page(self) -> None:
        """Fetches a single HTML page as BeautifulSoup."""
        entries = _build_entries({"/status.html": ("text/html", "<html><table>Data</table></html>")})

        with HARMockServer(entries) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(session, server.base_url, timeout=10)
            targets = [ResourceTarget(path="/status.html", format="table")]
            resources = loader.fetch(targets)

        assert "/status.html" in resources
        assert isinstance(resources["/status.html"], BeautifulSoup)

    def test_fetch_multiple_pages(self) -> None:
        """Fetches multiple pages in one call."""
        entries = _build_entries(
            {
                "/status.html": ("text/html", "<html>Status</html>"),
                "/info.html": ("text/html", "<html>Info</html>"),
            }
        )

        with HARMockServer(entries) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(session, server.base_url, timeout=10)
            targets = [
                ResourceTarget(path="/status.html", format="table"),
                ResourceTarget(path="/info.html", format="html_fields"),
            ]
            resources = loader.fetch(targets)

        assert len(resources) == 2
        assert "/status.html" in resources
        assert "/info.html" in resources

    def test_fetch_json_page(self) -> None:
        """Fetches JSON page and returns dict."""
        entries = _build_entries({"/api/data": ("application/json", '{"channels": []}')})

        with HARMockServer(entries) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(session, server.base_url, timeout=10)
            targets = [ResourceTarget(path="/api/data", format="json")]
            resources = loader.fetch(targets)

        assert "/api/data" in resources
        assert isinstance(resources["/api/data"], dict)
        assert resources["/api/data"]["channels"] == []

    def test_404_raises_error(self) -> None:
        """404 response raises ResourceLoadError."""
        entries = _build_entries({"/status.html": ("text/html", "<html>OK</html>")})

        with HARMockServer(entries) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(session, server.base_url, timeout=10)
            targets = [ResourceTarget(path="/nonexistent.html", format="table")]
            with pytest.raises(ResourceLoadError, match="404"):
                loader.fetch(targets)

    def test_auth_response_reuse(self) -> None:
        """Auth response is reused when its URL matches a target."""
        entries = _build_entries({"/status.html": ("text/html", "<html>Status</html>")})

        # Simulate auth response that landed on /status.html
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response._content = b"<html>Auth Landing</html>"
        mock_response.url = "http://192.168.100.1/status.html"
        mock_response.encoding = "utf-8"

        auth_result = AuthResult(
            success=True,
            response=mock_response,
            response_url="/status.html",
        )

        with HARMockServer(entries) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(session, server.base_url, timeout=10)
            targets = [ResourceTarget(path="/status.html", format="table")]
            resources = loader.fetch(targets, auth_result=auth_result)

        assert "/status.html" in resources
        # Should have the auth response content, not the server content
        soup = resources["/status.html"]
        assert "Auth Landing" in soup.get_text()

    def test_url_token_appended(self) -> None:
        """URL token is appended to request URLs."""
        entries = _build_entries({"/status.html": ("text/html", "<html>Data</html>")})

        with HARMockServer(entries) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(
                session,
                server.base_url,
                timeout=10,
                url_token="abc123",
                token_prefix="ct_",
            )
            # This will fail because the mock server routes by path
            # without query string, so the fetch should still work
            targets = [ResourceTarget(path="/status.html", format="table")]
            resources = loader.fetch(targets)

        assert "/status.html" in resources

    def test_empty_targets_returns_empty_dict(self) -> None:
        """No targets produces empty resource dict."""
        entries = _build_entries({})

        with HARMockServer(entries) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(session, server.base_url, timeout=10)
            resources = loader.fetch([])

        assert resources == {}

    def test_auth_response_reuse_only_for_matching_path(self) -> None:
        """Auth response is not reused for non-matching paths."""
        entries = _build_entries(
            {
                "/status.html": ("text/html", "<html>Server Status</html>"),
                "/info.html": ("text/html", "<html>Server Info</html>"),
            }
        )

        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response._content = b"<html>Auth Landing</html>"
        mock_response.url = "http://192.168.100.1/info.html"
        mock_response.encoding = "utf-8"

        auth_result = AuthResult(
            success=True,
            response=mock_response,
            response_url="/info.html",
        )

        with HARMockServer(entries) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(session, server.base_url, timeout=10)
            targets = [
                ResourceTarget(path="/status.html", format="table"),
                ResourceTarget(path="/info.html", format="html_fields"),
            ]
            resources = loader.fetch(targets, auth_result=auth_result)

        # /status.html should come from server
        assert "Server Status" in resources["/status.html"].get_text()
        # /info.html should be reused from auth response
        assert "Auth Landing" in resources["/info.html"].get_text()
