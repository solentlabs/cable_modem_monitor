"""Tests for restart_evidence(): does a capture hold the request a declared restart sends.

Table-driven, one table per transport. The cases pin the matching rule,
not any modem: method and path for ``http`` (placeholders as wildcards,
query ignored), the action name for ``hnap``, the ``fun`` code for
``cbn`` and the method name for ``json_rpc``.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.actions.evidence import restart_evidence


def _entry(method: str, url: str, body: str = "", headers: dict[str, str] | None = None) -> dict[str, Any]:
    """One HAR entry carrying just the request fields the matcher reads."""
    request: dict[str, Any] = {
        "method": method,
        "url": url,
        "headers": [{"name": k, "value": v} for k, v in (headers or {}).items()],
    }
    if body:
        request["postData"] = {"text": body}
    return {"request": request}


def _config(action: dict[str, Any] | None) -> dict[str, Any]:
    return {"actions": {"restart": action}} if action else {}


HTTP_CASES = [
    # (declared endpoint, method, har method, har path, expected, id)
    ("/reset.htm", "GET", "GET", "/reset.htm", "captured", "exact-path"),
    ("/reset.htm", "GET", "GET", "/reset.htm?a=1", "captured", "har-query-ignored"),
    ("/reset.htm?a=1", "GET", "GET", "/reset.htm", "captured", "declared-query-ignored"),
    ("/reset.htm", "POST", "GET", "/reset.htm", "not captured", "method-differs"),
    ("/reset.htm", "GET", "GET", "/status.htm", "not captured", "path-differs"),
    ("/reset.htm", "GET", "get", "/reset.htm", "captured", "method-case"),
    ("/api/{auth:uid}/boot", "POST", "POST", "/api/42/boot", "captured", "placeholder-wildcard"),
    ("/api/{auth:uid}/boot", "POST", "POST", "/api//boot", "not captured", "placeholder-needs-a-segment"),
]


@pytest.mark.parametrize(
    ("endpoint", "method", "har_method", "har_path", "expected", "case_id"),
    HTTP_CASES,
    ids=[c[-1] for c in HTTP_CASES],
)
def test_http_restart(endpoint: str, method: str, har_method: str, har_path: str, expected: str, case_id: str) -> None:
    """An http restart is captured when a request has its method and path."""
    config = _config({"type": "http", "method": method, "endpoint": endpoint})
    assert restart_evidence(config, [_entry(har_method, f"http://192.168.100.1{har_path}")]) == expected


HNAP_URL = "http://192.168.100.1/HNAP1/"
HNAP_ACTION = {"type": "hnap", "action_name": "SetReboot"}
SOAP_HEADER = {"SOAPAction": '"http://purenetworks.com/HNAP1/SetReboot"'}
HNAP_CASES = [
    # (har entry, expected, id)
    (_entry("POST", HNAP_URL, json.dumps({"SetReboot": {"Action": "1"}})), "captured", "body-key"),
    (_entry("POST", HNAP_URL, "{}", SOAP_HEADER), "captured", "soap-header"),
    (_entry("POST", HNAP_URL, json.dumps({"GetStatus": {}})), "not captured", "other-action"),
    (_entry("POST", HNAP_URL, "not json"), "not captured", "body-not-json"),
    (_entry("POST", HNAP_URL), "not captured", "no-body"),
]


@pytest.mark.parametrize(("entry", "expected", "case_id"), HNAP_CASES, ids=[c[-1] for c in HNAP_CASES])
def test_hnap_restart(entry: dict[str, Any], expected: str, case_id: str) -> None:
    """An hnap restart is captured when a request names its action."""
    assert restart_evidence(_config(HNAP_ACTION), [entry]) == expected


CBN_URL = "http://192.168.0.1/xml/setter.xml"
CBN_CASES = [
    # (har method, body,                      expected,       id)
    ("POST", "token=abc&fun=133", "captured", "fun-matches"),
    ("POST", "token=abc&fun=8", "not captured", "fun-differs"),
    ("POST", "fun=133&token=abc", "not captured", "token-not-first"),
    ("GET", "token=abc&fun=133", "not captured", "not-a-post"),
    ("POST", "token=abc", "not captured", "no-fun"),
]


@pytest.mark.parametrize(("har_method", "body", "expected", "case_id"), CBN_CASES, ids=[c[-1] for c in CBN_CASES])
def test_cbn_restart(har_method: str, body: str, expected: str, case_id: str) -> None:
    """A cbn restart is captured when a setter call carries its fun code."""
    config = _config({"type": "cbn", "fun": 133})
    assert restart_evidence(config, [_entry(har_method, CBN_URL, body)]) == expected


RPC_URL = "http://192.168.0.1/cgi-bin/router.php"
RPC_CASES = [
    # (body,                                                         expected,       id)
    ({"jsonrpc": "2.0", "method": "SYSTEM.reboot", "id": 1}, "captured", "method-matches"),
    ({"jsonrpc": "2.0", "method": "STATUS.get", "id": 1}, "not captured", "method-differs"),
    ({"method": "SYSTEM.reboot", "id": 1}, "not captured", "not-jsonrpc-2"),
]


@pytest.mark.parametrize(("body", "expected", "case_id"), RPC_CASES, ids=[c[-1] for c in RPC_CASES])
def test_json_rpc_restart(body: dict[str, Any], expected: str, case_id: str) -> None:
    """A json_rpc restart is captured when a call names its method."""
    config = _config({"type": "json_rpc", "method": "SYSTEM.reboot"})
    assert restart_evidence(config, [_entry("POST", RPC_URL, json.dumps(body))]) == expected


def test_no_declared_restart_is_not_applicable() -> None:
    """A config with no restart action reports n/a whatever the capture holds."""
    assert restart_evidence(_config(None), [_entry("GET", "http://192.168.100.1/reset.htm")]) == "n/a"
    assert restart_evidence({"actions": {"logout": {"type": "http", "method": "GET", "endpoint": "/x"}}}, []) == "n/a"


def test_empty_capture_is_not_captured() -> None:
    """A declared restart against a capture with no entries is not captured."""
    assert restart_evidence(_config({"type": "http", "method": "GET", "endpoint": "/reset.htm"}), []) == "not captured"
