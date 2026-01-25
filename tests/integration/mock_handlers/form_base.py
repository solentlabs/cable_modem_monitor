"""Base class for form-based authentication handlers.

Provides common functionality shared by FormAuthHandler, FormDynamicAuthHandler,
and FormAjaxAuthHandler.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .base import BaseAuthHandler

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.modem_config.schema import ModemConfig

_LOGGER = logging.getLogger(__name__)

# Test credentials for MockModemServer - use "pw" instead of "password" to avoid
# browser password managers flagging these as real credentials during development
TEST_USERNAME = "admin"
TEST_PASSWORD = "pw"


class BaseFormAuthHandler(BaseAuthHandler):
    """Base class for form-based authentication handlers.

    Subclasses implement specific form auth strategies:
    - FormAuthHandler: Traditional form POST with optional password encoding
    - FormDynamicAuthHandler: Form POST with dynamic action URL
    - FormAjaxAuthHandler: AJAX-based login with base64 credentials
    """

    # Subclasses must define the auth type key for config lookup
    AUTH_TYPE_KEY: str = ""

    def __init__(self, config: ModemConfig, fixtures_path: Path):
        """Initialize form auth handler.

        Args:
            config: Modem configuration from modem.yaml.
            fixtures_path: Path to fixtures directory.
        """
        super().__init__(config, fixtures_path)
        self.form_config = self._load_form_config()

    def _load_form_config(self) -> Any:
        """Load and validate form config from auth.types.

        Returns:
            The typed form config object.

        Raises:
            ValueError: If required config is missing.
        """
        if not self.AUTH_TYPE_KEY:
            raise NotImplementedError("Subclass must define AUTH_TYPE_KEY")

        form_config = self.config.auth.types.get(self.AUTH_TYPE_KEY)
        if not form_config:
            raise ValueError(f"{self.__class__.__name__} requires {self.AUTH_TYPE_KEY} config in auth.types")
        return form_config

    @abstractmethod
    def handle_request(
        self,
        handler: BaseHTTPRequestHandler,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle an HTTP request (implemented by subclasses)."""

    def get_cookie_name(self) -> str:
        """Get session cookie name from config or use default.

        Returns:
            Cookie name string.
        """
        if self.config.auth.session and self.config.auth.session.cookie_name:
            return self.config.auth.session.cookie_name
        return "session"

    def create_session_cookie(self) -> tuple[str, str]:
        """Create a session and return cookie header.

        Returns:
            Tuple of (session_id, cookie_header_value).
        """
        session_id = self.create_session()
        cookie_name = self.get_cookie_name()
        cookie_value = f"{cookie_name}={session_id}; Path=/"
        return session_id, cookie_value

    def handle_login_success_redirect(
        self,
        redirect_url: str,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle successful login with redirect response.

        Args:
            redirect_url: URL to redirect to after login.

        Returns:
            Response tuple with 302 redirect.
        """
        _, cookie_value = self.create_session_cookie()

        _LOGGER.debug("Login successful, redirecting to %s", redirect_url)

        return (
            302,
            {
                "Location": redirect_url,
                "Set-Cookie": cookie_value,
            },
            b"",
        )

    def validate_credentials(self, username: str, password: str) -> bool:
        """Validate login credentials against test credentials.

        Args:
            username: Submitted username.
            password: Submitted password (decoded).

        Returns:
            True if credentials match.
        """
        return username == TEST_USERNAME and password == TEST_PASSWORD

    def serve_login_page(self) -> tuple[int, dict[str, str], bytes]:
        """Serve the login page.

        Tries login.html fixture first, falls back to synthesized form.

        Returns:
            Response tuple with login HTML.
        """
        # Try to serve login.html fixture if exists
        login_fixture = self.get_fixture_content("/login.html")
        if login_fixture:
            return 200, {"Content-Type": "text/html; charset=utf-8"}, login_fixture

        # Synthesize minimal login form
        login_html = self.synthesize_login_page()
        return 200, {"Content-Type": "text/html; charset=utf-8"}, login_html.encode()

    @abstractmethod
    def synthesize_login_page(self) -> str:
        """Synthesize a minimal login page HTML.

        Returns:
            HTML string for login page.
        """

    def get_page_title(self) -> str:
        """Get page title from modem config.

        Returns:
            Title string like "ARRIS SB8200 - Login".
        """
        return f"{self.config.manufacturer} {self.config.model} - Login"

    def get_page_heading(self) -> str:
        """Get page heading from modem config.

        Returns:
            Heading string like "ARRIS SB8200".
        """
        return f"{self.config.manufacturer} {self.config.model}"
