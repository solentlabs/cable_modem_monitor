"""Form authentication handler for MockModemServer.

Handles form-based authentication (plain and base64 encoded).
Implements FORM_PLAIN and FORM_BASE64 auth patterns.
"""

from __future__ import annotations

import base64
import logging
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import unquote, urlparse

from .base import BaseAuthHandler

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.modem_config.schema import (
        FormAuthConfig,
        ModemConfig,
    )

_LOGGER = logging.getLogger(__name__)

# Test credentials for MockModemServer - use "pw" instead of "password" to avoid
# browser password managers flagging these as real credentials during development
TEST_USERNAME = "admin"
TEST_PASSWORD = "pw"


class FormAuthHandler(BaseAuthHandler):
    """Handler for form-based authentication.

    Supports both plain and base64-encoded password submissions.
    """

    def __init__(self, config: ModemConfig, fixtures_path: Path):
        """Initialize form auth handler.

        Args:
            config: Modem configuration.
            fixtures_path: Path to fixtures directory.
        """
        super().__init__(config, fixtures_path)

        # Extract form config from auth.types{}
        form_config = config.auth.types.get("form")
        if not form_config:
            raise ValueError("Form auth handler requires form config in auth.types")
        self.form_config: FormAuthConfig = cast("FormAuthConfig", form_config)

    def handle_request(
        self,
        handler: BaseHTTPRequestHandler,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle HTTP request with form authentication.

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

        # Form config is required for this handler
        assert self.form_config is not None, "FormAuthHandler requires form_config"

        # Handle login form submission
        if method == "POST" and clean_path == self.form_config.action:
            return self._handle_login(body, headers)

        # Check if authenticated for protected paths
        if self.is_protected_path(clean_path) and not self.is_authenticated(headers):
            # Return login page
            return self._serve_login_page()

        # Serve the requested page
        return self.serve_fixture(clean_path)

    def _handle_login(
        self,
        body: bytes | None,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle login form submission.

        Args:
            body: POST body with form data.
            headers: Request headers.

        Returns:
            Response tuple.
        """
        assert self.form_config is not None, "FormAuthHandler requires form_config"
        assert body is not None, "POST body is required for login"

        form_data = self.parse_form_data(body)

        username = form_data.get(self.form_config.username_field, "")
        password_raw = form_data.get(self.form_config.password_field, "")

        # Decode password based on encoding
        password = self._decode_password(password_raw)

        _LOGGER.debug(
            "Login attempt: username=%s, password=%s (raw=%s)",
            username,
            password,
            password_raw,
        )

        # Validate credentials
        if username == TEST_USERNAME and password == TEST_PASSWORD:
            return self._handle_login_success()
        else:
            return self._handle_login_failure()

    def _decode_password(self, password_raw: str) -> str:
        """Decode password based on configured encoding.

        Args:
            password_raw: Raw password from form.

        Returns:
            Decoded password.
        """
        from custom_components.cable_modem_monitor.modem_config.schema import (
            PasswordEncoding,
        )

        assert self.form_config is not None, "FormAuthHandler requires form_config"
        encoding = self.form_config.password_encoding

        if encoding == PasswordEncoding.BASE64:
            try:
                # Base64 decode, then URL decode (JavaScript escape() then btoa())
                decoded_bytes = base64.b64decode(password_raw)
                url_encoded = decoded_bytes.decode("utf-8")
                return unquote(url_encoded)
            except Exception as e:
                _LOGGER.warning("Failed to decode base64 password: %s", e)
                return password_raw

        # Plain encoding - return as-is
        return password_raw

    def _handle_login_success(self) -> tuple[int, dict[str, str], bytes]:
        """Handle successful login.

        Returns:
            Redirect response with session cookie.
        """
        assert self.form_config is not None, "FormAuthHandler requires form_config"

        session_id = self.create_session()

        # Get cookie name from session config or use default
        cookie_name = "session"
        if self.config.auth.session and self.config.auth.session.cookie_name:
            cookie_name = self.config.auth.session.cookie_name

        # Determine redirect location
        redirect_url = "/MotoHome.asp"  # Default
        if self.form_config.success and self.form_config.success.redirect:
            redirect_url = self.form_config.success.redirect

        response_headers = {
            "Location": redirect_url,
            "Set-Cookie": f"{cookie_name}={session_id}; Path=/",
        }

        _LOGGER.debug("Login successful, redirecting to %s", redirect_url)

        return 302, response_headers, b""

    def _handle_login_failure(self) -> tuple[int, dict[str, str], bytes]:
        """Handle failed login.

        Returns:
            Login page again with error indication.
        """
        _LOGGER.debug("Login failed")
        return self._serve_login_page()

    def _serve_login_page(self) -> tuple[int, dict[str, str], bytes]:
        """Serve the login page.

        If a login.html fixture exists, serve it.
        Otherwise, synthesize a minimal login form.

        Returns:
            Response tuple.
        """
        # Try to serve login.html fixture
        login_fixture = self.get_fixture_content("/login.html")
        if login_fixture:
            return 200, {"Content-Type": "text/html; charset=utf-8"}, login_fixture

        # Synthesize minimal login form
        login_html = self._synthesize_login_page()
        return 200, {"Content-Type": "text/html; charset=utf-8"}, login_html.encode()

    def _synthesize_login_page(self) -> str:
        """Synthesize a minimal login page from form config.

        Returns:
            HTML string.
        """
        assert self.form_config is not None, "FormAuthHandler requires form_config"

        username_field = self.form_config.username_field
        password_field = self.form_config.password_field
        action = self.form_config.action
        method = self.form_config.method or "POST"

        # Build hidden fields
        hidden_inputs = ""
        if self.form_config.hidden_fields:
            for name, value in self.form_config.hidden_fields.items():
                hidden_inputs += f'<input type="hidden" name="{name}" value="{value}">\n'

        # Check if base64 encoding is needed
        from custom_components.cable_modem_monitor.modem_config.schema import (
            PasswordEncoding,
        )

        encode_script = ""
        onsubmit = ""
        if self.form_config.password_encoding == PasswordEncoding.BASE64:
            encode_script = """
<script>
function encodePassword() {
    var pass = document.getElementById('password').value;
    var encoded = btoa(escape(pass));
    document.getElementById('password').value = encoded;
    return true;
}
</script>
"""
            onsubmit = ' onsubmit="return encodePassword()"'

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{self.config.manufacturer} {self.config.model} - Login</title>
    {encode_script}
</head>
<body>
    <h1>{self.config.manufacturer} {self.config.model}</h1>
    <form action="{action}" method="{method}"{onsubmit}>
        {hidden_inputs}
        <label>Username: <input type="text" name="{username_field}" id="username"></label><br>
        <label>Password: <input type="password" name="{password_field}" id="password"></label><br>
        <input type="submit" value="Login">
    </form>
</body>
</html>
"""
