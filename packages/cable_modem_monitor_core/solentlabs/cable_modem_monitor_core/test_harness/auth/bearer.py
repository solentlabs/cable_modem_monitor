"""Bearer token auth handler.

Serves a token from the login endpoint and requires it back as
``Authorization: Bearer <token>`` on subsequent requests.

When the capture holds the login response, it is served verbatim and
the token it carries is the one enforced. This is what makes a logout
that addresses the session in its URL replayable: the captured logout
path contains the captured token, so Core has to be carrying that same
token for the request to match. Enforcement compares against what the
client sends, which is derived from the login *body* — never against
the captured ``Authorization`` header, because har-capture sanitizes
bodies and headers independently and the two carry different values.

Without a captured login response the handler synthesizes one from
``token_path``, so the real ``BearerAuthManager`` still extracts the
token by the same walk it uses against hardware. Answers
``201 Created`` — the status the Sagemcom F3896LG firmware returns for
token creation (issue #185).

The declared shape is simulated too. The login answers only the
configured ``method``. With ``token_source: header`` the token travels
in the ``token_header`` response header, taken from the captured login
when it carries one, otherwise synthesized over an empty ``200`` body.
Later requests must carry the token where ``token_placement`` puts it:
``Authorization: Bearer``, the named request header, or the bare
``{token_prefix}{token}`` query key.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Literal

from ..routes import RouteEntry, build_routes, normalize_path
from .base import AuthHandler

if TYPE_CHECKING:
    from ...models.modem_config import ModemConfig

_logger = logging.getLogger(__name__)

_MOCK_TOKEN = "mock-bearer-token"


def _nest(token_path: str, token: str) -> dict[str, Any]:
    """Build the response body that ``token_path`` walks down to reach the token."""
    keys = token_path.split(".")
    body: dict[str, Any] = {keys[-1]: token}
    for key in reversed(keys[:-1]):
        body = {key: body}
    return body


class BearerAuthHandler(AuthHandler):
    """Issues a bearer token at the login endpoint and enforces it thereafter."""

    def __init__(
        self,
        login_path: str,
        token_path: str,
        captured_login: RouteEntry | None = None,
        *,
        method: Literal["POST", "PUT"] = "POST",
        token_source: Literal["body", "header"] = "body",
        token_header: str = "",
        token_placement: Literal["authorization", "header", "query"] = "authorization",
        token_prefix: str = "",
    ) -> None:
        super().__init__()
        self._login_path = normalize_path(login_path)
        self._token_path = token_path
        self._captured_login = captured_login
        self._method = method
        self._token_source = token_source
        self._token_header = token_header
        self._token_placement = token_placement
        self._token_prefix = token_prefix
        self._token = ""
        if captured_login is not None:
            if token_source == "header":
                self._token = _header_value(captured_login, token_header)
            else:
                self._token = _extract_token(captured_login, token_path)

    def is_login_request(self, method: str, path: str) -> bool:
        """Check if this is the configured method to the login endpoint."""
        return method == self._method and normalize_path(path) == self._login_path

    def handle_login(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: dict[str, str],
    ) -> RouteEntry | None:
        """Serve the captured login response, or a synthesized one when it carries no token."""
        if not self.is_login_request(method, path):
            return None

        if self._token and self._captured_login is not None:
            _logger.debug("Mock server: bearer login served from capture at %s", path)
            return self._captured_login

        _logger.debug("Mock server: bearer login accepted at %s", path)
        if self._token_source == "header":
            return RouteEntry(status=200, headers=[(self._token_header, _MOCK_TOKEN)], body="")
        return RouteEntry(
            status=201,
            headers=[("Content-Type", "application/json")],
            body=json.dumps(_nest(self._token_path, _MOCK_TOKEN)),
        )

    def is_authenticated(self, headers: dict[str, str], *, query: str = "") -> bool:
        """Require the issued token back where token_placement puts it."""
        token = self._token or _MOCK_TOKEN
        if self._token_placement == "header":
            return headers.get(self._token_header.lower(), "") == token
        if self._token_placement == "query":
            # The firmware sends a bare key (``?ct_<token>``), not key=value,
            # possibly alongside other params such as a cache-buster.
            return f"{self._token_prefix}{token}" in query.split("&")
        return headers.get("authorization", "") == f"Bearer {token}"

    def get_challenge_response(self) -> RouteEntry:
        """Return 401 for requests arriving without the bearer token."""
        return RouteEntry(status=401, headers=[], body="Unauthorized")

    def handle_restart(self, *, body: bytes = b"") -> RouteEntry:
        """Accept restart — the modem is rebooting, so the token dies with it."""
        _logger.debug("Mock server: restart accepted — bearer token invalidated")
        return RouteEntry(status=200, headers=[], body="OK")


def _extract_token(login_response: RouteEntry, token_path: str) -> str:
    """Walk ``token_path`` down the captured login body; empty if it does not resolve."""
    try:
        value: Any = json.loads(login_response.body)
    except (TypeError, ValueError):
        return ""
    for key in token_path.split("."):
        if not isinstance(value, dict) or key not in value:
            return ""
        value = value[key]
    return value if isinstance(value, str) else ""


def _header_value(login_response: RouteEntry, name: str) -> str:
    """Return the captured login's value for response header ``name``; empty if absent."""
    wanted = name.lower()
    return next((value for key, value in login_response.headers if key.lower() == wanted), "")


def _captured_login_response(
    har_entries: list[dict[str, Any]] | None,
    login_path: str,
    method: str = "POST",
) -> RouteEntry | None:
    """Return the captured response to the login request, if the capture has one."""
    if not har_entries:
        return None
    return build_routes(har_entries, login_path=login_path).get((method, normalize_path(login_path)))


def create_handler(
    modem_config: ModemConfig,
    har_entries: list[dict[str, Any]] | None = None,
) -> BearerAuthHandler:
    """Entry point for dynamic auth handler dispatch."""
    from ...models.modem_config.auth import BearerAuth

    auth = modem_config.auth
    assert isinstance(auth, BearerAuth)
    handler = BearerAuthHandler(
        login_path=auth.login_endpoint,
        token_path=auth.token_path,
        captured_login=_captured_login_response(har_entries, auth.login_endpoint, auth.method),
        method=auth.method,
        token_source=auth.token_source,
        token_header=auth.token_header,
        token_placement=auth.token_placement,
        token_prefix=auth.token_prefix,
    )
    handler.login_action = auth.login_endpoint
    handler.token_prefix = auth.token_prefix
    return handler
