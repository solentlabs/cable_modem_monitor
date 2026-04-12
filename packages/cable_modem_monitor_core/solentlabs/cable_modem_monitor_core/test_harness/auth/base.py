"""Base auth handler — no authentication required.

Provides the ``AuthHandler`` base class used by all auth strategies.
When used directly, all requests are considered authenticated (no-auth
mode for ``auth: none`` modems).

Also provides the shared ``ActionConfig`` helper used by form-based
handler modules to extract logout/restart endpoints from modem config.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from ..routes import RouteEntry

if TYPE_CHECKING:
    from ...models.modem_config import ModemConfig


class ActionConfig(NamedTuple):
    """Shared action fields extracted from modem config.

    Simple data carrier for the cookie name, logout path, restart
    path, and restart method that form-based handler modules need.
    """

    cookie_name: str
    logout_path: str
    restart_path: str
    restart_method: str


def extract_action_config(modem_config: ModemConfig) -> ActionConfig:
    """Extract shared action fields from modem config.

    Reads session cookie name and action endpoints (logout, restart)
    from the config.
    """
    from ...models.modem_config.actions import HttpAction

    cookie_name = getattr(modem_config.auth, "cookie_name", "")
    logout_path = ""
    restart_path = ""
    restart_method = "POST"
    if modem_config.actions:
        if modem_config.actions.logout and isinstance(modem_config.actions.logout, HttpAction):
            logout_path = modem_config.actions.logout.endpoint
        if modem_config.actions.restart and isinstance(modem_config.actions.restart, HttpAction):
            restart_path = modem_config.actions.restart.endpoint
            restart_method = modem_config.actions.restart.method
    return ActionConfig(
        cookie_name=cookie_name,
        logout_path=logout_path,
        restart_path=restart_path,
        restart_method=restart_method,
    )


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

    def get_challenge_response(self) -> RouteEntry:
        """Return the 401 challenge response for unauthenticated requests."""
        return RouteEntry(status=401, headers=[], body="Unauthorized")

    def is_authenticated(self, headers: dict[str, str]) -> bool:
        """Check if the request is authenticated."""
        return True

    def set_authenticated(self) -> dict[str, str]:
        """Mark session as authenticated. Returns headers to add to response."""
        return {}

    def is_logout_request(self, method: str, path: str) -> bool:
        """Check if this request targets the logout endpoint."""
        return False

    def handle_logout(self) -> RouteEntry:
        """Handle a logout request. Clears session state."""
        return RouteEntry(status=200, headers=[], body="OK")

    def is_restart_request(self, method: str, path: str) -> bool:
        """Check if this request targets the restart endpoint."""
        return False

    def handle_restart(self) -> RouteEntry:
        """Handle a restart request. Returns 200 and clears session."""
        return RouteEntry(status=200, headers=[], body="OK")

    def get_route_override(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: dict[str, str],
    ) -> RouteEntry | None:
        """Override the route table for this request.

        Returns a ``RouteEntry`` to bypass the route table, or ``None``
        to use the standard route table lookup. Used by HNAP to serve
        merged data responses from a single endpoint.
        """
        return None
