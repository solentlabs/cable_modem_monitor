"""URL Token authentication handler for MockModemServer.

Handles URL-based token authentication with session cookies.
Implements URL_TOKEN_SESSION auth pattern.
"""

from __future__ import annotations

import base64
import logging
import secrets
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import urlparse

from .base import BaseAuthHandler

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.modem_config.schema import (
        ModemConfig,
        UrlTokenAuthConfig,
    )

_LOGGER = logging.getLogger(__name__)

# Test credentials for MockModemServer - use "pw" instead of "password" to avoid
# browser password managers flagging these as real credentials during development
TEST_USERNAME = "admin"
TEST_PASSWORD = "pw"


class UrlTokenAuthHandler(BaseAuthHandler):
    """Handler for URL-based token authentication.

    Implements the auth flow:
    1. Client sends GET to login_page with login_<base64(user:pass)> in query
    2. Server validates credentials, sets session cookie, returns data
    3. Subsequent requests include ?ct_<session_token> for authenticated access

    Variants:
    - Some firmware (Spectrum) doesn't require auth at all
    - Other firmware (HTTPS) requires URL token auth

    Strict mode (strict=True):
    - Simulates real SB8200 HTTPS behavior where cookies alone don't work
    - Session token MUST be in URL query string for EVERY request
    - Used for testing Issue #81 (polling fails without URL tokens)
    """

    def __init__(self, config: ModemConfig, fixtures_path: Path, *, strict: bool = False):
        """Initialize URL token auth handler.

        Args:
            config: Modem configuration.
            fixtures_path: Path to fixtures directory.
            strict: If True, require URL token in every request (reject cookies).
                    Simulates real SB8200 HTTPS firmware behavior.
        """
        super().__init__(config, fixtures_path)

        # Extract URL token config from auth.types{}
        url_token_config = config.auth.types.get("url_token")
        if not url_token_config:
            raise ValueError("URL token auth handler requires url_token config in auth.types")
        self.url_token_config: UrlTokenAuthConfig = cast("UrlTokenAuthConfig", url_token_config)

        # Strict mode: require URL token, reject cookie-only requests
        self.strict = strict
        if strict:
            _LOGGER.debug("UrlTokenAuthHandler in strict mode - cookies will be ignored")

        # Session state
        self.authenticated_sessions: dict[str, str] = {}  # session_id -> username

    def handle_request(
        self,
        handler: BaseHTTPRequestHandler,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle HTTP request with URL token authentication.

        Args:
            handler: HTTP request handler.
            method: HTTP method.
            path: Request path with query string.
            headers: Request headers.
            body: Request body.

        Returns:
            Response tuple (status, headers, body).
        """
        parsed = urlparse(path)
        clean_path = parsed.path
        query = parsed.query

        # Check for login token in URL
        login_prefix = self.url_token_config.login_prefix
        if login_prefix and login_prefix in query:
            return self._handle_login(query, headers)

        # Check for session token in URL or cookie
        if self._is_authenticated(headers, query):
            return self.serve_fixture(clean_path)

        # Public paths don't need auth
        if self.is_public_path(clean_path):
            return self.serve_fixture(clean_path)

        # Not authenticated - return login page or 401
        return self._serve_unauthenticated_response(clean_path)

    def _handle_login(
        self,
        query: str,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle login request with base64 token in URL.

        Args:
            query: Query string containing login token.
            headers: Request headers.

        Returns:
            Response tuple.
        """
        login_prefix = self.url_token_config.login_prefix

        # Extract base64 token from query
        token = None
        for param in query.split("&"):
            if param.startswith(login_prefix):
                token = param[len(login_prefix) :]
                break

        if not token:
            return self._unauthorized_response()

        # Decode and validate credentials
        try:
            decoded = base64.b64decode(token).decode("utf-8")
            if ":" not in decoded:
                return self._unauthorized_response()

            username, password = decoded.split(":", 1)

            if username == TEST_USERNAME and password == TEST_PASSWORD:
                return self._create_authenticated_session(username)

        except Exception as e:
            _LOGGER.debug("URL token auth failed: %s", e)

        return self._unauthorized_response()

    def _create_authenticated_session(
        self,
        username: str,
    ) -> tuple[int, dict[str, str], bytes]:
        """Create authenticated session and return data page.

        Args:
            username: Authenticated username.

        Returns:
            Response with session cookie and data.
        """
        # Generate session token
        session_token = secrets.token_hex(16)
        self.authenticated_sessions[session_token] = username

        # Get the data page content
        data_page = self.url_token_config.login_page
        content = self.get_fixture_content(data_page)

        if content is None:
            content = b"<html><body>Authenticated</body></html>"

        cookie_name = self.url_token_config.session_cookie
        response_headers = {
            "Content-Type": self.get_content_type(data_page),
            "Content-Length": str(len(content)),
            "Set-Cookie": f"{cookie_name}={session_token}; Path=/",
        }

        _LOGGER.debug(
            "URL token auth successful for %s, session=%s",
            username,
            session_token[:8],
        )

        return 200, response_headers, content

    def _is_authenticated(self, headers: dict[str, str], query: str) -> bool:
        """Check if request is authenticated via session token.

        In strict mode (simulating real SB8200 HTTPS), only URL tokens are accepted.
        In normal mode, either URL token or session cookie is accepted.

        Args:
            headers: Request headers.
            query: Query string.

        Returns:
            True if authenticated.
        """
        # Check for session token in query string
        token_prefix = self.url_token_config.token_prefix
        if token_prefix and token_prefix in query:
            for param in query.split("&"):
                if param.startswith(token_prefix):
                    token = param[len(token_prefix) :]
                    if token in self.authenticated_sessions:
                        return True

        # In strict mode, only URL token is accepted (cookies ignored)
        if self.strict:
            _LOGGER.debug("Strict mode: No URL token found, rejecting request")
            return False

        # Check for session cookie (only in non-strict mode)
        cookie_name = self.url_token_config.session_cookie
        cookie_header = headers.get("Cookie", "")

        for cookie_part in cookie_header.split(";"):
            stripped_cookie = cookie_part.strip()
            if stripped_cookie.startswith(f"{cookie_name}="):
                session_token = stripped_cookie.split("=", 1)[1]
                if session_token in self.authenticated_sessions:
                    return True

        return False

    def _unauthorized_response(self) -> tuple[int, dict[str, str], bytes]:
        """Return 401 Unauthorized response."""
        return (
            401,
            {"Content-Type": "text/plain"},
            b"Unauthorized",
        )

    def _serve_unauthenticated_response(
        self,
        path: str,
    ) -> tuple[int, dict[str, str], bytes]:
        """Serve response for unauthenticated request.

        In strict mode: Always return login page (no no-auth fallback).
        In normal mode: Serve fixture if available (for Spectrum no-auth variant).

        Args:
            path: Request path.

        Returns:
            Response tuple.
        """
        # In strict mode, always return login page
        if self.strict:
            _LOGGER.debug("Strict mode: Serving login page for unauthenticated request to %s", path)
            return self._serve_login_page()

        # Try to serve the fixture (for no-auth variant testing)
        content = self.get_fixture_content(path)

        if content is not None:
            # Check if this looks like a data page (has success indicator)
            success_indicator = self.url_token_config.success_indicator
            if success_indicator and success_indicator.encode() in content:
                # For no-auth variant, just serve the data
                return (
                    200,
                    {
                        "Content-Type": self.get_content_type(path),
                        "Content-Length": str(len(content)),
                    },
                    content,
                )

        # Return login page or minimal page with model detection
        return self._serve_login_page()

    def _serve_login_page(self) -> tuple[int, dict[str, str], bytes]:
        """Serve the login page.

        Returns:
            Response tuple.
        """
        # Try to serve Login.html fixture if it exists
        login_content = self.get_fixture_content("/Login.html")
        if login_content:
            return 200, {"Content-Type": "text/html; charset=utf-8"}, login_content

        # Try root.html, but only if it doesn't contain data (check success indicator)
        # In strict mode, we need a real login page, not a data page
        root_content = self.get_fixture_content("/root.html")
        if root_content:
            success_indicator = self.url_token_config.success_indicator
            if not success_indicator or success_indicator.encode() not in root_content:
                return 200, {"Content-Type": "text/html; charset=utf-8"}, root_content
            # root.html contains data, don't use it as login page

        # Synthesize minimal login page with model detection
        login_html = f"""<!DOCTYPE html>
<html><head><title>Login</title></head>
<body>
<span id="thisModelNumberIs">{self.config.model}</span>
<form action="">
<input type="text" id="username" name="username">
<input type="password" id="password" name="password">
<input type="button" id="loginButton" value="Login">
</form>
</body></html>
"""
        return 200, {"Content-Type": "text/html; charset=utf-8"}, login_html.encode()
