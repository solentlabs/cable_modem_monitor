"""Tests for the jsonrpc auth strategy.

Covers the login call on the wire, token extraction, and the reply
classification in AUTH_JSONRPC_SPEC.md § Auth Flow and § Error Codes:
lockout, rejected credential, missing token, non-2xx, and a body that
is not an envelope. Token placement and session
validity are in test_manager_hooks.py with every other strategy's.

TEST DATA TABLES
================
Tables sit above the test that consumes them, with ASCII
box-drawing comments for readability.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.base import LoginLockoutError
from solentlabs.cable_modem_monitor_core.auth.jsonrpc import JsonrpcAuthManager
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import JsonrpcAuth


def _config(**fields: Any) -> JsonrpcAuth:
    return JsonrpcAuth.model_validate(
        {
            "strategy": "jsonrpc",
            "endpoint": "/cgi-bin/router.php",
            "login_method": "MGMT.login",
            "username_field": "loginUserName",
            "password_field": "loginPwd",
            "token_path": "token",
            "token_param": "token",
            **fields,
        }
    )


def _response(status_code: int = 200, body: Any = None, *, not_json: bool = False) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    if not_json:
        resp.json.side_effect = ValueError("not json")
    else:
        resp.json.return_value = body
    return resp


def _session(response: MagicMock) -> MagicMock:
    session = MagicMock(spec=requests.Session)
    session.post.return_value = response
    return session


def _login(config: JsonrpcAuth, response: MagicMock) -> tuple[Any, MagicMock]:
    session = _session(response)
    result = JsonrpcAuthManager(config).authenticate(session, "http://192.168.0.1", "admin", "pw")
    return result, session


_OK = {"jsonrpc": "2.0", "result": {"username": "admin", "token": "tok123", "level": "user"}, "id": 1}


def _error(code: object) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "error": {"code": code, "message": ""}, "id": 1}


# =============================================================================
# Wire shape
# =============================================================================


class TestLoginCall:
    """The login is one JSON-RPC call to the endpoint, credentials in params[0]."""

    def test_posts_envelope_to_endpoint_without_token(self) -> None:
        _, session = _login(_config(), _response(body=_OK))
        url = session.post.call_args.args[0]
        body = session.post.call_args.kwargs["json"]
        assert url == "http://192.168.0.1/cgi-bin/router.php"
        assert body["jsonrpc"] == "2.0"
        assert body["method"] == "MGMT.login"
        assert body["params"] == [{"loginUserName": "admin", "loginPwd": "pw"}]
        assert isinstance(body["id"], int)

    def test_success_populates_context(self) -> None:
        result, _ = _login(_config(), _response(body=_OK))
        assert result.success
        assert result.auth_context.token == "tok123"
        assert result.auth_context.url_token == "tok123"
        # The login reply is not a data page, so it is never offered for reuse.
        assert result.response is None

    def test_nested_token_path(self) -> None:
        body = {"jsonrpc": "2.0", "result": {"session": {"key": "deep"}}, "id": 1}
        result, _ = _login(_config(token_path="session.key"), _response(body=body))
        assert result.success
        assert result.auth_context.token == "deep"

    def test_connection_error_propagates(self) -> None:
        session = MagicMock(spec=requests.Session)
        session.post.side_effect = requests.ConnectionError("down")
        with pytest.raises(requests.ConnectionError):
            JsonrpcAuthManager(_config()).authenticate(session, "http://192.168.0.1", "admin", "pw")


# =============================================================================
# Reply classification
# =============================================================================
#
# ┌──────────────────────────────┬──────────────────────────┬─────────┬──────────────────────┐
# │ reply                        │ lockout_code configured  │ outcome │ error mentions       │
# ├──────────────────────────────┼──────────────────────────┼─────────┼──────────────────────┤
# │ msgBadLoginText              │ yes                      │ failed  │ msgBadLoginText      │
# │ msgBadLoginText              │ no                       │ failed  │ msgBadLoginText      │
# │ msgUserLockedText            │ no                       │ failed  │ msgUserLockedText    │
# │ integer code                 │ no                       │ failed  │ -32000               │
# │ result without token         │ ---                      │ failed  │ token_path           │
# │ token is not a string        │ ---                      │ failed  │ token_path           │
# │ result is not an object      │ ---                      │ failed  │ token_path           │
# │ not JSON                     │ ---                      │ failed  │ JSON-RPC             │
# │ JSON without result or error │ ---                      │ failed  │ JSON-RPC             │
# │ HTTP 500                     │ ---                      │ failed  │ HTTP 500             │
# │ HTTP 404                     │ ---                      │ failed  │ HTTP 404             │
# └──────────────────────────────┴──────────────────────────┴─────────┴──────────────────────┘
#
_LOCKOUT = {"lockout_code": "msgUserLockedText"}

_NO_TOKEN = {"jsonrpc": "2.0", "result": {"a": 1}}
_TOKEN_NOT_STR = {"jsonrpc": "2.0", "result": {"token": 7}}
_RESULT_LIST = {"jsonrpc": "2.0", "result": []}
_NO_ENVELOPE = {"jsonrpc": "2.0", "id": 1}

# fmt: off
FAILURE_CASES = [
    # (config fields, status, body,                        not_json, fragment,            id)
    (_LOCKOUT,        200,    _error("msgBadLoginText"),   False,    "msgBadLoginText",   "bad-login-with-lockout"),
    ({},              200,    _error("msgBadLoginText"),   False,    "msgBadLoginText",   "bad-login"),
    ({},              200,    _error("msgUserLockedText"), False,    "msgUserLockedText", "lock-code-undeclared"),
    ({},              200,    _error(-32000),              False,    "-32000",            "integer-code"),
    ({},              200,    _NO_TOKEN,                   False,    "token_path",        "no-token"),
    ({},              200,    _TOKEN_NOT_STR,              False,    "token_path",        "token-not-string"),
    ({},              200,    _RESULT_LIST,                False,    "token_path",        "result-not-object"),
    ({},              200,    None,                        True,     "JSON-RPC",          "not-json"),
    ({},              200,    _NO_ENVELOPE,                False,    "JSON-RPC",          "no-envelope"),
    ({},              500,    None,                        True,     "HTTP 500",          "http-500"),
    ({},              404,    None,                        True,     "HTTP 404",          "http-404"),
]
# fmt: on


@pytest.mark.parametrize(
    "fields,status,body,not_json,fragment",
    [c[:5] for c in FAILURE_CASES],
    ids=[c[5] for c in FAILURE_CASES],
)
def test_failed_login(fields: dict[str, str], status: int, body: Any, not_json: bool, fragment: str) -> None:
    """Every non-token reply is a failed login that names why, with the response attached."""
    result, _ = _login(_config(**fields), _response(status, body, not_json=not_json))
    assert not result.success
    assert not result.busy
    assert fragment in result.error
    assert result.response is not None


def test_declared_lockout_code_raises() -> None:
    """The entry's lockout code is the firmware protecting itself, not a verdict on the credential."""
    with pytest.raises(LoginLockoutError, match="msgUserLockedText"):
        _login(_config(**_LOCKOUT), _response(body=_error("msgUserLockedText")))
