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
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from .base import BaseAuthHandler

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.modem_config.schema import (
        ModemConfig,
        UrlTokenAuthConfig,
    )

_LOGGER = logging.getLogger(__name__)

# Test credentials for MockModemServer
TEST_USERNAME = "admin"
TEST_PASSWORD = "password"


class UrlTokenAuthHandler(BaseAuthHandler):
    """Handler for URL-based token authentication.

    Implements the auth flow:
    1. Client sends GET to login_page with login_<base64(user:pass)> in query
    2. Server validates credentials, sets session cookie, returns data
    3. Subsequent requests include ?ct_<session_token> for authenticated access

    Variants:
    - Some firmware (Spectrum) doesn't require auth at all
    - Other firmware (HTTPS) requires URL token auth
    """

    def __init__(self, config: ModemConfig, fixtures_path: Path):
        """Initialize URL token auth handler.

        Args:
            config: Modem configuration.
            fixtures_path: Path to fixtures directory.
        """
        super().__init__(config, fixtures_path)

        # Extract URL token config (validated as non-None)
        if not config.auth.url_token:
            raise ValueError("URL token auth handler requires url_token config")
        self.url_token_config: UrlTokenAuthConfig = config.auth.url_token

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

        # Check for session cookie
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

        Some URL_TOKEN modems serve data without auth (certain firmware versions),
        others require auth. We serve the fixture if available
        to support the no-auth variant.

        Args:
            path: Request path.

        Returns:
            Response tuple.
        """
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

        # Try root.html
        root_content = self.get_fixture_content("/root.html")
        if root_content:
            return 200, {"Content-Type": "text/html; charset=utf-8"}, root_content

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
