"""Base auth handler — no authentication required.

Provides the ``AuthHandler`` base class used by all auth strategies.
When used directly, all requests are considered authenticated (no-auth
mode for ``auth: none`` modems).
"""

from __future__ import annotations

from ..routes import RouteEntry


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
