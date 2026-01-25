"""AJAX-based form authentication handler for MockModemServer.

Simulates modems that use JavaScript XMLHttpRequest for login instead of
traditional form submission. Credentials are base64-encoded and submitted
with a client-generated nonce.

Response format:
- Success: "Url:/path" (redirect to path)
- Failure: "Error:message"
"""

from __future__ import annotations

import base64
import logging
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import unquote, urlparse

from .base import BaseAuthHandler
from .form import TEST_PASSWORD, TEST_USERNAME

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.modem_config.schema import (
        FormAjaxAuthConfig,
        ModemConfig,
    )

_LOGGER = logging.getLogger(__name__)


class FormAjaxAuthHandler(BaseAuthHandler):
    """Handler for AJAX-based form authentication.

    Simulates modems that use JavaScript XMLHttpRequest for login.
    The client submits:
    - arguments: base64(urlencode("username={user}:password={pass}"))
    - ar_nonce: random digits (client-generated)

    Response is plain text:
    - "Url:/path" on success
    - "Error:message" on failure
    """

    def __init__(self, config: ModemConfig, fixtures_path: Path):
        """Initialize AJAX form auth handler.

        Args:
            config: Modem configuration.
            fixtures_path: Path to fixtures directory.
        """
        super().__init__(config, fixtures_path)

        # Get form_ajax config (required for this handler)
        form_config = config.auth.types.get("form_ajax")
        if not form_config:
            raise ValueError("FormAjaxAuthHandler requires form_ajax config in auth.types")
        self.form_config: FormAjaxAuthConfig = cast("FormAjaxAuthConfig", form_config)

    def handle_request(
        self,
        handler: BaseHTTPRequestHandler,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle HTTP request with AJAX form authentication.

        Args:
            handler: HTTP request handler.
            method: HTTP method.
            path: Request path.
            headers: Request headers.
            body: Request body.

        Returns:
            Response tuple (status, headers, body).
        """
        parsed = urlparse(path)
        clean_path = parsed.path

        # Handle AJAX login endpoint
        if method == "POST" and clean_path == self.form_config.endpoint:
            return self._handle_ajax_login(body, headers)

        # Check if authenticated for protected paths
        if self.is_protected_path(clean_path) and not self.is_authenticated(headers):
            # Return login page
            return self._serve_login_page()

        # Serve the requested page
        return self.serve_fixture(clean_path)

    def _handle_ajax_login(self, body: bytes | None, headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
        """Handle AJAX login submission.

        Args:
            body: POST body with form data.
            headers: Request headers.

        Returns:
            Response tuple with plain text body.
        """
        if body is None:
            return self._error_response("No data submitted")

        form_data = self.parse_form_data(body)

        # Get encoded arguments
        arguments_field = getattr(self.form_config, "arguments_field", "arguments")
        encoded_args = form_data.get(arguments_field, "")

        if not encoded_args:
            return self._error_response("Missing credentials")

        # Decode credentials: base64(urlencode("username=X:password=Y"))
        try:
            decoded_bytes = base64.b64decode(encoded_args)
            decoded_str = unquote(decoded_bytes.decode("utf-8"))
        except Exception as e:
            _LOGGER.warning("Failed to decode credentials: %s", e)
            return self._error_response("Invalid credential format")

        # Parse credentials from format "username=X:password=Y"
        username, password = self._parse_credentials(decoded_str)

        _LOGGER.debug("AJAX login attempt: username=%s", username)

        if username == TEST_USERNAME and password == TEST_PASSWORD:
            # Success - create session
            session_id = self.create_session()
            cookie_name = "session"
            if self.config.auth.session and self.config.auth.session.cookie_name:
                cookie_name = self.config.auth.session.cookie_name

            # Return success response
            success_prefix = getattr(self.form_config, "success_prefix", "Url:")
            redirect_path = "/cgi-bin/status"  # Default redirect

            _LOGGER.debug("AJAX login successful")
            return (
                200,
                {
                    "Content-Type": "text/plain",
                    "Set-Cookie": f"{cookie_name}={session_id}; Path=/",
                },
                f"{success_prefix}{redirect_path}".encode(),
            )

        # Failed login
        _LOGGER.debug("AJAX login failed: invalid credentials")
        return self._error_response("Invalid password")

    def _parse_credentials(self, credential_str: str) -> tuple[str, str]:
        """Parse credentials from format string.

        Expected format: "username={user}:password={pass}"

        Args:
            credential_str: Decoded credential string.

        Returns:
            Tuple of (username, password).
        """
        username = ""
        password = ""

        # Parse "username=X:password=Y" format
        parts = credential_str.split(":")
        for part in parts:
            if part.startswith("username="):
                username = part[9:]
            elif part.startswith("password="):
                password = part[9:]

        return username, password

    def _error_response(self, message: str) -> tuple[int, dict[str, str], bytes]:
        """Return an error response.

        Args:
            message: Error message.

        Returns:
            Response tuple with error message.
        """
        error_prefix = getattr(self.form_config, "error_prefix", "Error:")
        return (
            200,
            {"Content-Type": "text/plain"},
            f"{error_prefix}{message}".encode(),
        )

    def _serve_login_page(self) -> tuple[int, dict[str, str], bytes]:
        """Serve the login page.

        Returns:
            Response tuple with login HTML.
        """
        # Try to serve login.html fixture if exists
        login_fixture = self.get_fixture_content("/login.html")
        if login_fixture:
            return 200, {"Content-Type": "text/html; charset=utf-8"}, login_fixture

        # Synthesize minimal login page
        login_html = self._synthesize_login_page()
        return 200, {"Content-Type": "text/html; charset=utf-8"}, login_html.encode()

    def _synthesize_login_page(self) -> str:
        """Synthesize a minimal login page with AJAX form.

        Returns:
            HTML string with AJAX login form.
        """
        endpoint = getattr(self.form_config, "endpoint", "/cgi-bin/adv_pwd_cgi")
        nonce_field = getattr(self.form_config, "nonce_field", "ar_nonce")
        arguments_field = getattr(self.form_config, "arguments_field", "arguments")

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{self.config.manufacturer} {self.config.model} - Login</title>
    <script>
    function getNonce() {{
        return Math.random().toString().substr(2, 8);
    }}
    function do_login() {{
        var username = document.getElementById('username').value;
        var password = document.getElementById('password').value;
        var creds = 'username=' + username + ':password=' + password;
        var encoded = btoa(encodeURIComponent(creds));
        var nonce = getNonce();

        var xhr = new XMLHttpRequest();
        xhr.open('POST', '{endpoint}', true);
        xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
        xhr.onload = function() {{
            if (xhr.responseText.indexOf('Url:') === 0) {{
                window.location.href = xhr.responseText.substr(4);
            }} else {{
                alert(xhr.responseText.substr(6));
            }}
        }};
        xhr.send('{arguments_field}=' + encoded + '&{nonce_field}=' + nonce);
    }}
    </script>
</head>
<body>
    <h1>{self.config.manufacturer} {self.config.model}</h1>
    <p>AJAX Login Form</p>
    <form onsubmit="do_login(); return false;">
        <input type="hidden" name="{nonce_field}" id="{nonce_field}">
        <label>Username: <input type="text" name="username" id="username"></label><br>
        <label>Password: <input type="password" name="password" id="password"></label><br>
        <input type="submit" value="Login">
    </form>
</body>
</html>
"""
