"""HAR file parser for extracting HTTP exchanges for test mocking.

This module parses HAR (HTTP Archive) files and extracts the information
needed to mock HTTP responses in tests. It focuses on:
- Request/response pairs for specific URLs
- Authentication-related exchanges (login pages, form posts, HNAP calls)
- Cookie and session tracking

Unlike scripts/har_auth_extractor.py (which is a developer triage tool),
this module is designed for test infrastructure integration.
"""

from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


class AuthPattern(Enum):
    """Detected authentication patterns."""

    UNKNOWN = "unknown"
    NO_AUTH = "no_auth"
    BASIC_HTTP = "basic_http"
    FORM_PLAIN = "form_plain"
    FORM_BASE64 = "form_base64"
    HNAP_SESSION = "hnap_session"
    URL_TOKEN_SESSION = "url_token_session"
    CREDENTIAL_CSRF = "credential_csrf"


@dataclass
class HarRequest:
    """Parsed HTTP request from HAR."""

    method: str
    url: str
    headers: dict[str, str]
    cookies: dict[str, str]
    post_data: str | None = None
    mime_type: str | None = None

    @property
    def path(self) -> str:
        """Extract URL path."""
        return urlparse(self.url).path

    @property
    def host(self) -> str:
        """Extract host from URL."""
        return urlparse(self.url).netloc

    def has_header(self, name: str) -> bool:
        """Check if header exists (case-insensitive)."""
        return name.lower() in {k.lower() for k in self.headers}

    def get_header(self, name: str) -> str | None:
        """Get header value (case-insensitive)."""
        for key, value in self.headers.items():
            if key.lower() == name.lower():
                return value
        return None


@dataclass
class HarResponse:
    """Parsed HTTP response from HAR."""

    status: int
    status_text: str
    headers: dict[str, str]
    cookies: dict[str, str]
    content: str
    mime_type: str | None = None
    encoding: str | None = None

    @property
    def is_html(self) -> bool:
        """Check if response is HTML."""
        mime = self.mime_type or ""
        return "text/html" in mime or "application/xhtml" in mime

    @property
    def is_json(self) -> bool:
        """Check if response is JSON."""
        mime = self.mime_type or ""
        return "application/json" in mime or "text/json" in mime

    @property
    def is_xml(self) -> bool:
        """Check if response is XML."""
        mime = self.mime_type or ""
        return "text/xml" in mime or "application/xml" in mime

    def get_set_cookie(self, name: str) -> str | None:
        """Get a specific Set-Cookie value."""
        return self.cookies.get(name)


@dataclass
class HarExchange:
    """A single HTTP request/response exchange."""

    index: int
    request: HarRequest
    response: HarResponse
    started: str | None = None  # ISO timestamp
    time_ms: float = 0.0

    @property
    def url(self) -> str:
        """Shortcut to request URL."""
        return self.request.url

    @property
    def path(self) -> str:
        """Shortcut to request path."""
        return self.request.path

    @property
    def method(self) -> str:
        """Shortcut to request method."""
        return self.request.method

    @property
    def status(self) -> int:
        """Shortcut to response status."""
        return self.response.status

    def is_auth_related(self) -> bool:
        """Check if this exchange appears auth-related."""
        path_lower = self.path.lower()

        # URL patterns
        if any(p in path_lower for p in ["/login", "/auth", "/session", "/hnap"]):
            return True

        # POST with password-like fields
        if self.method == "POST" and self.request.post_data:
            post_lower = self.request.post_data.lower()
            if any(p in post_lower for p in ["password", "passwd", "pwd"]):
                return True

        # HNAP/SOAP patterns
        if self.request.has_header("SOAPAction"):
            return True

        # Basic auth
        if self.request.has_header("Authorization"):
            return True

        # 401 response
        return self.status == 401


@dataclass
class HarAuthFlow:
    """Extracted authentication flow from HAR."""

    pattern: AuthPattern = AuthPattern.UNKNOWN
    exchanges: list[HarExchange] = field(default_factory=list)

    # Login page info
    login_url: str | None = None
    login_page_index: int | None = None

    # Form auth
    form_action: str | None = None
    form_fields: dict[str, str] = field(default_factory=dict)
    password_field: str | None = None
    username_field: str | None = None
    password_encoding: str | None = None  # "plain", "base64", "urlencoded"

    # Session info
    session_cookie: str | None = None
    csrf_token_field: str | None = None

    # HNAP info
    hnap_endpoint: str | None = None
    soap_actions: list[str] = field(default_factory=list)

    # URL token info (URL_TOKEN_SESSION pattern)
    url_token_prefix: str | None = None
    url_auth_header: str | None = None


class HarParser:
    """Parser for HAR files to extract HTTP exchanges and auth flows."""

    def __init__(self, har_path: Path | str):
        """Initialize parser with HAR file path.

        Args:
            har_path: Path to .har or .har.gz file
        """
        self.path = Path(har_path)
        self._har_data: dict[str, Any] | None = None
        self._exchanges: list[HarExchange] | None = None

    def load(self) -> dict[str, Any]:
        """Load and parse HAR file.

        Returns:
            Parsed HAR data as dict
        """
        if self._har_data is not None:
            return self._har_data

        if self.path.suffix == ".gz":
            with gzip.open(self.path, "rt", encoding="utf-8") as f:
                self._har_data = json.load(f)
        else:
            with open(self.path, encoding="utf-8") as f:
                self._har_data = json.load(f)

        return self._har_data

    def _parse_headers(self, headers: list[dict[str, str]]) -> dict[str, str]:
        """Convert HAR headers list to dict."""
        result: dict[str, str] = {}
        for h in headers:
            name = h.get("name", "")
            value = h.get("value", "")
            if name:
                result[name] = value
        return result

    def _parse_cookies(self, cookies: list[dict[str, Any]]) -> dict[str, str]:
        """Convert HAR cookies list to dict."""
        result: dict[str, str] = {}
        for c in cookies:
            name = c.get("name", "")
            value = c.get("value", "")
            if name:
                result[name] = value
        return result

    def _parse_set_cookies(self, headers: list[dict[str, str]]) -> dict[str, str]:
        """Extract Set-Cookie values from headers."""
        result: dict[str, str] = {}
        for h in headers:
            if h.get("name", "").lower() == "set-cookie":
                value = h.get("value", "")
                # Parse "name=value; ..." format
                if "=" in value:
                    parts = value.split(";")[0]
                    name, _, val = parts.partition("=")
                    result[name.strip()] = val.strip()
        return result

    def _parse_entry(self, index: int, entry: dict[str, Any]) -> HarExchange:
        """Parse a single HAR entry into HarExchange."""
        request = entry.get("request", {})
        response = entry.get("response", {})

        # Parse request
        post_data = None
        mime_type = None
        if "postData" in request:
            post_data = request["postData"].get("text", "")
            mime_type = request["postData"].get("mimeType", "")

        har_request = HarRequest(
            method=request.get("method", "GET"),
            url=request.get("url", ""),
            headers=self._parse_headers(request.get("headers", [])),
            cookies=self._parse_cookies(request.get("cookies", [])),
            post_data=post_data,
            mime_type=mime_type,
        )

        # Parse response
        content = response.get("content", {})
        content_text = content.get("text", "")

        har_response = HarResponse(
            status=response.get("status", 0),
            status_text=response.get("statusText", ""),
            headers=self._parse_headers(response.get("headers", [])),
            cookies=self._parse_set_cookies(response.get("headers", [])),
            content=content_text,
            mime_type=content.get("mimeType", ""),
            encoding=content.get("encoding", ""),
        )

        return HarExchange(
            index=index,
            request=har_request,
            response=har_response,
            started=entry.get("startedDateTime"),
            time_ms=entry.get("time", 0),
        )

    def get_exchanges(self) -> list[HarExchange]:
        """Get all HTTP exchanges from HAR file.

        Returns:
            List of HarExchange objects
        """
        if self._exchanges is not None:
            return self._exchanges

        har = self.load()
        entries = har.get("log", {}).get("entries", [])

        self._exchanges = [self._parse_entry(i, e) for i, e in enumerate(entries)]
        return self._exchanges

    def get_auth_exchanges(self) -> list[HarExchange]:
        """Get only auth-related exchanges.

        Returns:
            List of auth-related HarExchange objects
        """
        return [e for e in self.get_exchanges() if e.is_auth_related()]

    def get_exchange_by_path(self, path: str) -> HarExchange | None:
        """Find first exchange matching URL path.

        Args:
            path: URL path to match (e.g., "/login")

        Returns:
            First matching exchange or None
        """
        for e in self.get_exchanges():
            if e.path == path or e.path.endswith(path):
                return e
        return None

    def get_exchanges_by_pattern(self, pattern: str) -> list[HarExchange]:
        """Find exchanges matching URL regex pattern.

        Args:
            pattern: Regex pattern to match against URLs

        Returns:
            List of matching exchanges
        """
        regex = re.compile(pattern, re.IGNORECASE)
        return [e for e in self.get_exchanges() if regex.search(e.url)]

    def detect_auth_pattern(self) -> AuthPattern:  # noqa: C901
        """Detect the authentication pattern used in the HAR.

        Returns:
            Detected AuthPattern enum value
        """
        exchanges = self.get_exchanges()

        # Check for HNAP
        for e in exchanges:
            if e.request.has_header("SOAPAction"):
                soap = e.request.get_header("SOAPAction") or ""
                if "Login" in soap or "HNAP" in soap:
                    return AuthPattern.HNAP_SESSION

        # Check for URL token (URL_TOKEN_SESSION pattern)
        for e in exchanges:
            if "login_" in e.url or "ct_" in e.url:
                return AuthPattern.URL_TOKEN_SESSION

        # Check for Basic auth
        for e in exchanges:
            if e.status == 401:
                for h in e.response.headers:
                    if h.lower() == "www-authenticate":
                        return AuthPattern.BASIC_HTTP
            if e.request.has_header("Authorization"):
                auth = e.request.get_header("Authorization") or ""
                if auth.lower().startswith("basic "):
                    return AuthPattern.BASIC_HTTP

        # Check for form auth
        for e in exchanges:
            if e.method == "POST" and e.request.post_data:
                post_lower = e.request.post_data.lower()
                if "password" in post_lower or "passwd" in post_lower:
                    # Check if base64 encoded
                    if self._has_base64_password(e.request.post_data):
                        return AuthPattern.FORM_BASE64
                    return AuthPattern.FORM_PLAIN

        # Check if any page has login form
        for e in exchanges:
            if e.response.is_html and e.response.content:
                lower = e.response.content.lower()
                has_password = 'type="password"' in lower or "type='password'" in lower
                has_login = any(w in lower for w in ["login", "sign in", "authenticate"])
                if has_password and has_login:
                    return AuthPattern.FORM_PLAIN

        return AuthPattern.UNKNOWN

    def _has_base64_password(self, post_data: str) -> bool:
        """Check if POST data contains base64-encoded password.

        This is a heuristic - we look for common patterns like:
        - password=<base64_string>
        - The password value has base64 characteristics
        """
        # Parse form data
        try:
            params = parse_qs(post_data)
        except Exception:
            return False

        # Look for password field
        for key in ["password", "Password", "passwd", "Passwd", "pwd", "PWD"]:
            if key in params:
                value = params[key][0]
                # Base64 characteristics: length multiple of 4, valid chars
                is_valid_length = len(value) > 0 and len(value) % 4 == 0
                is_base64_chars = bool(re.match(r"^[A-Za-z0-9+/=]+$", value))
                if is_valid_length and is_base64_chars:
                    return True
        return False

    def extract_auth_flow(self) -> HarAuthFlow:
        """Extract complete auth flow from HAR.

        Returns:
            HarAuthFlow with detected pattern and relevant exchanges
        """
        flow = HarAuthFlow()
        flow.pattern = self.detect_auth_pattern()
        flow.exchanges = self.get_auth_exchanges()

        # Pattern-specific extraction
        if flow.pattern == AuthPattern.HNAP_SESSION:
            self._extract_hnap_flow(flow)
        elif flow.pattern == AuthPattern.URL_TOKEN_SESSION:
            self._extract_url_token_flow(flow)
        elif flow.pattern in (AuthPattern.FORM_PLAIN, AuthPattern.FORM_BASE64):
            self._extract_form_flow(flow)

        return flow

    def _extract_hnap_flow(self, flow: HarAuthFlow) -> None:
        """Extract HNAP-specific auth details."""
        for e in self.get_exchanges():
            soap_action = e.request.get_header("SOAPAction")
            if soap_action:
                flow.soap_actions.append(soap_action)
                if not flow.hnap_endpoint:
                    flow.hnap_endpoint = e.path

    def _extract_url_token_flow(self, flow: HarAuthFlow) -> None:
        """Extract URL token auth details (URL_TOKEN_SESSION pattern)."""
        for e in self.get_exchanges():
            if "login_" in e.url:
                flow.url_token_prefix = "login_"
                flow.login_url = e.url
            if e.request.has_header("credential"):
                flow.url_auth_header = e.request.get_header("credential")

    def _extract_form_flow(self, flow: HarAuthFlow) -> None:  # noqa: C901
        """Extract form-based auth details."""
        # Find login page
        for e in self.get_exchanges():
            if e.response.is_html and e.response.content:
                content_lower = e.response.content.lower()
                if 'type="password"' in content_lower:
                    flow.login_url = e.url
                    flow.login_page_index = e.index
                    break

        # Find form submission
        for e in self.get_exchanges():
            if e.method == "POST" and e.request.post_data:
                post_lower = e.request.post_data.lower()
                if "password" in post_lower:
                    flow.form_action = e.path
                    flow.password_encoding = "base64" if flow.pattern == AuthPattern.FORM_BASE64 else "plain"
                    # Parse form fields
                    try:
                        params = parse_qs(e.request.post_data)
                        for key, values in params.items():
                            flow.form_fields[key] = values[0] if values else ""
                            if key.lower() in ["password", "passwd", "pwd"]:
                                flow.password_field = key
                            if key.lower() in ["username", "user", "login", "uid"]:
                                flow.username_field = key
                    except Exception:
                        pass
                    break
