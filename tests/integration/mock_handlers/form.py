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

from .form_base import TEST_PASSWORD, TEST_USERNAME, BaseFormAuthHandler

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.modem_config.schema import (
        FormAuthConfig,
        ModemConfig,
    )

_LOGGER = logging.getLogger(__name__)

# Re-export for backwards compatibility
__all__ = ["FormAuthHandler", "TEST_USERNAME", "TEST_PASSWORD"]


class FormAuthHandler(BaseFormAuthHandler):
    """Handler for form-based authentication.

    Supports both plain and base64-encoded password submissions.
    """

    AUTH_TYPE_KEY = "form"

    def __init__(
        self,
        config: ModemConfig,
        fixtures_path: Path,
        auth_redirect: str | None = None,
    ):
        """Initialize form auth handler."""
        super().__init__(config, fixtures_path, auth_redirect=auth_redirect)
        # Type narrow the config
        self.form_config: FormAuthConfig = cast("FormAuthConfig", self.form_config)

    def handle_request(
        self,
        handler: BaseHTTPRequestHandler,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle HTTP request with form authentication."""
        parsed = urlparse(path)
        clean_path = parsed.path

        # Handle login form submission
        if method == "POST" and clean_path == self.form_config.action:
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
        """Handle login form submission."""
        if body is None:
            _LOGGER.debug("Login failed: no body")
            return self.serve_login_page()

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

        if self.validate_credentials(username, password):
            return self._handle_login_success()
        else:
            return self._handle_login_failure()

    def _decode_password(self, password_raw: str) -> str:
        """Decode password based on configured encoding."""
        from custom_components.cable_modem_monitor.modem_config.schema import (
            PasswordEncoding,
        )

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
        """Handle successful login."""
        # Use override if set (for testing auth redirect scenarios)
        if self.auth_redirect_override:
            redirect_url = self.auth_redirect_override
        elif self.form_config.success and self.form_config.success.redirect:
            redirect_url = self.form_config.success.redirect
        else:
            redirect_url = "/MotoHome.asp"  # Default

        return self.handle_login_success_redirect(redirect_url)

    def _handle_login_failure(self) -> tuple[int, dict[str, str], bytes]:
        """Handle failed login."""
        _LOGGER.debug("Login failed")
        return self.serve_login_page()

    def synthesize_login_page(self) -> str:
        """Synthesize a minimal login page from form config."""
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
    <title>{self.get_page_title()}</title>
    {encode_script}
</head>
<body>
    <h1>{self.get_page_heading()}</h1>
    <form action="{action}" method="{method}"{onsubmit}>
        {hidden_inputs}
        <label>Username: <input type="text" name="{username_field}" id="username"></label><br>
        <label>Password: <input type="password" name="{password_field}" id="password"></label><br>
        <input type="submit" value="Login">
    </form>
</body>
</html>
"""
