"""JSON-RPC 2.0 envelope primitives shared by ``jsonrpc`` auth, loader, and actions.

JSON-RPC fixes only the envelope: a call carries ``jsonrpc``,
``method``, ``params`` and ``id``; a reply carries exactly one of
``result`` or ``error``. Everything inside is vendor vocabulary and
comes from entry config. See AUTH_JSONRPC_SPEC.md § Envelope.

Also owns typed access to the ``jsonrpc`` auth block
(``jsonrpc_params``) for the generic collector and action dispatcher.
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any, NamedTuple

import requests

from ..models.modem_config.auth import JsonrpcAuth

if TYPE_CHECKING:
    from ..models.modem_config.auth import AuthConfig

# The server echoes the id and gives it no meaning (the firmware's own
# client sends a random one), so a process-wide counter is enough.
_CALL_IDS = itertools.count(1)


class JsonRpcReply(NamedTuple):
    """A reply that is a JSON-RPC envelope: its ``result``, or its error code."""

    result: Any = None
    # String form of error.code; None when the reply carries a result.
    error_code: str | None = None

    @property
    def is_error(self) -> bool:
        """Whether the reply carries ``error`` rather than ``result``."""
        return self.error_code is not None


def jsonrpc_params(auth: AuthConfig | None) -> JsonrpcAuth:
    """The ``jsonrpc`` auth block; the transport cannot run without one."""
    # jsonrpc has exactly one strategy and every field names a firmware
    # value, so unlike cbn there are no defaults to fall back to.
    if not isinstance(auth, JsonrpcAuth):
        raise ValueError("transport 'jsonrpc' requires an auth block with strategy 'jsonrpc'")
    return auth


def build_call(method: str, params: list[Any]) -> dict[str, Any]:
    """Build one JSON-RPC 2.0 request body."""
    return {"jsonrpc": "2.0", "method": method, "params": params, "id": next(_CALL_IDS)}


def call_url(base_url: str, endpoint: str, token_prefix: str, token: str) -> str:
    """The endpoint URL, with the session token in the query once a login produced one."""
    url = f"{base_url}{endpoint}"
    if token_prefix and token:
        url = f"{url}?{token_prefix}{token}"
    return url


def post_call(
    session: requests.Session,
    url: str,
    method: str,
    params: list[Any],
    *,
    timeout: int,
) -> requests.Response:
    """POST one call; transport errors propagate to the caller."""
    return session.post(url, json=build_call(method, params), timeout=timeout)


def parse_reply(response: requests.Response) -> JsonRpcReply | None:
    """Read a reply's envelope, or ``None`` when the body is not one."""
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    error = body.get("error")
    if error is not None:
        if not isinstance(error, dict):
            return None
        return JsonRpcReply(error_code=str(error.get("code")))
    if "result" not in body:
        return None
    return JsonRpcReply(result=body["result"])
