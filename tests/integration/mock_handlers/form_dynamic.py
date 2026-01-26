"""Dynamic form authentication handler for MockModemServer.

Simulates modems where the login form action contains a dynamic parameter
that changes per page load (e.g., /goform/Login?id=XXXXXXXXXX).

The modem only accepts login submissions to the exact URL including the
dynamic ID. Submissions to the static action (without ?id=) are rejected.
"""

from __future__ import annotations

import logging
import secrets
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, urlparse

from .form_base import BaseFormAuthHandler

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.modem_config.schema import (
        FormDynamicAuthConfig,
        ModemConfig,
    )

_LOGGER = logging.getLogger(__name__)


class FormDynamicAuthHandler(BaseFormAuthHandler):
    """Handler for form authentication with dynamic action URLs.

    Simulates modems that generate a unique session ID in the form action
    on each page load. The modem rejects login attempts that don't include
    the correct dynamic ID.

    This reproduces the regression where FormPlain used the static
    action from modem.yaml, missing the required dynamic parameter.
    """

    AUTH_TYPE_KEY = "form_dynamic"

    def __init__(
        self,
        config: ModemConfig,
        fixtures_path: Path,
        auth_redirect: str | None = None,
    ):
        """Initialize dynamic form auth handler."""
        super().__init__(config, fixtures_path, auth_redirect=auth_redirect)
        # Type narrow the config
        self.form_config: FormDynamicAuthConfig = cast("FormDynamicAuthConfig", self.form_config)
        # Track the current valid dynamic ID
        self._current_dynamic_id: str | None = None

    def handle_request(
        self,
        handler: BaseHTTPRequestHandler,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle HTTP request with dynamic form authentication."""
        parsed = urlparse(path)
        clean_path = parsed.path
        query_params = parse_qs(parsed.query)

        # Handle login form submission
        if method == "POST" and clean_path == self.form_config.action:
            # Check if the dynamic ID is present and valid
            submitted_id = query_params.get("id", [None])[0]

            if not submitted_id:
                # No ID in URL - this is the bug we're reproducing
                _LOGGER.warning(
                    "Login rejected: missing dynamic ?id= parameter. "
                    "Static action '%s' submitted, but modem requires '%s?id=<dynamic>'",
                    clean_path,
                    clean_path,
                )
                return self._reject_invalid_action()

            if submitted_id != self._current_dynamic_id:
                # Wrong/expired ID
                _LOGGER.warning(
                    "Login rejected: invalid dynamic ID. Got '%s', expected '%s'",
                    submitted_id,
                    self._current_dynamic_id,
                )
                return self._reject_invalid_action()

            # Valid dynamic ID - process login
            return self._handle_login(body)

        # Check if authenticated for protected paths
        if self.is_protected_path(clean_path) and not self.is_authenticated(headers):
            return self._serve_login_page_with_dynamic_id()

        # Serve the requested page
        return self.serve_fixture(clean_path)

    def _reject_invalid_action(self) -> tuple[int, dict[str, str], bytes]:
        """Reject login attempt with invalid or missing dynamic ID.

        Simulates the real modem behavior: redirect back to login page.
        """
        # Generate new dynamic ID for the login page
        self._current_dynamic_id = self._generate_dynamic_id()

        return (
            302,
            {
                "Location": "/",
                "Content-Type": "text/html",
            },
            b"<html><body>Session expired. Please login again.</body></html>",
        )

    def _handle_login(self, body: bytes | None) -> tuple[int, dict[str, str], bytes]:
        """Handle login form submission."""
        if body is None:
            _LOGGER.debug("Login failed: no body")
            return self._serve_login_page_with_dynamic_id()

        form_data = self.parse_form_data(body)
        username = form_data.get(self.form_config.username_field, "")
        password = form_data.get(self.form_config.password_field, "")

        _LOGGER.debug("Login attempt: username=%s", username)

        if self.validate_credentials(username, password):
            redirect_url = "/DocsisStatus.htm"
            if self.form_config.success and self.form_config.success.redirect:
                redirect_url = self.form_config.success.redirect
            return self.handle_login_success_redirect(redirect_url)

        # Failed login - return to login page
        _LOGGER.debug("Login failed")
        return self._serve_login_page_with_dynamic_id()

    def _serve_login_page_with_dynamic_id(self) -> tuple[int, dict[str, str], bytes]:
        """Serve the login page with a fresh dynamic ID."""
        # Generate new dynamic ID
        self._current_dynamic_id = self._generate_dynamic_id()
        _LOGGER.debug("Generated dynamic ID: %s", self._current_dynamic_id)

        # Try to serve login.html fixture (if exists, inject the dynamic action)
        login_fixture = self.get_fixture_content("/login.html")
        if login_fixture:
            # Inject dynamic action into existing fixture
            html = login_fixture.decode("utf-8")
            dynamic_action = f"{self.form_config.action}?id={self._current_dynamic_id}"
            # Replace static action with dynamic one
            html = html.replace(
                f'action="{self.form_config.action}"',
                f'action="{dynamic_action}"',
            )
            return 200, {"Content-Type": "text/html; charset=utf-8"}, html.encode()

        # Synthesize minimal login form with dynamic action
        login_html = self.synthesize_login_page()
        return 200, {"Content-Type": "text/html; charset=utf-8"}, login_html.encode()

    def synthesize_login_page(self) -> str:
        """Synthesize a minimal login page with dynamic form action."""
        username_field = self.form_config.username_field
        password_field = self.form_config.password_field
        method = self.form_config.method or "POST"

        # Dynamic action URL with ID
        dynamic_action = f"{self.form_config.action}?id={self._current_dynamic_id}"

        # Build hidden fields
        hidden_inputs = ""
        if self.form_config.hidden_fields:
            for name, value in self.form_config.hidden_fields.items():
                hidden_inputs += f'<input type="hidden" name="{name}" value="{value}">\n'

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{self.get_page_title()}</title>
</head>
<body>
    <h1>{self.get_page_heading()}</h1>
    <p>Login form with dynamic action URL</p>
    <form name="loginform" action="{dynamic_action}" method="{method}">
        {hidden_inputs}
        <label>Username: <input type="text" name="{username_field}" id="username"></label><br>
        <label>Password: <input type="password" name="{password_field}" id="password"></label><br>
        <input type="submit" value="Login">
    </form>
    <!-- Debug: Dynamic ID = {self._current_dynamic_id} -->
</body>
</html>
"""

    def _generate_dynamic_id(self) -> str:
        """Generate a random dynamic ID."""
        return secrets.token_hex(8).upper()
