"""HTTP Basic Authentication handler.

Checks that an Authorization header with the Basic scheme is present.
Stateless — no session tracking.
"""

from __future__ import annotations

from .base import AuthHandler


class BasicAuthHandler(AuthHandler):
    """HTTP Basic Authentication handler.

    Checks that an Authorization header with the Basic scheme is
    present. Credentials are not validated — any Basic header is
    accepted. Real credential validation lives in the auth managers.
    Stateless — no session tracking.
    """

    def is_authenticated(self, headers: dict[str, str]) -> bool:
        """Check for valid Basic auth header."""
        auth_header = headers.get("authorization", "")
        return auth_header.lower().startswith("basic ")
