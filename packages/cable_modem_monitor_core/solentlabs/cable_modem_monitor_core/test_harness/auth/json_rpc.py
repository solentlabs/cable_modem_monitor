"""JSON-RPC 2.0 mock handler: every call answered by its body ``method``.

The route table keys on path, and every JSON-RPC call shares one path,
so this handler takes all of them. The login is answered with the
capture's successful login reply, whose token every later call must
carry in the query. Data and action calls are answered from a
``method → reply`` lookup built from the capture.

Honesty rules, the #82 rule at this transport's layer: a login whose
credential keys the capture never sent fails, and a method the capture
never called answers 404 rather than another method's reply.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

from ...auth.response import extract_token
from ..routes import RouteEntry, normalize_path
from .base import AuthHandler

if TYPE_CHECKING:
    from ...models.modem_config import ModemConfig

_logger = logging.getLogger(__name__)


class JsonRpcAuthHandler(AuthHandler):
    """Answers JSON-RPC calls from the capture, dispatching on ``method``."""

    def __init__(
        self,
        endpoint: str,
        login_method: str,
        credential_keys: frozenset[str],
        token_path: str,
        token_param: str,
        restart_method: str,
        har_entries: list[dict[str, Any]],
    ) -> None:
        super().__init__()
        self._endpoint = normalize_path(endpoint)
        self._login_method = login_method
        self._credential_keys = credential_keys
        self._token_param = token_param
        self._restart_method = restart_method
        self._replies = _build_replies(har_entries, self._endpoint)
        login = self._replies.get(login_method)
        self._token = _reply_token(login, token_path) if login else ""
        self._authenticated = False

    def is_login_request(self, method: str, path: str) -> bool:
        """Every call is a POST to the one endpoint; all route here for body dispatch."""
        return method == "POST" and normalize_path(path) == self._endpoint

    def handle_login(self, method: str, path: str, body: bytes, headers: dict[str, str]) -> RouteEntry | None:
        """Answer the login and the restart; data calls fall through to the auth check."""
        call = _parse_call(body)
        if call is None:
            return RouteEntry(status=400, headers=[], body="not a JSON-RPC call")
        name = call.get("method")
        if name == self._login_method:
            return self._handle_login_call(call)
        if name and name == self._restart_method:
            return self._handle_restart_call()
        return None

    def _handle_login_call(self, call: dict[str, Any]) -> RouteEntry:
        params = call.get("params")
        sent = frozenset(params[0]) if isinstance(params, list) and params and isinstance(params[0], dict) else None
        if sent != self._credential_keys:
            return RouteEntry(
                status=500,
                headers=[("Content-Type", "text/plain")],
                body=f"login credential keys not in the capture: sent {sorted(sent or [])}, "
                f"captured {sorted(self._credential_keys)}",
            )
        reply = self._replies.get(self._login_method)
        if reply is None:
            return RouteEntry(status=404, headers=[], body="no successful login in the capture")
        self._authenticated = True
        _logger.debug("Mock server: JSON-RPC login accepted")
        return reply

    def _handle_restart_call(self) -> RouteEntry:
        # Recorded here: the restart shares the endpoint with every other
        # call, so the server's path matching never sees it as an action.
        # A restart the capture never made is refused, not synthesized: a
        # synthesized answer would let an unevidenced action pass replay.
        reply = self._replies.get(self._restart_method) or RouteEntry(
            status=404, headers=[], body=f"restart method not in the capture: {self._restart_method}"
        )
        self.record_action("restart", reply.status)
        self._authenticated = False
        return reply

    def is_authenticated(self, headers: dict[str, str], *, query: str = "") -> bool:
        """Logged in, and the call carries the issued token in the query."""
        sent = parse_qs(query).get(self._token_param, [""])[0]
        return self._authenticated and bool(self._token) and sent == self._token

    def get_route_override(self, method: str, path: str, body: bytes, headers: dict[str, str]) -> RouteEntry | None:
        """Serve a data call by ``method``; never fall through to the path-keyed route table."""
        if method != "POST" or normalize_path(path) != self._endpoint:
            return None
        call = _parse_call(body)
        name = call.get("method") if call else None
        reply = self._replies.get(name) if isinstance(name, str) else None
        if reply is None:
            return RouteEntry(status=404, headers=[], body=f"method not in the capture: {name}")
        return reply


def _parse_call(body: bytes) -> dict[str, Any] | None:
    """The request body as a JSON object, or None."""
    try:
        call = json.loads(body or b"null")
    except ValueError:
        return None
    return call if isinstance(call, dict) else None


def _reply_token(reply: RouteEntry, token_path: str) -> str:
    """The token the captured login reply issued."""
    try:
        parsed = json.loads(reply.body)
    except ValueError:
        return ""
    result = parsed.get("result") if isinstance(parsed, dict) else None
    return extract_token(result, token_path) or ""


def _build_replies(har_entries: list[dict[str, Any]], endpoint: str) -> dict[str, RouteEntry]:
    """Build ``method → reply`` from the capture's calls to ``endpoint``.

    A reply carrying ``result`` beats one carrying ``error``, and among
    equals the later exchange wins: the capture steps ask for a
    deliberate wrong-password login before the real one.
    """
    replies: dict[str, RouteEntry] = {}
    successful: set[str] = set()
    for entry in har_entries:
        request = entry.get("request", {})
        if request.get("method", "").upper() != "POST":
            continue
        if normalize_path(urlparse(request.get("url", "")).path) != endpoint:
            continue
        call = _parse_call(str(request.get("postData", {}).get("text", "")).encode())
        name = call.get("method") if call else None
        if not isinstance(name, str):
            continue

        response = entry.get("response", {})
        text = str(response.get("content", {}).get("text", ""))
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = None
        ok = isinstance(parsed, dict) and "result" in parsed
        if name in successful and not ok:
            continue
        headers = [
            (h.get("name", ""), h.get("value", ""))
            for h in response.get("headers", [])
            if h.get("name") and h.get("name", "").lower() not in ("content-length", "set-cookie")
        ]
        replies[name] = RouteEntry(status=response.get("status", 0), headers=headers, body=text)
        if ok:
            successful.add(name)
    _logger.debug("JSON-RPC mock: %d captured methods: %s", len(replies), sorted(replies))
    return replies


def create_handler(
    modem_config: ModemConfig,
    har_entries: list[dict[str, Any]] | None = None,
) -> JsonRpcAuthHandler:
    """Entry point for dynamic auth handler dispatch."""
    from ...models.modem_config.actions import JsonRpcAction
    from ...models.modem_config.auth import JsonRpcAuth

    auth = modem_config.auth
    assert isinstance(auth, JsonRpcAuth)

    restart_method = ""
    if modem_config.actions and isinstance(modem_config.actions.restart, JsonRpcAction):
        restart_method = modem_config.actions.restart.method

    entries = har_entries or []
    return JsonRpcAuthHandler(
        endpoint=auth.endpoint,
        login_method=auth.login_method,
        credential_keys=_captured_credential_keys(entries, auth.endpoint, auth.login_method),
        token_path=auth.token_path,
        token_param=auth.token_param,
        restart_method=restart_method,
        har_entries=entries,
    )


def _captured_credential_keys(har_entries: list[dict[str, Any]], endpoint: str, login_method: str) -> frozenset[str]:
    """Keys of the credential object the capture's login calls sent."""
    path = normalize_path(endpoint)
    for entry in har_entries:
        request = entry.get("request", {})
        if normalize_path(urlparse(request.get("url", "")).path) != path:
            continue
        call = _parse_call(str(request.get("postData", {}).get("text", "")).encode())
        if not call or call.get("method") != login_method:
            continue
        params = call.get("params")
        if isinstance(params, list) and params and isinstance(params[0], dict):
            return frozenset(params[0])
    return frozenset()
