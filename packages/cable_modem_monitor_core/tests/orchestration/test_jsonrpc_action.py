"""Tests for the JSON-RPC action executor.

Table-driven over ORCHESTRATION_SPEC.md § JSON-RPC Executor: result is
success, error is a refused action, a dropped connection is a reboot.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
import requests
from solentlabs.cable_modem_monitor_core.models.modem_config.actions import JsonrpcAction
from solentlabs.cable_modem_monitor_core.orchestration.actions.jsonrpc_action import execute_jsonrpc_action

_URL = "http://192.168.0.1/cgi-bin/router.php?token=T1"


def _response(status_code: int = 200, body: Any = None, *, not_json: bool = False) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 400
    if not_json:
        resp.json.side_effect = ValueError("not json")
    else:
        resp.json.return_value = body
    return resp


def _run(effect: Any, action: JsonrpcAction | None = None) -> tuple[Any, MagicMock]:
    session = MagicMock(spec=requests.Session)
    if isinstance(effect, Exception):
        session.post.side_effect = effect
    else:
        session.post.return_value = effect
    result = execute_jsonrpc_action(
        session, action or JsonrpcAction(type="jsonrpc", method="MGMT.reboot"), url=_URL, timeout=10, model="T950"
    )
    return result, session


def test_sends_the_call_with_token() -> None:
    """The action is one call to the endpoint, token in the query, declared params."""
    action = JsonrpcAction(type="jsonrpc", method="MGMT.reboot", params=[{"delay": 0}])
    _, session = _run(_response(body={"jsonrpc": "2.0", "result": [], "id": 1}), action)
    assert session.post.call_args.args[0] == _URL
    body = session.post.call_args.kwargs["json"]
    assert (body["method"], body["params"]) == ("MGMT.reboot", [{"delay": 0}])


# ┌──────────────────────────────┬─────────┬──────────────────────┐
# │ reply                        │ success │ message mentions     │
# ├──────────────────────────────┼─────────┼──────────────────────┤
# │ result [] (captured reboot)  │ True    │ MGMT.reboot          │
# │ result null                  │ True    │ MGMT.reboot          │
# │ error code                   │ False   │ msgNotAllowedText    │
# │ not an envelope              │ False   │ JSON-RPC             │
# │ HTTP 500                     │ False   │ 500                  │
# │ HTTP 304                     │ False   │ 304                  │
# │ ConnectionError              │ True    │ connection lost      │
# │ Timeout                      │ True    │ connection lost      │
# │ other request error          │ False   │ failed               │
# └──────────────────────────────┴─────────┴──────────────────────┘
#
_REPLY_EMPTY = _response(body={"jsonrpc": "2.0", "result": [], "id": 1})
_REPLY_NULL = _response(body={"jsonrpc": "2.0", "result": None, "id": 1})
_REPLY_ERROR = _response(body={"jsonrpc": "2.0", "error": {"code": "msgNotAllowedText"}})
_REPLY_NO_ENVELOPE = _response(body={"jsonrpc": "2.0", "id": 1})

# fmt: off
CASES = [
    # (effect,                                 success, fragment,            id)
    (_REPLY_EMPTY,                             True,    "MGMT.reboot",       "result-empty"),
    (_REPLY_NULL,                              True,    "MGMT.reboot",       "result-null"),
    (_REPLY_ERROR,                             False,   "msgNotAllowedText", "error"),
    (_REPLY_NO_ENVELOPE,                       False,   "JSON-RPC",          "no-envelope"),
    (_response(500, not_json=True),            False,   "500",               "http-500"),
    (_response(304, not_json=True),            False,   "304",               "http-304"),
    (requests.ConnectionError("rebooting"),    True,    "connection lost",   "conn-lost"),
    (requests.Timeout("slow"),                 True,    "connection lost",   "timeout"),
    (requests.exceptions.InvalidURL("bad"),    False,   "failed",            "request-error"),
]
# fmt: on


@pytest.mark.parametrize("effect,success,fragment", [c[:3] for c in CASES], ids=[c[3] for c in CASES])
def test_outcome(effect: Any, success: bool, fragment: str) -> None:
    """Success is read from the envelope; a dropped connection is the modem rebooting."""
    result, _ = _run(effect)
    assert result.success is success
    assert fragment in result.message
