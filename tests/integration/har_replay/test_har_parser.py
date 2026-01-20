"""Unit tests for HAR parser infrastructure.

These tests validate the HAR parsing logic without requiring actual HAR files.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .har_parser import (
    AuthPattern,
    HarExchange,
    HarParser,
    HarRequest,
    HarResponse,
)


class TestHarRequest:
    """Test HarRequest dataclass."""

    def test_path_extraction(self):
        """Test URL path extraction."""
        req = HarRequest(
            method="GET",
            url="http://192.168.100.1/login.html?foo=bar",
            headers={},
            cookies={},
        )
        assert req.path == "/login.html"

    def test_host_extraction(self):
        """Test host extraction from URL."""
        req = HarRequest(
            method="GET",
            url="https://192.168.100.1:8080/test",
            headers={},
            cookies={},
        )
        assert req.host == "192.168.100.1:8080"

    def test_header_case_insensitive(self):
        """Test case-insensitive header lookup."""
        req = HarRequest(
            method="GET",
            url="http://test/",
            headers={"Content-Type": "text/html", "X-Custom": "value"},
            cookies={},
        )
        assert req.has_header("content-type")
        assert req.has_header("CONTENT-TYPE")
        assert req.get_header("x-custom") == "value"

    def test_get_header_missing(self):
        """Test get_header returns None for missing header."""
        req = HarRequest(method="GET", url="http://test/", headers={}, cookies={})
        assert req.get_header("missing") is None


class TestHarResponse:
    """Test HarResponse dataclass."""

    def test_is_html(self):
        """Test HTML detection."""
        resp = HarResponse(
            status=200,
            status_text="OK",
            headers={},
            cookies={},
            content="<html>",
            mime_type="text/html; charset=utf-8",
        )
        assert resp.is_html

    def test_is_json(self):
        """Test JSON detection."""
        resp = HarResponse(
            status=200,
            status_text="OK",
            headers={},
            cookies={},
            content="{}",
            mime_type="application/json",
        )
        assert resp.is_json

    def test_is_xml(self):
        """Test XML detection."""
        resp = HarResponse(
            status=200,
            status_text="OK",
            headers={},
            cookies={},
            content="<xml>",
            mime_type="text/xml",
        )
        assert resp.is_xml


class TestHarExchange:
    """Test HarExchange dataclass."""

    def create_exchange(
        self,
        method: str = "GET",
        url: str = "http://test/",
        status: int = 200,
        post_data: str | None = None,
        headers: dict[str, str] | None = None,
        content: str = "",
    ) -> HarExchange:
        """Helper to create test exchanges."""
        return HarExchange(
            index=0,
            request=HarRequest(
                method=method,
                url=url,
                headers=headers or {},
                cookies={},
                post_data=post_data,
            ),
            response=HarResponse(
                status=status,
                status_text="OK",
                headers={},
                cookies={},
                content=content,
            ),
        )

    def test_is_auth_related_login_url(self):
        """Test auth detection via URL pattern."""
        exchange = self.create_exchange(url="http://192.168.100.1/login.html")
        assert exchange.is_auth_related()

    def test_is_auth_related_hnap(self):
        """Test auth detection via HNAP URL."""
        exchange = self.create_exchange(url="http://192.168.100.1/HNAP1/")
        assert exchange.is_auth_related()

    def test_is_auth_related_post_password(self):
        """Test auth detection via POST with password."""
        exchange = self.create_exchange(
            method="POST",
            url="http://192.168.100.1/check.php",
            post_data="username=admin&password=test123",
        )
        assert exchange.is_auth_related()

    def test_is_auth_related_soap_header(self):
        """Test auth detection via SOAPAction header."""
        exchange = self.create_exchange(
            url="http://192.168.100.1/HNAP1/",
            headers={"SOAPAction": '"http://purenetworks.com/HNAP1/Login"'},
        )
        assert exchange.is_auth_related()

    def test_is_auth_related_401(self):
        """Test auth detection via 401 status."""
        exchange = self.create_exchange(status=401)
        assert exchange.is_auth_related()

    def test_not_auth_related(self):
        """Test non-auth exchange detection."""
        exchange = self.create_exchange(url="http://192.168.100.1/status.html")
        assert not exchange.is_auth_related()


class TestHarParser:
    """Test HarParser class."""

    def create_minimal_har(self, entries: list[dict]) -> str:
        """Create minimal HAR JSON for testing."""
        return json.dumps({"log": {"entries": entries}})

    def write_har_file(self, content: str) -> Path:
        """Write HAR content to temp file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".har", delete=False) as f:
            f.write(content)
            return Path(f.name)

    def test_load_har(self):
        """Test loading HAR file."""
        content = self.create_minimal_har([])
        path = self.write_har_file(content)
        try:
            parser = HarParser(path)
            data = parser.load()
            assert "log" in data
        finally:
            path.unlink()

    def test_get_exchanges(self):
        """Test parsing entries to exchanges."""
        content = self.create_minimal_har(
            [
                {
                    "request": {
                        "method": "GET",
                        "url": "http://192.168.100.1/",
                        "headers": [],
                        "cookies": [],
                    },
                    "response": {
                        "status": 200,
                        "statusText": "OK",
                        "headers": [],
                        "content": {"text": "<html>test</html>", "mimeType": "text/html"},
                    },
                }
            ]
        )
        path = self.write_har_file(content)
        try:
            parser = HarParser(path)
            exchanges = parser.get_exchanges()
            assert len(exchanges) == 1
            assert exchanges[0].url == "http://192.168.100.1/"
            assert exchanges[0].status == 200
        finally:
            path.unlink()

    def test_detect_form_auth_with_password_post(self):
        """Test detecting FORM_PLAIN from POST with password."""
        content = self.create_minimal_har(
            [
                {
                    "request": {
                        "method": "POST",
                        "url": "http://192.168.100.1/goform/login",
                        "headers": [],
                        "cookies": [],
                        # Use a password that's clearly not base64 (odd length, special chars)
                        "postData": {"text": "username=admin&password=test!@#"},
                    },
                    "response": {
                        "status": 302,
                        "statusText": "Found",
                        "headers": [],
                        "content": {},
                    },
                }
            ]
        )
        path = self.write_har_file(content)
        try:
            parser = HarParser(path)
            pattern = parser.detect_auth_pattern()
            assert pattern == AuthPattern.FORM_PLAIN
        finally:
            path.unlink()

    def test_detect_hnap_auth(self):
        """Test detecting HNAP_SESSION from SOAPAction header."""
        content = self.create_minimal_har(
            [
                {
                    "request": {
                        "method": "POST",
                        "url": "http://192.168.100.1/HNAP1/",
                        "headers": [{"name": "SOAPAction", "value": '"http://purenetworks.com/HNAP1/Login"'}],
                        "cookies": [],
                        "postData": {"text": "<Login>...</Login>"},
                    },
                    "response": {
                        "status": 200,
                        "statusText": "OK",
                        "headers": [],
                        "content": {"text": '{"LoginResponse": {}}', "mimeType": "application/json"},
                    },
                }
            ]
        )
        path = self.write_har_file(content)
        try:
            parser = HarParser(path)
            pattern = parser.detect_auth_pattern()
            assert pattern == AuthPattern.HNAP_SESSION
        finally:
            path.unlink()

    def test_detect_url_token_auth(self):
        """Test detecting URL_TOKEN_SESSION from login_ URL."""
        content = self.create_minimal_har(
            [
                {
                    "request": {
                        "method": "GET",
                        "url": "http://192.168.100.1/login_test12345678.html",
                        "headers": [],
                        "cookies": [],
                    },
                    "response": {
                        "status": 200,
                        "statusText": "OK",
                        "headers": [],
                        "content": {"text": "<html>", "mimeType": "text/html"},
                    },
                }
            ]
        )
        path = self.write_har_file(content)
        try:
            parser = HarParser(path)
            pattern = parser.detect_auth_pattern()
            assert pattern == AuthPattern.URL_TOKEN_SESSION
        finally:
            path.unlink()

    def test_extract_auth_flow_form(self):
        """Test extracting form auth flow details."""
        content = self.create_minimal_har(
            [
                {
                    "request": {
                        "method": "GET",
                        "url": "http://192.168.100.1/login.html",
                        "headers": [],
                        "cookies": [],
                    },
                    "response": {
                        "status": 200,
                        "statusText": "OK",
                        "headers": [],
                        "content": {
                            "text": '<form><input type="password" name="pwd"></form>',
                            "mimeType": "text/html",
                        },
                    },
                },
                {
                    "request": {
                        "method": "POST",
                        "url": "http://192.168.100.1/goform/login",
                        "headers": [],
                        "cookies": [],
                        "postData": {"text": "username=admin&password=test123"},
                    },
                    "response": {
                        "status": 302,
                        "statusText": "Found",
                        "headers": [],
                        "content": {},
                    },
                },
            ]
        )
        path = self.write_har_file(content)
        try:
            parser = HarParser(path)
            flow = parser.extract_auth_flow()
            assert flow.pattern == AuthPattern.FORM_PLAIN
            assert flow.login_url == "http://192.168.100.1/login.html"
            assert flow.form_action == "/goform/login"
            assert flow.password_field == "password"
        finally:
            path.unlink()


class TestBase64Detection:
    """Test base64 password detection heuristics."""

    def test_detects_base64_password(self):
        """Test base64 password detection."""
        content = json.dumps(
            {
                "log": {
                    "entries": [
                        {
                            "request": {
                                "method": "POST",
                                "url": "http://192.168.100.1/login",
                                "headers": [],
                                "cookies": [],
                                # "test" in base64 is "dGVzdA=="
                                "postData": {"text": "username=admin&password=dGVzdA=="},
                            },
                            "response": {
                                "status": 302,
                                "statusText": "Found",
                                "headers": [],
                                "content": {},
                            },
                        }
                    ]
                }
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".har", delete=False) as f:
            f.write(content)
            path = Path(f.name)
        try:
            parser = HarParser(path)
            pattern = parser.detect_auth_pattern()
            assert pattern == AuthPattern.FORM_BASE64
        finally:
            path.unlink()
