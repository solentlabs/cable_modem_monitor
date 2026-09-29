"""Tests for CBN intake: the login decides the transport and carries the form_cbn fields; setter calls are actions.

Table-driven over the login request's shape. Per docs/ONBOARDING_SPEC.md
Phase 1 and Phase 2 (CBN transport).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from solentlabs.cable_modem_monitor_catalog_tools.analysis.actions.grading import grade_action
from solentlabs.cable_modem_monitor_catalog_tools.analysis.auth import detect_auth
from solentlabs.cable_modem_monitor_catalog_tools.analysis.transport import TransportResult
from solentlabs.cable_modem_monitor_catalog_tools.analysis.types import FleetPatterns
from solentlabs.cable_modem_monitor_catalog_tools.analyze_har import analyze_har
from solentlabs.cable_modem_monitor_catalog_tools.generate_config import generate_config
from tests._helpers import write_har

_HOST = "http://192.168.100.1"


def _post(path: str, body: str, *, referer: str = "", cookie: str = "", response: str = "") -> dict[str, Any]:
    """A form-encoded POST entry."""
    headers = [{"name": "Content-Type", "value": "application/x-www-form-urlencoded"}]
    if referer:
        headers.append({"name": "Referer", "value": f"{_HOST}{referer}"})
    if cookie:
        headers.append({"name": "Cookie", "value": cookie})
    return {
        "request": {
            "method": "POST",
            "url": f"{_HOST}{path}",
            "headers": headers,
            "postData": {"mimeType": "application/x-www-form-urlencoded", "text": body},
        },
        "response": {
            "status": 200,
            "headers": [{"name": "Content-Type", "value": "text/xml"}],
            "content": {"size": len(response), "mimeType": "text/xml", "text": response},
        },
    }


def _login(
    fun: str = "15",
    setter: str = "/xml/setter.xml",
    username: str = "NULL",
    response: str = "successful;SID=1",
    referer: str = "/common_page/login.html",
) -> dict[str, Any]:
    """A CBN login: token first, a fun code, the credentials."""
    return _post(
        setter,
        f"token=T1&fun={fun}&Username={username}&Password=ENC",
        referer=referer,
        cookie="sessionToken=T1",
        response=response,
    )


def _getter(fun: str, path: str = "/xml/getter.xml") -> dict[str, Any]:
    """A CBN data call."""
    return _post(path, f"token=T2&fun={fun}", response="<downstream_table/>")


# =============================================================================
# Transport: the login decides
# =============================================================================
#
# ┌──────────────────────────────────────────┬───────────┬──────────────────────────────┐
# │ entries                                  │ transport │ description                  │
# ├──────────────────────────────────────────┼───────────┼──────────────────────────────┤
# │ CBN login + getter calls                 │ cbn       │ the credential call decides  │
# │ getter calls only                        │ http      │ data calls alone do not      │
# │ credential POST, fun but token not first │ http      │ token-first is the protocol  │
# └──────────────────────────────────────────┴───────────┴──────────────────────────────┘
#
# fmt: off
TRANSPORT_CASES: list[tuple[list[dict[str, Any]], str, str]] = [
    ([_login(), _getter("10")],                                                   "cbn",  "login-decides"),
    ([_getter("10"), _getter("11")],                                              "http", "data-calls-alone"),
    ([_post("/xml/setter.xml", "fun=15&token=T1&Username=NULL&Password=ENC")],    "http", "token-not-first"),
]
# fmt: on


@pytest.mark.parametrize("entries,transport", [c[:2] for c in TRANSPORT_CASES], ids=[c[2] for c in TRANSPORT_CASES])
def test_cbn_transport(entries: list[dict[str, Any]], transport: str) -> None:
    """A token-first fun call carrying a password-shaped field makes the transport cbn."""
    assert TransportResult.detect(entries).transport == transport


# =============================================================================
# Auth fields from the login call
# =============================================================================

_DEFAULTS = {
    "login_fun": 15,
    "setter_endpoint": "/xml/setter.xml",
    "getter_endpoint": "/xml/getter.xml",
    "login_page": "/common_page/login.html",
    "session_cookie_name": "sessionToken",
    "username_value": "NULL",
}

_OTHER_ENDPOINTS = {"login_fun": 7, "setter_endpoint": "/cgi/set.xml", "getter_endpoint": "/cgi/get.xml"}
_OTHER_USER = {"username_value": "admin", "login_page": "/login.htm"}

# fmt: off
FIELD_CASES: list[tuple[list[dict[str, Any]], dict[str, Any], str]] = [
    # (entries,                                                               differs,          id)
    ([_login(), _getter("10"), _getter("11")],                                {},               "defaults"),
    ([_login(fun="7", setter="/cgi/set.xml"), _getter("10", "/cgi/get.xml")], _OTHER_ENDPOINTS, "endpoints-and-fun"),
    ([_login(username="admin", referer="/login.htm"), _getter("10")],         _OTHER_USER,      "username-and-page"),
    ([_login(fun="3", response="idloginincorrect"), _login(), _getter("10")], {},               "accepted-wins"),
]
# fmt: on


@pytest.mark.parametrize("entries,differs", [c[:2] for c in FIELD_CASES], ids=[c[2] for c in FIELD_CASES])
def test_form_cbn_fields(entries: list[dict[str, Any]], differs: dict[str, Any]) -> None:
    """Every form_cbn field comes from the capture's login and data calls."""
    auth = detect_auth(entries, "cbn", [], [])
    assert auth.strategy == "form_cbn"
    assert auth.fields == {**_DEFAULTS, **differs}


def test_no_successful_attempt_takes_the_first() -> None:
    """Without a successful body, the first login stands; its fields are the same call shape."""
    auth = detect_auth([_login(fun="3", response=""), _login(fun="4", response="idloginincorrect")], "cbn", [], [])
    assert auth.fields["login_fun"] == 3


def test_analyze_har_routes_cbn(tmp_path: Path) -> None:
    """A CBN capture analyzes as cbn with form_cbn auth."""
    result = analyze_har(write_har(tmp_path, {"log": {"entries": [_login(), _getter("10")]}}))
    assert (result.transport.transport, result.auth.strategy) == ("cbn", "form_cbn")


def test_generated_auth_omits_defaults() -> None:
    """Fields equal to the Core model's defaults are left out of modem.yaml."""
    analysis = {
        "transport": "cbn",
        "auth": {"strategy": "form_cbn", "fields": {**_DEFAULTS, "username_value": "admin"}},
        "session": {},
        "actions": {},
        "sections": None,
    }
    modem = yaml.safe_load(generate_config(analysis, {"manufacturer": "Solent Labs", "model": "T1"}).modem_yaml)
    assert modem["transport"] == "cbn"
    assert modem["auth"] == {"strategy": "form_cbn", "username_value": "admin"}


def test_reboot_page_is_not_an_http_action(tmp_path: Path) -> None:
    """Loading the reboot page is not read as an http restart, which transport cbn would reject."""
    page = {
        "request": {"method": "GET", "url": f"{_HOST}/common_page/Reboot.html", "headers": []},
        "response": {
            "status": 200,
            "headers": [{"name": "Content-Type", "value": "text/html"}],
            "content": {"size": 0, "mimeType": "text/html", "text": "<html></html>"},
        },
    }
    reboot = _post("/xml/setter.xml", "token=T3&fun=8", referer="/common_page/Reboot.html")
    result = analyze_har(write_har(tmp_path, {"log": {"entries": [_login(), _getter("10"), page, reboot]}}))
    assert (result.actions.logout, result.actions.restart) == (None, None)


# =============================================================================
# Actions: setter calls other than the login are logout and restart candidates
# =============================================================================

_REBOOT = _post("/xml/setter.xml", "token=T3&fun=8", referer="/common_page/Reboot.html")
_LOGOUT = _post("/xml/setter.xml", "token=T4&fun=16", referer="/index.html")
_ACTION_ENTRIES = [_login(), _getter("10"), _REBOOT, _LOGOUT]


def _action_ambiguities(tmp_path: Path, fleet: FleetPatterns | None = None) -> dict[str, Any]:
    result = analyze_har(write_har(tmp_path, {"log": {"entries": _ACTION_ENTRIES}}), fleet=fleet)
    return {a.field: a for a in result.ambiguities if a.field.startswith("actions.")}


def test_setter_calls_are_action_candidates(tmp_path: Path) -> None:
    """Each non-login setter fun is a candidate for both actions, citing its page and body; neither blocks."""
    ambiguities = _action_ambiguities(tmp_path)
    assert sorted(ambiguities) == ["actions.logout.fun", "actions.restart.fun"]
    for ambiguity in ambiguities.values():
        assert ambiguity.blocking is False
        assert [(c.value, [(e.source, e.snippet) for e in c.evidence]) for c in ambiguity.candidates] == [
            ("8", [("/common_page/Reboot.html", "token=T3&fun=8")]),
            ("16", [("/index.html", "token=T4&fun=16")]),
        ]


def test_confirmed_fleet_prefills_each_action(tmp_path: Path) -> None:
    """A confirmed entry's fun corroborates its candidate and pre-fills that action only."""
    fleet = FleetPatterns(confirmed_config_values={"actions.restart.fun": {"8": ["vendor/m1"]}})
    ambiguities = _action_ambiguities(tmp_path, fleet)
    assert ambiguities["actions.restart.fun"].resolution == {"value": "8", "source": "fleet"}
    assert ambiguities["actions.logout.fun"].resolution is None


def test_resolved_actions_generate_cbn_actions(tmp_path: Path) -> None:
    """Resolved funs become type: cbn actions with integer codes."""
    analysis = analyze_har(write_har(tmp_path, {"log": {"entries": _ACTION_ENTRIES}})).to_dict()
    for ambiguity in analysis["ambiguities"]:
        value = {"actions.restart.fun": "8", "actions.logout.fun": "16"}.get(ambiguity["field"])
        if value:
            ambiguity["resolution"] = {"value": value}
    modem = yaml.safe_load(generate_config(analysis, {"manufacturer": "Solent Labs", "model": "T1"}).modem_yaml)
    assert modem["actions"] == {"logout": {"type": "cbn", "fun": 16}, "restart": {"type": "cbn", "fun": 8}}


# fmt: off
CBN_GRADE_CASES: list[tuple[dict[str, Any], dict[str, Any], str, str]] = [
    ({"type": "cbn", "fun": 8}, {"type": "cbn", "fun": 8},  "match",    "same-fun"),
    ({"type": "cbn", "fun": 8}, {"type": "cbn", "fun": 16}, "mismatch", "different-fun"),
]
# fmt: on


@pytest.mark.parametrize(
    "detected,committed,status", [c[:3] for c in CBN_GRADE_CASES], ids=[c[3] for c in CBN_GRADE_CASES]
)
def test_cbn_action_identity_is_the_fun(detected: dict[str, Any], committed: dict[str, Any], status: str) -> None:
    """Two CBN actions are the same action when their fun codes are."""
    grade = grade_action(detected, committed)
    assert grade is not None
    assert grade.status == status
