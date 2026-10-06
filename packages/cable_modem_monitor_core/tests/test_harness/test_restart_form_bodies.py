"""Restart form-body enforcement: index of captured bodies and server rejection.

One form endpoint can serve reboot and factory reset by field values
alone, so a restart's ``name=value`` pairs must all appear together in
one body the capture posted there. Fewer fields pass (a browser posts
fields Core has no reason to send); an unrecorded field or value fails.

TEST DATA TABLES
================
``INDEX_CASES``: HAR entries in, indexed bodies out.
``MISMATCH_CASES``: captured bodies and a sent body in, unrecorded pairs out.
``SERVER_CASES``: a sent restart body in, HTTP status out.
"""

from __future__ import annotations

from typing import Any

import pytest
import requests
from solentlabs.cable_modem_monitor_core.models.modem_config import ModemConfig
from solentlabs.cable_modem_monitor_core.test_harness.routes import (
    build_form_bodies,
    unrecorded_form_pairs,
)
from solentlabs.cable_modem_monitor_core.test_harness.server import HARMockServer

REBOOT = "ResetYes=0x01&ResetFactoryNo=0x00"
FACTORY = "ResetFactoryYes=0x01&ResetNo=0x00"
ENDPOINT = "/goform/UbeeConfiguration"


def _post(url: str, text: str, mime: str = "application/x-www-form-urlencoded") -> dict[str, Any]:
    return {
        "request": {"method": "POST", "url": url, "postData": {"mimeType": mime, "text": text}},
        "response": {"status": 200, "headers": [], "content": {"text": "ok"}},
    }


def _pairs(*items: tuple[str, str]) -> frozenset[tuple[str, str]]:
    return frozenset(items)


# fmt: off
INDEX_CASES = [
    # (id, entries, expected index)
    ("one form body",
     [_post(f"http://m{ENDPOINT}", REBOOT)],
     {("POST", ENDPOINT): (_pairs(("ResetYes", "0x01"), ("ResetFactoryNo", "0x00")),)}),
    ("two bodies on one endpoint are both kept",
     [_post(f"http://m{ENDPOINT}", REBOOT), _post(f"http://m{ENDPOINT}", FACTORY)],
     {("POST", ENDPOINT): (
         _pairs(("ResetYes", "0x01"), ("ResetFactoryNo", "0x00")),
         _pairs(("ResetFactoryYes", "0x01"), ("ResetNo", "0x00")),
     )}),
    ("a repeated body is kept once",
     [_post(f"http://m{ENDPOINT}", REBOOT), _post(f"http://m{ENDPOINT}", REBOOT)],
     {("POST", ENDPOINT): (_pairs(("ResetYes", "0x01"), ("ResetFactoryNo", "0x00")),)}),
    ("a JSON object body is not a form body",
     [_post("http://m/api/restart", '{"a": 1}', "application/json")],
     {}),
    ("a body with no pairs is skipped",
     [_post(f"http://m{ENDPOINT}", "")],
     {}),
    ("a body that is not name=value is skipped",
     [_post(f"http://m{ENDPOINT}", "garbage")],
     {}),
    ("blank values are kept",
     [_post(f"http://m{ENDPOINT}", "a=&b=1")],
     {("POST", ENDPOINT): (_pairs(("a", ""), ("b", "1")),)}),
]

MISMATCH_CASES = [
    # (id, captured bodies, sent body, unrecorded pairs)
    ("exact match", [_pairs(("ResetYes", "0x01"), ("ResetFactoryNo", "0x00"))], REBOOT, set()),
    ("fewer fields pass", [_pairs(("ResetYes", "0x01"), ("ResetFactoryNo", "0x00"))], "ResetYes=0x01", set()),
    ("field order is irrelevant", [_pairs(("ResetYes", "0x01"), ("ResetFactoryNo", "0x00"))],
     "ResetFactoryNo=0x00&ResetYes=0x01", set()),
    ("wrong value", [_pairs(("ResetYes", "0x01"), ("ResetFactoryNo", "0x00"))],
     "ResetYes=0x01&ResetFactoryNo=0x01", {("ResetFactoryNo", "0x01")}),
    ("invented field", [_pairs(("ResetYes", "0x01"))], "ResetYes=0x01&Extra=1", {("Extra", "1")}),
    ("pairs from two captured bodies do not combine",
     [_pairs(("ResetYes", "0x01"), ("ResetFactoryNo", "0x00")),
      _pairs(("ResetFactoryYes", "0x01"), ("ResetNo", "0x00"))],
     "ResetYes=0x01&ResetFactoryYes=0x01", {("ResetFactoryYes", "0x01")}),
    ("matches the second captured body",
     [_pairs(("ResetYes", "0x01"), ("ResetFactoryNo", "0x00")),
      _pairs(("ResetFactoryYes", "0x01"), ("ResetNo", "0x00"))],
     FACTORY, set()),
    ("a JSON sent body is not compared", [_pairs(("a", "1"))], '{"b": 2}', set()),
    ("an empty sent body passes", [_pairs(("a", "1"))], "", set()),
    ("a placeholder value in the capture matches any value",
     [_pairs(("csrfp_token", "FIELD_64fba6c9"), ("resetInfo", "x"))], "csrfp_token=abc123&resetInfo=x", set()),
    ("a placeholder in the capture matches a blank value",
     [_pairs(("Password", "FIELD_7e8cc9ae"), ("UserId", ""))], "Password=&UserId=", set()),
    ("the sanitizer's REDACTED marker is a placeholder too",
     [_pairs(("passwd", "[REDACTED]"))], "passwd=anything", set()),
    ("a placeholder does not excuse an invented field",
     [_pairs(("csrfp_token", "FIELD_64fba6c9"))], "csrfp_token=abc&Extra=1", {("Extra", "1")}),
    ("a placeholder does not excuse a wrong value on another field",
     [_pairs(("csrfp_token", "FIELD_64fba6c9"), ("resetInfo", "x"))],
     "csrfp_token=abc&resetInfo=y", {("resetInfo", "y")}),
    ("a value merely shaped like a placeholder is not one",
     [_pairs(("a", "FIELD_xyz"))], "a=other", {("a", "other")}),
]

SERVER_CASES = [
    # (id, sent body, expected status)
    ("captured reboot body", REBOOT, 200),
    ("subset of the captured body", "ResetYes=0x01", 200),
    ("factory reset body never captured", FACTORY, 500),
    ("right field, wrong value", "ResetYes=0x01&ResetFactoryNo=0x01", 500),
]
# fmt: on


def _restart_config() -> ModemConfig:
    from solentlabs.cable_modem_monitor_core.config_loader import validate_modem_config

    return validate_modem_config(
        {
            "manufacturer": "Solent Labs",
            "model": "T100",
            "transport": "http",
            "default_host": "192.168.100.1",
            "status": "unsupported",
            "auth": {"strategy": "none"},
            "actions": {"restart": {"type": "http", "method": "POST", "endpoint": ENDPOINT}},
        }
    )


@pytest.mark.parametrize(("case_id", "entries", "expected"), INDEX_CASES, ids=[c[0] for c in INDEX_CASES])
def test_build_form_bodies(case_id: str, entries: list[dict[str, Any]], expected: dict[Any, Any]) -> None:
    assert build_form_bodies(entries) == expected


@pytest.mark.parametrize(
    ("case_id", "captured", "sent", "expected"), MISMATCH_CASES, ids=[c[0] for c in MISMATCH_CASES]
)
def test_unrecorded_form_pairs(
    case_id: str, captured: list[frozenset[tuple[str, str]]], sent: str, expected: set[tuple[str, str]]
) -> None:
    assert unrecorded_form_pairs(tuple(captured), sent.encode()) == frozenset(expected)


@pytest.mark.parametrize(("case_id", "body", "status"), SERVER_CASES, ids=[c[0] for c in SERVER_CASES])
def test_restart_replay_checks_form_body(case_id: str, body: str, status: int) -> None:
    with HARMockServer([_post(f"http://m{ENDPOINT}", REBOOT)], modem_config=_restart_config()) as server:
        resp = requests.post(f"{server.base_url}{ENDPOINT}", data=body, timeout=5)
    assert resp.status_code == status
    if status == 500:
        assert "restart" in resp.text


def test_restart_endpoint_the_capture_never_posted_is_not_checked() -> None:
    """No captured body to compare against: the rule has nothing to say."""
    entries = [_post("http://m/other", "a=1")]
    with HARMockServer(entries, modem_config=_restart_config()) as server:
        resp = requests.post(f"{server.base_url}{ENDPOINT}", data=FACTORY, timeout=5)
    assert resp.status_code == 200


def test_a_form_post_to_a_non_restart_endpoint_is_not_checked() -> None:
    """The rule is for restart only; other form posts keep today's behaviour."""
    entries = [_post("http://m/goform/other", "a=1")]
    with HARMockServer(entries, modem_config=_restart_config()) as server:
        resp = requests.post(f"{server.base_url}/goform/other", data="b=2", timeout=5)
    assert resp.status_code != 500


def test_restart_sharing_the_login_endpoint_is_not_checked() -> None:
    """One endpoint, two requests: a body cannot say which, so the rule stays out (DM1000)."""
    from solentlabs.cable_modem_monitor_core.config_loader import validate_modem_config

    config = validate_modem_config(
        {
            "manufacturer": "Solent Labs",
            "model": "T100",
            "transport": "http",
            "default_host": "192.168.100.1",
            "status": "unsupported",
            "auth": {"strategy": "form", "action": "/setup.cgi", "cookie_name": "s"},
            "actions": {"restart": {"type": "http", "method": "POST", "endpoint": "/setup.cgi"}},
        }
    )
    entries = [_post("http://m/setup.cgi", "todo=login&user=a"), _post("http://m/setup.cgi", "todo=reboot")]
    with HARMockServer(entries, modem_config=config) as server:
        login = requests.post(
            f"{server.base_url}/setup.cgi", data="todo=login&user=a", timeout=5, allow_redirects=False
        )
    assert login.status_code != 500
