"""Tests for the JSON-RPC 2.0 envelope primitives.

Table-driven: reply classification (result, error, not an envelope)
and call construction. See AUTH_JSONRPC_SPEC.md § Envelope.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from solentlabs.cable_modem_monitor_core.protocol.jsonrpc import (
    build_call,
    call_url,
    parse_reply,
)


def _response(body: Any = None, *, text: str | None = None) -> MagicMock:
    resp = MagicMock()
    if text is not None:
        resp.json.side_effect = ValueError("not json")
    else:
        resp.json.return_value = body
    return resp


# =============================================================================
# parse_reply
# =============================================================================
#
# ┌──────────────────────────────────────────────┬──────────┬──────────────┬──────────────────┐
# │ body                                         │ envelope │ result       │ error code       │
# ├──────────────────────────────────────────────┼──────────┼──────────────┼──────────────────┤
# │ result object                                │ yes      │ {"a": 1}     │ None             │
# │ result empty list (reboot answer)            │ yes      │ []           │ None             │
# │ result null                                  │ yes      │ None         │ None             │
# │ error with string code (SDMC)                │ yes      │ None         │ "msgBadLogin"    │
# │ error with integer code (JSON-RPC spec)      │ yes      │ None         │ "-32601"         │
# │ error that is not an object                  │ no       │ ---          │ ---              │
# │ neither result nor error                     │ no       │ ---          │ ---              │
# │ JSON array                                   │ no       │ ---          │ ---              │
# │ not JSON                                     │ no       │ ---          │ ---              │
# └──────────────────────────────────────────────┴──────────┴──────────────┴──────────────────┘
#
def _ok(value: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "result": value, "id": 1}


def _err(code: object) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "error": {"code": code, "message": ""}, "id": 1}


# fmt: off
REPLY_CASES = [
    # (body,                             is_envelope, result,    error_code,    id)
    (_ok({"a": 1}),                      True,        {"a": 1},  None,          "result-object"),
    (_ok([]),                            True,        [],        None,          "result-empty-list"),
    (_ok(None),                          True,        None,      None,          "result-null"),
    (_err("msgBadLogin"),                True,        None,      "msgBadLogin", "error-string-code"),
    (_err(-32601),                       True,        None,      "-32601",      "error-int-code"),
    ({"jsonrpc": "2.0", "error": "boom"}, False,      None,      None,          "error-not-object"),
    ({"jsonrpc": "2.0", "id": 1},        False,       None,      None,          "no-result-no-error"),
    ([{"result": 1}],                    False,       None,      None,          "json-array"),
]
# fmt: on


@pytest.mark.parametrize(
    "body,is_envelope,result,error_code",
    [c[:4] for c in REPLY_CASES],
    ids=[c[4] for c in REPLY_CASES],
)
def test_parse_reply(body: Any, is_envelope: bool, result: Any, error_code: str | None) -> None:
    """A reply is classified by the envelope members JSON-RPC 2.0 defines."""
    reply = parse_reply(_response(body))
    if not is_envelope:
        assert reply is None
        return
    assert reply is not None
    assert reply.result == result
    assert reply.error_code == error_code


def test_parse_reply_not_json() -> None:
    """A body that does not parse is not an envelope."""
    assert parse_reply(_response(text="<html>")) is None


def test_error_code_matches_configured_value_as_string() -> None:
    """Codes compare as strings, so an integer code matches its YAML spelling."""
    reply = parse_reply(_response(_err(401)))
    assert reply is not None
    assert reply.is_error
    assert reply.error_code == "401"


# =============================================================================
# build_call / call_url
# =============================================================================


def test_build_call_shape() -> None:
    """A call carries exactly the four JSON-RPC 2.0 request members."""
    call = build_call("CM.getDownstream", [])
    assert set(call) == {"jsonrpc", "method", "params", "id"}
    assert call["jsonrpc"] == "2.0"
    assert call["method"] == "CM.getDownstream"
    assert call["params"] == []
    assert isinstance(call["id"], int)


def test_build_call_ids_increase() -> None:
    """Each call gets a fresh id."""
    first = build_call("A", [])["id"]
    second = build_call("A", [])["id"]
    assert second > first


# fmt: off
URL_CASES = [
    # (token_prefix, token,   expected,                                        id)
    ("token=",       "abc",   "http://m/cgi-bin/router.php?token=abc",         "with-token"),
    ("token=",       "",      "http://m/cgi-bin/router.php",                   "no-token-yet"),
    ("",             "",      "http://m/cgi-bin/router.php",                   "no-prefix"),
]
# fmt: on


@pytest.mark.parametrize("prefix,token,expected", [c[:3] for c in URL_CASES], ids=[c[3] for c in URL_CASES])
def test_call_url(prefix: str, token: str, expected: str) -> None:
    """The token rides in the query only once a login has produced one."""
    assert call_url("http://m", "/cgi-bin/router.php", prefix, token) == expected
