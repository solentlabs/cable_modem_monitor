"""Form authentication handler with client nonce for MockModemServer.

Simulates modems that use plain form fields with a client-generated nonce.
Unlike form_ajax, credentials are NOT base64-encoded.

Used by: ARRIS SB6190 (firmware 9.1.103+)

Response format:
- Success: "Url:/path" (redirect to path)
- Failure: "Error:message"
"""

from __future__ import annotations

import logging
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import urlparse

from .form_base import BaseFormAuthHandler

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.modem_config.schema import (
        FormNonceAuthConfig,
        ModemConfig,
    )

_LOGGER = logging.getLogger(__name__)


class FormNonceAuthHandler(BaseFormAuthHandler):
    """Handler for form authentication with client nonce.

    Simulates modems that use plain form POST with a client-generated nonce.
    The client submits:
    - username: plain text
    - password: plain text
    - ar_nonce: random digits (client-generated)

    Response is plain text:
    - "Url:/path" on success
    - "Error:message" on failure
    """

    AUTH_TYPE_KEY = "form_nonce"

    def __init__(
        self,
        config: ModemConfig,
        fixtures_path: Path,
        auth_redirect: str | None = None,
        response_delay: float = 0.0,
    ):
        """Initialize form nonce auth handler."""
        super().__init__(config, fixtures_path, auth_redirect=auth_redirect, response_delay=response_delay)
        # Type narrow the config
        self.form_config: FormNonceAuthConfig = cast("FormNonceAuthConfig", self.form_config)

    def handle_request(
        self,
        handler: BaseHTTPRequestHandler,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle HTTP request with form nonce authentication."""
        parsed = urlparse(path)
        clean_path = parsed.path

        # Handle login endpoint
        if method == "POST" and clean_path == self.form_config.endpoint:
            return self._handle_login(body, headers)

        # Check if authenticated for protected paths
        if self.is_protected_path(clean_path) and not self.is_authenticated(headers):
            return self.serve_login_page()

        # Serve the requested page
        return self.serve_fixture(clean_path)

    def _handle_login(
        self,
        body: bytes | None,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle form login submission."""
        if body is None:
            return self._error_response("No data submitted")

        form_data = self.parse_form_data(body)

        # Get plain credentials
        username_field = getattr(self.form_config, "username_field", "username")
        password_field = getattr(self.form_config, "password_field", "password")

        username = form_data.get(username_field, "")
        password = form_data.get(password_field, "")

        if not username or not password:
            return self._error_response("Missing credentials")

        _LOGGER.debug("Form nonce login attempt: username=%s", username)

        if self.validate_credentials(username, password):
            return self._handle_login_success()

        # Failed login
        _LOGGER.debug("Form nonce login failed: invalid credentials")
        return self._error_response("Invalid password")

    def _handle_login_success(self) -> tuple[int, dict[str, str], bytes]:
        """Handle successful login with plain text response."""
        _, cookie_value = self.create_session_cookie()

        # Return success response
        success_prefix = getattr(self.form_config, "success_prefix", "Url:")
        redirect_path = "/cgi-bin/status"  # Default redirect

        _LOGGER.debug("Form nonce login successful")
        return (
            200,
            {
                "Content-Type": "text/plain",
                "Set-Cookie": cookie_value,
            },
            f"{success_prefix}{redirect_path}".encode(),
        )

    def _error_response(self, message: str) -> tuple[int, dict[str, str], bytes]:
        """Return an error response."""
        error_prefix = getattr(self.form_config, "error_prefix", "Error:")
        return (
            200,
            {"Content-Type": "text/plain"},
            f"{error_prefix}{message}".encode(),
        )

    def synthesize_login_page(self) -> str:
        """Synthesize a minimal login page with form and nonce."""
        endpoint = getattr(self.form_config, "endpoint", "/cgi-bin/adv_pwd_cgi")
        username_field = getattr(self.form_config, "username_field", "username")
        password_field = getattr(self.form_config, "password_field", "password")
        nonce_field = getattr(self.form_config, "nonce_field", "ar_nonce")

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{self.get_page_title()}</title>
    <script>
    function getNonce() {{
        return Math.random().toString().substr(2, 8);
    }}
    function do_login() {{
        document.getElementById('{nonce_field}').value = getNonce();
        var form = document.getElementById('login_form');
        var formData = new FormData(form);

        var xhr = new XMLHttpRequest();
        xhr.open('POST', '{endpoint}', true);
        xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.onload = function() {{
            if (xhr.responseText.indexOf('Url:') === 0) {{
                window.location.href = xhr.responseText.substr(4);
            }} else {{
                alert(xhr.responseText.substr(6));
            }}
        }};
        var params = new URLSearchParams(formData).toString();
        xhr.send(params);
    }}
    </script>
</head>
<body>
    <h1>{self.get_page_heading()}</h1>
    <p>Form Nonce Login</p>
    <form id="login_form" onsubmit="do_login(); return false;">
        <input type="hidden" name="{nonce_field}" id="{nonce_field}">
        <label>Username: <input type="text" name="{username_field}" id="{username_field}"></label><br>
        <label>Password: <input type="password" name="{password_field}" id="{password_field}"></label><br>
        <input type="submit" value="Login">
    </form>
</body>
</html>
"""
