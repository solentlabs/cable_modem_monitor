"""Auth handlers — driven by modem.yaml config.

Validate login requests and track session state. No modem-specific
logic — behavior is parameterized by config values.
"""

from __future__ import annotations

import logging
from typing import Any

from .routes import RouteEntry, normalize_path

_logger = logging.getLogger(__name__)


class AuthHandler:
    """Base auth handler — no authentication required.

    Used for ``auth: none`` modems. All requests are considered
    authenticated.
    """

    def is_login_request(self, method: str, path: str) -> bool:
        """Check if this request targets the login endpoint."""
        return False

    def handle_login(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: dict[str, str],
    ) -> RouteEntry | None:
        """Handle a login request. Returns response or None to pass through."""
        return None

    def is_authenticated(self, headers: dict[str, str]) -> bool:
        """Check if the request is authenticated."""
        return True

    def set_authenticated(self) -> dict[str, str]:
        """Mark session as authenticated. Returns headers to add to response."""
        return {}


class FormAuthHandler(AuthHandler):
    """Form-based authentication handler.

    Validates that a POST is made to the configured login endpoint.
    Tracks session state via a server-side flag (works for both
    cookie-based and IP-based modems — in tests all traffic is
    localhost).

    Args:
        login_path: The login endpoint path (from modem.yaml ``auth.action``).
        cookie_name: Session cookie name if cookie-based (from
            modem.yaml ``session.cookie_name``). Empty for IP-based.
    """

    _SESSION_TOKEN = "mock-session-token"

    def __init__(self, login_path: str, cookie_name: str = "") -> None:
        self._login_path = normalize_path(login_path)
        self._cookie_name = cookie_name
        self._authenticated = False

    def is_login_request(self, method: str, path: str) -> bool:
        """Check if this is a POST to the login endpoint."""
        return method == "POST" and normalize_path(path) == self._login_path

    def handle_login(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: dict[str, str],
    ) -> RouteEntry | None:
        """Accept login POST and set session state.

        Returns None — caller uses the route table response.
        """
        if not self.is_login_request(method, path):
            return None

        self._authenticated = True
        _logger.debug("Mock server: login accepted at %s", path)
        return None

    def is_authenticated(self, headers: dict[str, str]) -> bool:
        """Check session state."""
        if self._authenticated:
            return True

        if self._cookie_name:
            cookie_header = headers.get("cookie", "")
            if self._cookie_name in cookie_header:
                self._authenticated = True
                return True

        return False

    def set_authenticated(self) -> dict[str, str]:
        """Return Set-Cookie header if cookie-based session."""
        if self._cookie_name:
            return {"Set-Cookie": f"{self._cookie_name}={self._SESSION_TOKEN}; Path=/"}
        return {}


class BasicAuthHandler(AuthHandler):
    """HTTP Basic Authentication handler.

    Validates that an Authorization header with the Basic scheme is
    present. Stateless — no session tracking.
    """

    def is_authenticated(self, headers: dict[str, str]) -> bool:
        """Check for valid Basic auth header."""
        auth_header = headers.get("authorization", "")
        return auth_header.lower().startswith("basic ")


def create_auth_handler(
    modem_config: dict[str, Any] | None,
) -> AuthHandler:
    """Create the appropriate auth handler from modem config.

    Args:
        modem_config: Modem config dict (or None for no auth). Uses
            ``auth.strategy`` to select the handler and
            ``session.cookie_name`` for session tracking.

    Returns:
        Auth handler instance.
    """
    if modem_config is None:
        return AuthHandler()

    auth = modem_config.get("auth")
    if auth is None:
        return AuthHandler()

    strategy = auth.get("strategy", "none") if isinstance(auth, dict) else getattr(auth, "strategy", "none")

    if strategy == "none":
        return AuthHandler()

    if strategy == "basic":
        return BasicAuthHandler()

    if strategy in ("form", "form_nonce", "form_pbkdf2"):
        login_path = ""
        if isinstance(auth, dict):
            login_path = auth.get("action", "") or auth.get("login_endpoint", "")
        else:
            login_path = getattr(auth, "action", "") or getattr(auth, "login_endpoint", "")

        session = modem_config.get("session")
        cookie_name = ""
        if session is not None:
            cookie_name = (
                session.get("cookie_name", "") if isinstance(session, dict) else getattr(session, "cookie_name", "")
            )

        return FormAuthHandler(login_path=login_path, cookie_name=cookie_name)

    _logger.warning("Unsupported auth strategy '%s' in mock server, using no-auth", strategy)
    return AuthHandler()
