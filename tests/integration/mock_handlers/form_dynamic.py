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
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from .base import BaseAuthHandler

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.modem_config.schema import ModemConfig

_LOGGER = logging.getLogger(__name__)


class FormDynamicAuthHandler(BaseAuthHandler):
    """Handler for form authentication with dynamic action URLs.

    Simulates modems that generate a unique session ID in the form action
    on each page load. The modem rejects login attempts that don't include
    the correct dynamic ID.

    This reproduces the regression where FormPlain used the static
    action from modem.yaml, missing the required dynamic parameter.
    """

    def __init__(self, config: ModemConfig, fixtures_path: Path):
        """Initialize dynamic form auth handler.

        Args:
            config: Modem configuration.
            fixtures_path: Path to fixtures directory.
        """
        super().__init__(config, fixtures_path)

        # Track the current valid dynamic ID
        # A new ID is generated each time the login page is served
        self._current_dynamic_id: str | None = None

        # Get form_dynamic config (required for this handler)
        self.form_config = config.auth.types.get("form_dynamic")
        if not self.form_config:
            raise ValueError("FormDynamicAuthHandler requires form_dynamic config in auth.types")

    def handle_request(
        self,
        handler: BaseHTTPRequestHandler,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle HTTP request with dynamic form authentication.

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
        query_params = parse_qs(parsed.query)

        assert self.form_config is not None, "FormDynamicAuthHandler requires form_config"

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
            # Return login page with new dynamic ID
            return self._serve_login_page()

        # Serve the requested page
        return self.serve_fixture(clean_path)

    def _reject_invalid_action(self) -> tuple[int, dict[str, str], bytes]:
        """Reject login attempt with invalid or missing dynamic ID.

        Simulates the real modem behavior: redirect back to login page.
        This is what causes the 362-byte response (login redirect) instead
        of the expected 63KB data page.

        Returns:
            Redirect response back to login page.
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
        """Handle login form submission.

        Args:
            body: POST body with form data.

        Returns:
            Response tuple.
        """
        from .form import TEST_PASSWORD, TEST_USERNAME

        assert self.form_config is not None
        assert body is not None, "POST body is required for login"

        form_data = self.parse_form_data(body)
        username = form_data.get(self.form_config.username_field, "")
        password = form_data.get(self.form_config.password_field, "")

        _LOGGER.debug("Login attempt: username=%s", username)

        if username == TEST_USERNAME and password == TEST_PASSWORD:
            # Success - create session and redirect
            session_id = self.create_session()
            cookie_name = "session"
            if self.config.auth.session and self.config.auth.session.cookie_name:
                cookie_name = self.config.auth.session.cookie_name

            redirect_url = "/DocsisStatus.htm"
            if self.form_config.success and self.form_config.success.redirect:
                redirect_url = self.form_config.success.redirect

            _LOGGER.debug("Login successful, redirecting to %s", redirect_url)
            return (
                302,
                {
                    "Location": redirect_url,
                    "Set-Cookie": f"{cookie_name}={session_id}; Path=/",
                },
                b"",
            )

        # Failed login - return to login page
        _LOGGER.debug("Login failed")
        return self._serve_login_page()

    def _serve_login_page(self) -> tuple[int, dict[str, str], bytes]:
        """Serve the login page with a fresh dynamic ID.

        Generates a new dynamic ID and embeds it in the form action.

        Returns:
            Response tuple.
        """
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
        login_html = self._synthesize_login_page()
        return 200, {"Content-Type": "text/html; charset=utf-8"}, login_html.encode()

    def _synthesize_login_page(self) -> str:
        """Synthesize a minimal login page with dynamic form action.

        Returns:
            HTML string with form action containing dynamic ID.
        """
        assert self.form_config is not None, "FormDynamicAuthHandler requires form_config"

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
    <title>{self.config.manufacturer} {self.config.model} - Login</title>
</head>
<body>
    <h1>{self.config.manufacturer} {self.config.model}</h1>
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
        """Generate a random dynamic ID.

        Returns:
            Random alphanumeric string (simulates modem's session ID generator).
        """
        return secrets.token_hex(8).upper()
