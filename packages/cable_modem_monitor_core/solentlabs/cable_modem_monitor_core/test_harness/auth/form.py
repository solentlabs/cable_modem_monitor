"""Form-based authentication handler.

Validates that a POST is made to the configured login endpoint.
Tracks session state via a server-side flag (works for both
cookie-based and IP-based sessions).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..routes import RouteEntry, normalize_path
from .base import AuthHandler, extract_action_config

if TYPE_CHECKING:
    from ...models.modem_config import ModemConfig

_logger = logging.getLogger(__name__)


class FormAuthHandler(AuthHandler):
    """Form-based authentication handler.

    Validates that a POST is made to the configured login endpoint.
    Tracks session state via a server-side flag (works for both
    cookie-based and IP-based modems — in tests all traffic is
    localhost).

    Credentials are not validated — any POST to the login path is
    accepted. Real credential validation lives in the auth managers
    (``auth/``). This handler only gates access by session state.

    Args:
        login_path: The login endpoint path (from modem.yaml ``auth.action``).
        cookie_name: Session cookie name if cookie-based (from
            modem.yaml ``auth.cookie_name``). Empty for IP-based.
        logout_path: The logout endpoint path (from modem.yaml
            ``actions.logout.endpoint``). Empty if no logout.
        restart_path: The restart endpoint path (from modem.yaml
            ``actions.restart.endpoint``). Empty if no restart.
        restart_method: HTTP method for restart (default POST).
    """

    _SESSION_TOKEN = "mock-session-token"

    def __init__(
        self,
        login_path: str,
        cookie_name: str = "",
        logout_path: str = "",
        restart_path: str = "",
        restart_method: str = "POST",
    ) -> None:
        self._login_path = normalize_path(login_path)
        self._cookie_name = cookie_name
        self._logout_path = normalize_path(logout_path) if logout_path else ""
        self._restart_path = normalize_path(restart_path) if restart_path else ""
        self._restart_method = restart_method.upper()
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

        Returns None so the server falls through to the route table and
        serves the HAR response verbatim. A missing login entry in the HAR
        produces a 404, which fails the test — this is intentional. HAR
        fixtures must include the full auth flow; validate_har enforces this
        at intake time.
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

    def is_logout_request(self, method: str, path: str) -> bool:
        """Check if this request targets the logout endpoint."""
        if not self._logout_path:
            return False
        return normalize_path(path) == self._logout_path

    def handle_logout(self) -> RouteEntry:
        """Clear session state on logout."""
        self._authenticated = False
        _logger.debug("Mock server: logout — session cleared")
        return RouteEntry(status=200, headers=[], body="OK")

    def is_restart_request(self, method: str, path: str) -> bool:
        """Check if this request targets the restart endpoint."""
        if not self._restart_path:
            return False
        return method == self._restart_method and normalize_path(path) == self._restart_path

    def handle_restart(self) -> RouteEntry:
        """Accept restart and clear session (modem is rebooting)."""
        self._authenticated = False
        _logger.debug("Mock server: restart accepted — session cleared")
        return RouteEntry(status=200, headers=[], body="OK")


def create_handler(
    modem_config: ModemConfig,
    har_entries: list[dict[str, Any]] | None = None,
) -> FormAuthHandler:
    """Entry point for dynamic auth handler dispatch."""
    auth = modem_config.auth
    login_path = getattr(auth, "action", "") or getattr(auth, "login_endpoint", "")
    action_cfg = extract_action_config(modem_config)
    return FormAuthHandler(
        login_path=login_path,
        cookie_name=action_cfg.cookie_name,
        logout_path=action_cfg.logout_path,
        restart_path=action_cfg.restart_path,
        restart_method=action_cfg.restart_method,
    )
