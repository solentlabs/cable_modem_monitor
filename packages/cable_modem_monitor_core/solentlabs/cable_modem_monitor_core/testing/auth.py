"""Auth handlers — driven by modem.yaml config.

Validate login requests and track session state. No modem-specific
logic — behavior is parameterized by config values.

HNAP handler lives in ``auth_hnap.py`` (separate domain: HMAC crypto,
JSON SOAP protocol, HAR response merging).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .routes import RouteEntry, normalize_path

if TYPE_CHECKING:
    from ..models.modem_config import ModemConfig

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
    modem_config: ModemConfig | None,
    har_entries: list[dict[str, Any]] | None = None,
) -> AuthHandler:
    """Create the appropriate auth handler from modem config.

    Args:
        modem_config: Validated ``ModemConfig`` instance (or None for no auth).
            Uses ``auth.strategy`` to select the handler and
            ``session.cookie_name`` for session tracking.
        har_entries: HAR ``log.entries`` list. Required for HNAP auth
            to build the merged data response. Ignored for other
            strategies.

    Returns:
        Auth handler instance.
    """
    from ..models.modem_config.auth import (
        BasicAuth,
        FormAuth,
        FormNonceAuth,
        FormPbkdf2Auth,
        HnapAuth,
        NoneAuth,
        UrlTokenAuth,
    )

    if modem_config is None or modem_config.auth is None:
        return AuthHandler()

    auth = modem_config.auth

    if isinstance(auth, NoneAuth):
        return AuthHandler()

    if isinstance(auth, BasicAuth):
        return BasicAuthHandler()

    if isinstance(auth, FormAuth | FormNonceAuth | FormPbkdf2Auth):
        login_path = getattr(auth, "action", "") or getattr(auth, "login_endpoint", "")
        cookie_name = ""
        if modem_config.session is not None:
            cookie_name = modem_config.session.cookie_name
        return FormAuthHandler(login_path=login_path, cookie_name=cookie_name)

    if isinstance(auth, UrlTokenAuth):
        # URL token auth GETs the login page with credentials in the URL.
        # The HAR route table already contains the login page response
        # (with success indicator text and Set-Cookie header), so no
        # auth gating is needed — all requests pass through.
        return AuthHandler()

    if isinstance(auth, HnapAuth):
        from .auth_hnap import HnapAuthHandler

        return HnapAuthHandler(
            hmac_algorithm=auth.hmac_algorithm,
            har_entries=har_entries or [],
        )

    _logger.warning("Unsupported auth strategy '%s' in mock server, using no-auth", type(auth).__name__)
    return AuthHandler()
