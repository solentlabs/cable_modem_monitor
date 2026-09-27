"""Tests for JSONRPCLoader.

Table-driven over RESOURCE_LOADING_SPEC.md § JSON-RPC Loading: the
call on the wire, envelope stripping, and error classification.
Mock HTTP session for all tests.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
import requests
from solentlabs.cable_modem_monitor_core.fetch_list import ResourceTarget
from solentlabs.cable_modem_monitor_core.loaders.http import ResourceLoadError, SessionExpiredError
from solentlabs.cable_modem_monitor_core.loaders.jsonrpc import JSONRPCLoader

_EXPIRED = "msgLoginExpiredText"


def _response(status_code: int = 200, body: Any = None, *, not_json: bool = False) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 400
    resp.content = b"{}"
    resp.text = "{}"
    resp.headers = {"Content-Type": "application/json"}
    resp.request = None
    if not_json:
        resp.json.side_effect = ValueError("not json")
    else:
        resp.json.return_value = body
    return resp


def _result(value: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "result": value, "id": 1}


def _error(code: object) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "error": {"code": code, "message": ""}, "id": 1}


def _loader(session: MagicMock, *, expired_code: str = _EXPIRED, token: str = "tok") -> JSONRPCLoader:
    return JSONRPCLoader(
        session=session,
        base_url="http://192.168.0.1",
        endpoint="/cgi-bin/router.php",
        token_prefix="token=",
        url_token=token,
        session_expired_code=expired_code,
        timeout=7,
        model="T950",
    )


def _session(*responses: MagicMock) -> MagicMock:
    session = MagicMock(spec=requests.Session)
    session.post.side_effect = list(responses)
    return session


def _targets(*methods: str) -> list[ResourceTarget]:
    return [ResourceTarget(path=m, format="json") for m in methods]


# =============================================================================
# The call on the wire
# =============================================================================


class TestCall:
    """Each resource is one call to the endpoint, token in the query."""

    def test_posts_method_with_token(self) -> None:
        session = _session(_response(body=_result({"dss": []})))
        _loader(session).fetch(_targets("CM.getDownstream"))
        url = session.post.call_args.args[0]
        body = session.post.call_args.kwargs["json"]
        assert url == "http://192.168.0.1/cgi-bin/router.php?token=tok"
        assert body["method"] == "CM.getDownstream"
        assert body["params"] == []
        assert session.post.call_args.kwargs["timeout"] == 7

    def test_calls_are_sequential_in_target_order(self) -> None:
        session = _session(_response(body=_result({"a": 1})), _response(body=_result({"b": 2})))
        _loader(session).fetch(_targets("A.one", "B.two"))
        methods = [c.kwargs["json"]["method"] for c in session.post.call_args_list]
        assert methods == ["A.one", "B.two"]

    def test_records_fetch_timing(self) -> None:
        loader = _loader(_session(_response(body=_result({"a": 1}))))
        loader.fetch(_targets("A.one"))
        assert [f[0] for f in loader.resource_fetches] == ["A.one"]


# =============================================================================
# Envelope stripping
# =============================================================================
#
# ┌──────────────────────┬───────────────────────────┐
# │ result               │ resource dict value       │
# ├──────────────────────┼───────────────────────────┤
# │ object               │ the object                │
# │ list                 │ {"_raw": list}            │
# │ string               │ {"_raw": string}          │
# └──────────────────────┴───────────────────────────┘
#
# fmt: off
RESULT_CASES = [
    # (result,               expected,                  id)
    ({"dss": [{"ch": "1"}]}, {"dss": [{"ch": "1"}]},    "object"),
    ([{"mac": "x"}],         {"_raw": [{"mac": "x"}]},  "list"),
    ("Online",               {"_raw": "Online"},        "string"),
]
# fmt: on


@pytest.mark.parametrize("result,expected", [c[:2] for c in RESULT_CASES], ids=[c[2] for c in RESULT_CASES])
def test_result_is_the_resource(result: Any, expected: dict[str, Any]) -> None:
    """The parser receives result with the envelope stripped, keyed by method."""
    resources = _loader(_session(_response(body=_result(result)))).fetch(_targets("CM.x"))
    assert resources == {"CM.x": expected}


# =============================================================================
# Error classification
# =============================================================================
#
# ┌───────────────────────────────────┬────────────────────────────┬─────────────────────┐
# │ reply                             │ expired code configured    │ outcome             │
# ├───────────────────────────────────┼────────────────────────────┼─────────────────────┤
# │ error, the expired code           │ yes                        │ omitted, logged     │
# │ error, the expired code           │ no                         │ omitted, logged     │
# │ error, another code               │ yes                        │ omitted, logged     │
# │ not JSON                          │ ---                        │ omitted, logged     │
# │ neither result nor error          │ ---                        │ omitted, logged     │
# └───────────────────────────────────┴────────────────────────────┴─────────────────────┘
# (the first row raises instead; see test_expired_code_is_a_stale_session)
#
# fmt: off
OMIT_CASES = [
    # (expired_code, body,                       not_json, reason_fragment,      id)
    ("",             _error(_EXPIRED),            False,    _EXPIRED,             "expired-undeclared"),
    (_EXPIRED,       _error("msgGetFailedText"),  False,    "msgGetFailedText",   "other-code"),
    (_EXPIRED,       None,                        True,     "JSON-RPC",           "not-json"),
    (_EXPIRED,       {"jsonrpc": "2.0", "id": 1}, False,    "JSON-RPC",           "no-envelope"),
]
# fmt: on


@pytest.mark.parametrize(
    "expired_code,body,not_json,fragment",
    [c[:4] for c in OMIT_CASES],
    ids=[c[4] for c in OMIT_CASES],
)
def test_unserved_call_is_omitted_and_logged(expired_code: str, body: Any, not_json: bool, fragment: str) -> None:
    """A call that answered without data drops out of the dict and names why."""
    session = _session(_response(body=body, not_json=not_json), _response(body=_result({"ok": 1})))
    loader = _loader(session, expired_code=expired_code)
    resources = loader.fetch(_targets("CM.bad", "CM.good"))
    assert resources == {"CM.good": {"ok": 1}}
    assert len(loader.decode_errors) == 1
    method, fmt, reason = loader.decode_errors[0]
    assert (method, fmt) == ("CM.bad", "json")
    assert fragment in reason


def test_expired_code_is_a_stale_session() -> None:
    """The declared expiry code ends the load as a stale session."""
    session = _session(_response(body=_error(_EXPIRED)))
    with pytest.raises(SessionExpiredError) as info:
        _loader(session).fetch(_targets("CM.getDownstream"))
    assert info.value.path == "CM.getDownstream"
    assert info.value.code == _EXPIRED


# fmt: off
STATUS_CASES = [
    # (status, id)
    (304,      "not-modified"),
    (401,      "unauthorized"),
    (500,      "server-error"),
]
# fmt: on


@pytest.mark.parametrize("status", [c[0] for c in STATUS_CASES], ids=[c[1] for c in STATUS_CASES])
def test_non_2xx_raises_with_status(status: int) -> None:
    """The collector reads the status, as for every other transport."""
    with pytest.raises(ResourceLoadError) as info:
        _loader(_session(_response(status, not_json=True))).fetch(_targets("CM.x"))
    assert info.value.status_code == status
    assert info.value.path == "CM.x"


@pytest.mark.parametrize("exc", [requests.ConnectionError("down"), requests.Timeout("slow")], ids=["conn", "timeout"])
def test_transport_failure_propagates(exc: Exception) -> None:
    """An unreachable modem is CONNECTIVITY, never a short resource dict."""
    session = MagicMock(spec=requests.Session)
    session.post.side_effect = exc
    with pytest.raises(type(exc)):
        _loader(session).fetch(_targets("CM.x"))


def test_other_request_error_is_a_load_error() -> None:
    """Anything else requests raises becomes a status-less load error."""
    session = MagicMock(spec=requests.Session)
    session.post.side_effect = requests.exceptions.InvalidURL("bad")
    with pytest.raises(ResourceLoadError) as info:
        _loader(session).fetch(_targets("CM.x"))
    assert info.value.status_code is None


def test_failure_log_masks_the_token() -> None:
    """A 401's request line never carries the session token (RESOURCE_LOADING_SPEC § Error Signals)."""
    resp = _response(401, not_json=True)
    resp.request = requests.Request("POST", "http://192.168.0.1/cgi-bin/router.php?token=tok").prepare()
    with pytest.raises(ResourceLoadError) as info:
        _loader(_session(resp)).fetch(_targets("CM.x"))
    assert "tok" not in info.value.request_line.split(" [")[0].split("?")[1]
    assert "?<set, len=9>" in info.value.request_line
