"""Tests for JSON-RPC call analysis: calls as JSON pages, and restart candidates.

Table-driven: each case is a sequence of calls (method, answer, sending
page) and the pages or restart candidates analysis must produce.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.actions.jsonrpc import restart_ambiguity
from solentlabs.cable_modem_monitor_catalog_tools.analysis.format.jsonrpc import jsonrpc_pages

_ENDPOINT = "https://192.168.0.1/cgi-bin/router.php"
_LOGIN_PARAMS = [{"loginUserName": "u", "loginPwd": "p"}]


def _call(method: str, answer: dict[str, Any], referer: str | None = None, params: Any = None) -> dict[str, Any]:
    """A HAR entry for one JSON-RPC call and its answer."""
    headers = [{"name": "Referer", "value": f"https://192.168.0.1{referer}"}] if referer else []
    body = {"jsonrpc": "2.0", "method": method, "params": params if params is not None else [], "id": 1}
    return {
        "request": {"method": "POST", "url": _ENDPOINT, "headers": headers, "postData": {"text": json.dumps(body)}},
        "response": {"status": 200, "content": {"text": json.dumps({"jsonrpc": "2.0", "id": 1, **answer})}},
    }


_ERROR: dict[str, Any] = {"error": {"code": "msgFail"}}
_OK: dict[str, Any] = {"result": []}
_OBJ_1: dict[str, Any] = {"result": {"x": 1}}
_LOGIN = _call("MGMT.login", {"result": {"token": "t"}}, "/login.htm", params=_LOGIN_PARAMS)

# =============================================================================
# jsonrpc_pages test data
# =============================================================================
#
# ┌──────────────────────────────────────────┬─────────────────────────────────┬─────────────────────┐
# │ calls                                    │ pages (resource: json_data)     │ description         │
# ├──────────────────────────────────────────┼─────────────────────────────────┼─────────────────────┤
# │ A → {x: 1}                               │ A: {x: 1}                       │ object result       │
# │ A → [1]                                  │ A: {_raw: [1]}                  │ non-object wrapped  │
# │ A → error                                │ none                            │ error is not data   │
# │ A → error, A → {x: 1}                    │ A: {x: 1}                       │ error is skipped    │
# │ A → {x: 1}, A → {x: 2}                   │ A: {x: 2}                       │ later result wins   │
# │ A → {x: 1}, A → error                    │ A: {x: 1}                       │ result beats error  │
# │ login → {token}                          │ none                            │ login is not data   │
# └──────────────────────────────────────────┴─────────────────────────────────┴─────────────────────┘
#
# fmt: off
PAGES_CASES: list[tuple[list[dict[str, Any]], dict[str, Any], str]] = [
    # (calls,                                                   pages,                 id)
    ([_call("A", _OBJ_1)],                                      {"A": {"x": 1}},       "object-result"),
    ([_call("A", {"result": [1]})],                             {"A": {"_raw": [1]}},  "non-object-wrapped"),
    ([_call("A", _ERROR)],                                      {},                    "error-is-not-data"),
    ([_call("A", _ERROR), _call("A", _OBJ_1)],                  {"A": {"x": 1}},       "error-is-skipped"),
    ([_call("A", _OBJ_1), _call("A", {"result": {"x": 2}})],    {"A": {"x": 2}},       "later-result-wins"),
    ([_call("A", _OBJ_1), _call("A", _ERROR)],                  {"A": {"x": 1}},       "result-beats-error"),
    ([_LOGIN],                                                  {},                    "login-is-not-data"),
]
# fmt: on


@pytest.mark.parametrize("calls,pages", [c[:2] for c in PAGES_CASES], ids=[c[2] for c in PAGES_CASES])
def test_jsonrpc_pages(calls: list[dict[str, Any]], pages: dict[str, Any]) -> None:
    """Each answered non-login method becomes one JSON page keyed by the method name."""
    assert {page.resource: page.json_data for page in jsonrpc_pages(calls)} == pages


# =============================================================================
# restart_ambiguity test data
# =============================================================================
#
# ┌───────────────────────────────────────┬────────────────┬─────────────────────────────┬───────────────────────┐
# │ calls (method @ sending page)         │ data sources   │ candidates (value: sources) │ description           │
# ├───────────────────────────────────────┼────────────────┼─────────────────────────────┼───────────────────────┤
# │ R @ /reboot.htm                       │ none           │ R: /reboot.htm              │ cites sending page    │
# │ R, no Referer                         │ none           │ R: endpoint path            │ endpoint fallback     │
# │ R @ /a.htm, R @ /b.htm, R @ /a.htm    │ none           │ R: /a.htm, /b.htm           │ one per page          │
# │ D @ /s.htm, S @ /s.htm                │ D down, S info │ none                        │ data sources excluded │
# │ login @ /login.htm                    │ none           │ none                        │ login excluded        │
# │ R → error @ /reboot.htm               │ none           │ R: /reboot.htm              │ answer irrelevant     │
# └───────────────────────────────────────┴────────────────┴─────────────────────────────┴───────────────────────┘
#
_SECTIONS = {"downstream": {"resource": "D"}, "system_info": {"sources": [{"resource": "S"}]}}
_R_A = _call("R", _OK, "/a.htm")
_R_B = _call("R", _OK, "/b.htm")
_DATA = [_call("D", _OK, "/s.htm"), _call("S", _OK, "/s.htm")]

# fmt: off
RESTART_CASES: list[tuple[list[dict[str, Any]], dict[str, Any], dict[str, list[str]], str]] = [
    # (calls,                                sections,  candidates,                       id)
    ([_call("R", _OK, "/reboot.htm")],       {},        {"R": ["/reboot.htm"]},           "cites-sending-page"),
    ([_call("R", _OK)],                      {},        {"R": ["/cgi-bin/router.php"]},   "falls-back-to-endpoint"),
    ([_R_A, _R_B, _R_A],                     {},        {"R": ["/a.htm", "/b.htm"]},      "one-evidence-per-page"),
    (_DATA,                                  _SECTIONS, {},                               "data-sources-excluded"),
    ([_LOGIN],                               {},        {},                               "login-excluded"),
    ([_call("R", _ERROR, "/reboot.htm")],    {},        {"R": ["/reboot.htm"]},           "answer-irrelevant"),
]
# fmt: on


@pytest.mark.parametrize(
    "calls,sections,candidates",
    [c[:3] for c in RESTART_CASES],
    ids=[c[3] for c in RESTART_CASES],
)
def test_restart_ambiguity(
    calls: list[dict[str, Any]],
    sections: dict[str, Any],
    candidates: dict[str, list[str]],
) -> None:
    """Every call that is neither the login nor a data source is an unresolved, non-blocking candidate."""
    ambiguity = restart_ambiguity(calls, sections)
    assert (ambiguity.field, ambiguity.blocking, ambiguity.resolution) == ("actions.restart.method", False, None)
    assert {c.value: [e.source for e in c.evidence] for c in ambiguity.candidates} == candidates


def test_restart_evidence_snippet_is_the_call() -> None:
    """The snippet is the request body, so the reviewer sees the params the call sent."""
    call = _call("R", _OK, "/reboot.htm")
    [candidate] = restart_ambiguity([call], {}).candidates
    assert candidate.evidence[0].snippet == call["request"]["postData"]["text"]
