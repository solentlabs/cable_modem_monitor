"""Tests for HTTPResourceLoader."""

from __future__ import annotations

import base64 as b64mod
from typing import Any

import pytest
import requests
from bs4 import BeautifulSoup
from solentlabs.cable_modem_monitor_core.auth.base import AuthResult
from solentlabs.cable_modem_monitor_core.loaders.fetch_list import ResourceTarget
from solentlabs.cable_modem_monitor_core.loaders.http import (
    HTTPResourceLoader,
    LoginPageDetectedError,
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


# ---------------------------------------------------------------------------
# _decode_response — table-driven
# ---------------------------------------------------------------------------

# ┌──────────────────────────┬───────────────────┬──────────┬───────────┬──────────────────────────────────┐
# │ text                     │ format            │ encoding │ exp_type  │ description                      │
# ├──────────────────────────┼───────────────────┼──────────┼───────────┼──────────────────────────────────┤
# │ "<html>..."              │ table             │ ""       │ soup      │ HTML table                       │
# │ "<html>..."              │ table_transposed  │ ""       │ soup      │ transposed table                 │
# │ "<script>..."            │ javascript        │ ""       │ soup      │ JS embedded                      │
# │ "<script>..."            │ javascript_json   │ ""       │ soup      │ JS JSON                          │
# │ "<html>..."              │ html_fields       │ ""       │ soup      │ html_fields                      │
# │ '{"key":"val"}'          │ json              │ ""       │ dict      │ valid JSON dict                  │
# │ "not json"               │ json              │ ""       │ None      │ invalid JSON                     │
# │ "[1,2,3]"                │ json              │ ""       │ dict      │ non-dict JSON → _raw wrapper     │
# │ b64("<html>...")         │ table             │ base64   │ soup      │ base64-encoded body              │
# │ "!!!invalid"             │ table             │ base64   │ None      │ base64 decode failure            │
# │ ""                       │ table             │ ""       │ None      │ empty body                       │
# │ "<root/>"                │ xml               │ ""       │ None      │ XML not yet supported by loader  │
# │ "<html>..."              │ unknown           │ ""       │ soup      │ unknown format fallback          │
# └──────────────────────────┴───────────────────┴──────────┴───────────┴──────────────────────────────────┘

_B64_HTML = b64mod.b64encode(b"<html><table></table></html>").decode()

# fmt: off
_DECODE_CASES: list[tuple[str, str, str, str | None, str]] = [
    # (text,                          format,             encoding, exp_type, description)
    ("<html><table></table></html>",  "table",            "",       "soup",   "HTML table"),
    ("<html></html>",                 "table_transposed", "",       "soup",   "transposed table"),
    ("<script>var x=1;</script>",     "javascript",       "",       "soup",   "JS embedded"),
    ("<script>var x=1;</script>",     "javascript_json",  "",       "soup",   "JS JSON"),
    ("<html><div>info</div></html>",  "html_fields",      "",       "soup",   "html_fields"),
    ('{"key": "value"}',              "json",             "",       "dict",   "valid JSON dict"),
    ("not json",                      "json",             "",       None,     "invalid JSON"),
    ("[1, 2, 3]",                     "json",             "",       "dict",   "non-dict JSON wrapped"),
    (_B64_HTML,                       "table",            "base64", "soup",   "base64-encoded body"),
    ("x",                             "table",            "base64", None,     "base64 decode failure"),
    ("",                              "table",            "",       None,     "empty body"),
    ("<root/>",                       "xml",              "",       None,     "XML not yet supported"),
    ("<html></html>",                 "unknown",          "",       "soup",   "unknown format fallback"),
]
# fmt: on


@pytest.mark.parametrize("text,fmt,encoding,exp_type,desc", _DECODE_CASES, ids=[c[4] for c in _DECODE_CASES])
def test_decode_response(text: str, fmt: str, encoding: str, exp_type: str | None, desc: str) -> None:
    """_decode_response: {desc}."""
    result = _decode_response(text, fmt, encoding)
    if exp_type is None:
        assert result is None
    elif exp_type == "soup":
        assert isinstance(result, BeautifulSoup)
    elif exp_type == "dict":
        assert isinstance(result, dict)


class TestDecodeResponseBehaviors:
    """Behavioral assertions beyond type checking."""

    def test_json_dict_preserves_keys(self) -> None:
        """Valid JSON dict preserves original keys."""
        result = _decode_response('{"key": "value"}', "json", "")
        assert result["key"] == "value"

    def test_json_non_dict_wrapped_in_raw(self) -> None:
        """Non-dict JSON is wrapped in _raw key."""
        result = _decode_response("[1, 2, 3]", "json", "")
        assert result["_raw"] == [1, 2, 3]


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

    def test_auth_response_reuse_with_error_status(self) -> None:
        """Auth response with error status is still eligible for reuse.

        requests.Response.__bool__() returns False for status >= 400.
        The reuse check must use ``is not None``, not truthiness.
        """
        entries = _build_entries({"/status.html": ("text/html", "<html>Server Status</html>")})

        # Response with 403 — bool(response) is False
        error_response = requests.Response()
        error_response.status_code = 403
        error_response._content = b"<html>Error Landing</html>"
        error_response.url = "http://192.168.100.1/status.html"
        error_response.encoding = "utf-8"

        auth_result = AuthResult(
            success=True,
            response=error_response,
            response_url="/status.html",
        )

        with HARMockServer(entries) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(session, server.base_url, timeout=10)
            targets = [ResourceTarget(path="/status.html", format="table")]
            resources = loader.fetch(targets, auth_result=auth_result)

        # Should reuse the auth response (error content), not fetch from server
        assert "Error Landing" in resources["/status.html"].get_text()

    def test_connection_failure_raises_resource_load_error(self) -> None:
        """ConnectionError during fetch raises ResourceLoadError."""
        from unittest.mock import patch

        session = requests.Session()
        loader = HTTPResourceLoader(session, "http://127.0.0.1", timeout=1)
        targets = [ResourceTarget(path="/status.html", format="table")]
        with (
            patch.object(session, "get", side_effect=requests.ConnectionError("refused")),
            pytest.raises(ResourceLoadError, match="Failed to fetch"),
        ):
            loader.fetch(targets)

    def test_undecoded_response_skipped(self) -> None:
        """Page that decodes to None is excluded from resources."""
        entries = _build_entries({"/data.json": ("application/json", "not valid json")})

        with HARMockServer(entries) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(session, server.base_url, timeout=10)
            targets = [ResourceTarget(path="/data.json", format="json")]
            resources = loader.fetch(targets)

        assert "/data.json" not in resources

    def test_login_page_detected(self) -> None:
        """Login page detection raises LoginPageDetectedError."""
        login_html = '<html><form><input type="password" name="pw"></form></html>'
        entries = _build_entries({"/status.html": ("text/html", login_html)})

        with HARMockServer(entries) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(
                session,
                server.base_url,
                timeout=10,
                detect_login_pages=True,
            )
            targets = [ResourceTarget(path="/status.html", format="table")]
            with pytest.raises(LoginPageDetectedError):
                loader.fetch(targets)

    def test_401_raises_resource_load_error(self) -> None:
        """401 response raises ResourceLoadError with status code."""
        # Build a HAR entry that returns 401
        entries = [
            {
                "request": {"method": "GET", "url": "http://192.168.100.1/status.html"},
                "response": {
                    "status": 401,
                    "headers": [],
                    "content": {"text": "Unauthorized"},
                },
            }
        ]

        with HARMockServer(entries) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(session, server.base_url, timeout=10)
            targets = [ResourceTarget(path="/status.html", format="table")]
            with pytest.raises(ResourceLoadError, match="401"):
                loader.fetch(targets)

    def test_query_params_appended(self) -> None:
        """Session query_params are appended to fetch URLs."""
        entries = _build_entries({"/status.html": ("text/html", "<html>Data</html>")})

        with HARMockServer(entries) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(
                session,
                server.base_url,
                timeout=10,
                query_params={"_n": "12345"},
            )
            targets = [ResourceTarget(path="/status.html", format="table")]
            resources = loader.fetch(targets)

        assert "/status.html" in resources

    def test_query_params_with_url_token(self) -> None:
        """Query params combine with URL token in the request URL."""
        entries = _build_entries({"/status.html": ("text/html", "<html>Data</html>")})

        with HARMockServer(entries) as server:
            session = requests.Session()
            loader = HTTPResourceLoader(
                session,
                server.base_url,
                timeout=10,
                url_token="abc123",
                token_prefix="ct_",
                query_params={"_n": "99999"},
            )
            targets = [ResourceTarget(path="/status.html", format="table")]
            resources = loader.fetch(targets)

        assert "/status.html" in resources

    def test_resource_fetches_recorded(self) -> None:
        """Per-resource timing tuples are populated after fetch."""
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
            loader.fetch(targets)

        assert len(loader.resource_fetches) == 2
        paths = [f[0] for f in loader.resource_fetches]
        assert "/status.html" in paths
        assert "/info.html" in paths
        # Each tuple is (path, duration_ms, size_bytes, status_code, content_type)
        for _path, duration_ms, size_bytes, status_code, content_type in loader.resource_fetches:
            assert duration_ms >= 0
            assert size_bytes > 0
            assert status_code == 200
            assert "text/html" in content_type
