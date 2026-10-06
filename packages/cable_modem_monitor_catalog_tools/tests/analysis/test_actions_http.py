"""Tests for Phase 4: HTTP action detection.

Fixture-driven tests for HTTP logout and restart endpoint detection.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.actions import detect_actions
from solentlabs.cable_modem_monitor_catalog_tools.analysis.actions.types import ActionsDetail
from solentlabs.cable_modem_monitor_catalog_tools.analysis.ambiguity import Ambiguity
from tests._helpers import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "actions" / "http"
HTTP_FIXTURES = collect_fixtures(FIXTURES_DIR)


# =====================================================================
# HTTP action detection - fixture-driven
# =====================================================================


@pytest.mark.parametrize("fixture_path", HTTP_FIXTURES, ids=[f.stem for f in HTTP_FIXTURES])
def test_http_action_presence(fixture_path: Path) -> None:
    """Correct action presence/absence for each HTTP fixture."""
    data = load_fixture(fixture_path)
    result = detect_actions(data["_entries"], "http")
    assert (result.logout is not None) == (data["_expected_logout"] is not None)
    assert (result.restart is not None) == (data["_expected_restart"] is not None)


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in HTTP_FIXTURES if load_fixture(f)["_expected_logout"] is not None],
    ids=[f.stem for f in HTTP_FIXTURES if load_fixture(f)["_expected_logout"] is not None],
)
def test_http_logout_details(fixture_path: Path) -> None:
    """HTTP logout details match fixture expectations."""
    data = load_fixture(fixture_path)
    result = detect_actions(data["_entries"], "http")
    expected = data["_expected_logout"]
    assert result.logout is not None
    assert result.logout.type == expected["type"]
    assert result.logout.method == expected["method"]
    assert result.logout.endpoint == expected["endpoint"]
    if "params" in expected:
        assert result.logout.params == expected["params"]
    if "credential_params" in expected:
        assert result.logout.credential_params == expected["credential_params"]
    if "source" in expected:
        assert result.logout.source == expected["source"]
    if "pre_fetch_url" in expected:
        assert result.logout.pre_fetch_url == expected["pre_fetch_url"]
    if "endpoint_pattern" in expected:
        assert result.logout.endpoint_pattern == expected["endpoint_pattern"]
    # Every fixture pins json_body: observed JSON is copied, anything else yields none
    assert result.logout.json_body == expected.get("json_body")


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in HTTP_FIXTURES if "_expected_warnings_contains" in load_fixture(f)],
    ids=[f.stem for f in HTTP_FIXTURES if "_expected_warnings_contains" in load_fixture(f)],
)
def test_http_action_warnings(fixture_path: Path) -> None:
    """Unresolvable call-site params surface as warnings."""
    data = load_fixture(fixture_path)
    warnings: list[str] = []
    detect_actions(data["_entries"], "http", warnings)
    for needle in data["_expected_warnings_contains"]:
        assert any(needle in w for w in warnings), f"no warning mentions {needle!r}: {warnings}"


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in HTTP_FIXTURES if load_fixture(f)["_expected_restart"] is not None],
    ids=[f.stem for f in HTTP_FIXTURES if load_fixture(f)["_expected_restart"] is not None],
)
def test_http_restart_details(fixture_path: Path) -> None:
    """HTTP restart details match fixture expectations."""
    data = load_fixture(fixture_path)
    result = detect_actions(data["_entries"], "http")
    expected = data["_expected_restart"]
    assert result.restart is not None
    assert result.restart.type == expected["type"]
    assert result.restart.method == expected["method"]
    assert result.restart.endpoint == expected["endpoint"]
    if "params" in expected:
        assert result.restart.params == expected["params"]
    if "credential_params" in expected:
        assert result.restart.credential_params == expected["credential_params"]
    if "source" in expected:
        assert result.restart.source == expected["source"]
    if "pre_fetch_url" in expected:
        assert result.restart.pre_fetch_url == expected["pre_fetch_url"]
    if "endpoint_pattern" in expected:
        assert result.restart.endpoint_pattern == expected["endpoint_pattern"]
    # Every fixture pins json_body: observed JSON is copied, anything else yields none
    assert result.restart.json_body == expected.get("json_body")


@pytest.mark.parametrize(
    ("fixture_stem", "gap_reported"),
    [
        # Body observed as JSON: copied, no gap
        ("restart_json_body", False),
        # Body observed as form params: no gap
        ("restart_router_status", False),
        # Body observed but sanitized: withheld, and not reported as unobserved
        ("restart_json_body_sanitized", False),
        # Endpoint only in page script: the body is unobserved
        ("source_inferred_rest_unobserved", True),
        # Call-site params resolved from source: existing pass-1 rules, no gap
        ("source_inferred_ajax_restart", False),
    ],
)
def test_unobserved_body_gap(fixture_stem: str, gap_reported: bool) -> None:
    """A non-GET action with no captured request reports its body as unobserved."""
    data = load_fixture(FIXTURES_DIR / f"{fixture_stem}.json")
    warnings: list[str] = []
    detect_actions(data["_entries"], "http", warnings)
    assert any("request body unobserved" in w for w in warnings) == gap_reported


def _post(path: str, post_data: dict) -> dict:
    """One POST entry to an endpoint no action pattern matches."""
    return {"request": {"method": "POST", "url": f"http://192.168.100.1{path}", "postData": post_data}, "response": {}}


def _detect(entries: list[dict]) -> tuple[ActionsDetail, list[Ambiguity]]:
    """Detect HTTP actions; return the actions and the ambiguities."""
    ambiguities: list[Ambiguity] = []
    actions = detect_actions(entries, "http", [], ambiguities)
    return actions, ambiguities


@pytest.mark.parametrize(
    ("post_data", "expected_field"),
    [
        # Form body with an action-like param name
        ({"params": [{"name": "RebootAction", "value": "1"}]}, "actions.restart.endpoint"),
        # JSON body: its top-level keys are read the same way
        ({"mimeType": "application/json", "text": '{"rebootNow": {"enable": true}}'}, "actions.restart.endpoint"),
        ({"mimeType": "application/json", "text": '{"doLogout": true}'}, "actions.logout.endpoint"),
        # JSON body with no action-like key
        ({"mimeType": "application/json", "text": '{"language": "en"}'}, None),
    ],
)
def test_unmatched_action_write_is_candidate(post_data: dict, expected_field: str | None) -> None:
    """An action-like write at an unknown URL is a non-blocking endpoint candidate."""
    _, ambiguities = _detect([_post("/api/v9/devctl", post_data)])
    expected = [(expected_field, False, ["/api/v9/devctl"])] if expected_field else []
    assert [(a.field, a.blocking, [c.value for c in a.candidates]) for a in ambiguities] == expected


@pytest.mark.parametrize(("method", "candidate"), [("POST", True), ("PUT", True), ("PATCH", True), ("GET", False)])
def test_unmatched_action_any_write_method(method: str, candidate: bool) -> None:
    """A logout sent by any write method at an unknown URL is a candidate; a GET carries no body to read."""
    entry = _post("/actionHandler/ajaxSet_signout.php", {"mimeType": "application/json", "text": '{"DoLogOut": 1}'})
    entry["request"]["method"] = method
    actions, ambiguities = _detect([entry])
    assert [a.field for a in ambiguities] == (["actions.logout.endpoint"] if candidate else [])
    candidates = actions.candidates.get("logout", {})
    assert [(c.method, c.json_body) for c in candidates.values()] == ([(method, {"DoLogOut": 1})] if candidate else [])


def test_repeated_unmatched_action_is_one_candidate() -> None:
    """The same write sent twice is one candidate; another endpoint is another candidate of the same ambiguity."""
    logout = {"mimeType": "application/json", "text": '{"DoLogOut": 1}'}
    entries = [
        _post("/actionHandler/ajaxSet_signout.php", logout),
        _post("/actionHandler/ajaxSet_signout.php", logout),
        _post("/actionHandler/ajaxSet_signoff.php", logout),
    ]
    _, ambiguities = _detect(entries)
    assert [(a.field, [(c.value, len(c.evidence)) for c in a.candidates]) for a in ambiguities] == [
        (
            "actions.logout.endpoint",
            [("/actionHandler/ajaxSet_signout.php", 1), ("/actionHandler/ajaxSet_signoff.php", 1)],
        )
    ]


# One form, two operations: radios pick which, so only an observed body is safe to replay
_SHARED_FORM = (
    '<form action=/goform/devctl method=POST name="Device">'
    '<input type="radio" name="RebootYes" value=0x01><input type="radio" name="RebootNo" value=0x00 CHECKED>'
    '<input type="radio" name="WipeYes" value=0x01><input type="radio" name="WipeNo" value=0x00 CHECKED></form>'
)
_REBOOT = "RebootYes=0x01&WipeNo=0x00"
_WIPE = "RebootNo=0x00&WipeYes=0x01"


def _page(path: str) -> dict:
    """A captured page whose form posts to /goform/devctl."""
    return {
        "request": {"method": "GET", "url": f"http://192.168.100.1{path}"},
        "response": {"status": 200, "content": {"text": _SHARED_FORM}},
    }


def _sent(body: str, referer: str = "/device.asp", mime: str = "application/x-www-form-urlencoded") -> dict:
    """The form's POST to /goform/devctl from ``referer``."""
    write = _post("/goform/devctl", {"mimeType": mime, "text": body})
    write["request"]["headers"] = [{"name": "Referer", "value": f"http://192.168.100.1{referer}"}]
    return write


def test_candidate_carries_the_observed_request() -> None:
    """The candidate is the request as sent: its exact body, the sending page as evidence and pre-fetch."""
    actions, ambiguities = _detect([_page("/device.asp"), _sent(_REBOOT)])

    assert actions.restart is None
    restart = actions.candidates["restart"]["/goform/devctl"]
    assert (restart.type, restart.method, restart.source) == ("http", "POST", "observed")
    assert restart.params == {"RebootYes": "0x01", "WipeNo": "0x00"}
    assert restart.pre_fetch_url == "/device.asp"
    assert [[(e.source, e.snippet) for e in c.evidence] for c in ambiguities[0].candidates] == [
        [("/device.asp", _REBOOT)]
    ]
    assert actions.to_dict()["candidates"]["restart"]["/goform/devctl"]["params"] == restart.params


_ENCODED = '{"reboot": {"user": "FIELD_0a1b2c3d"}}'

# ┌───────────────────────────────┬──────────┬──────────────────────────────┬──────────────────────────────┐
# │ writes to /goform/devctl      │ stored   │ evidence snippets            │ description                  │
# ├───────────────────────────────┼──────────┼──────────────────────────────┼──────────────────────────────┤
# │ reboot, reboot                │ yes      │ reboot                       │ a repeat adds nothing        │
# │ wipe, reboot                  │ no       │ wipe, reboot                 │ bodies differ: none written  │
# │ encoded JSON body             │ no       │ the encoded body             │ no firmware value to send    │
# └───────────────────────────────┴──────────┴──────────────────────────────┴──────────────────────────────┘
#
# fmt: off
_BODY_CASES: list[tuple[list[dict], bool, list[str], str]] = [
    # (writes,                                          stored, snippets,           id)
    ([_sent(_REBOOT), _sent(_REBOOT)],                  True,   [_REBOOT],          "repeat"),
    ([_sent(_WIPE), _sent(_REBOOT)],                    False,  [_WIPE, _REBOOT],   "bodies-differ"),
    ([_sent(_ENCODED, mime="application/json")],        False,  [_ENCODED],         "encoded"),
]
# fmt: on


@pytest.mark.parametrize(
    ("writes", "stored", "snippets"), [(w, s, n) for w, s, n, _ in _BODY_CASES], ids=[c[3] for c in _BODY_CASES]
)
def test_candidate_stored_only_with_one_plain_body(writes: list[dict], stored: bool, snippets: list[str]) -> None:
    """An endpoint names an action only when the capture sent it one plain body; every body is evidence."""
    actions, ambiguities = _detect([_page("/device.asp"), *writes])
    assert ("/goform/devctl" in actions.candidates.get("restart", {})) == stored
    assert [e.snippet for e in ambiguities[0].candidates[0].evidence] == snippets


def test_params_only_body_is_evidence() -> None:
    """A capture that kept form params but no body text still shows the LLM what was sent."""
    _, ambiguities = _detect([_post("/api/v9/devctl", {"params": [{"name": "RebootAction", "value": "1"}]})])
    assert [e.snippet for e in ambiguities[0].candidates[0].evidence] == ["RebootAction=1"]


def test_pre_fetch_is_the_sending_page() -> None:
    """Two pages post to one endpoint: the pre-fetch is the page that sent the request."""
    actions, _ = _detect([_page("/status.asp"), _page("/device.asp"), _sent(_REBOOT, referer="/device.asp")])
    assert actions.candidates["restart"]["/goform/devctl"].pre_fetch_url == "/device.asp"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH"])
def test_write_outranks_earlier_page_get(method: str) -> None:
    """The operative write is the action, whatever its method; the page GET before it is not."""
    page = {"request": {"method": "GET", "url": "http://192.168.100.1/reboot.htm"}, "response": {"status": 200}}
    write = _post("/api/v1/reboot", {"mimeType": "application/json", "text": '{"reboot": true}'})
    write["request"]["method"] = method
    actions = detect_actions([page, write], "http", [], [])
    assert actions.restart is not None
    assert (actions.restart.method, actions.restart.endpoint) == (method, "/api/v1/reboot")


_COPIED = {"json_body": True, "body": "", "body_evidence": {}, "warning": None}


@pytest.mark.parametrize(
    ("fixture_stem", "expected"),
    [
        # Plain JSON body: copied (f3896lg-vmb, sbg8300 shapes)
        ("restart_json_body", _COPIED),
        ("restart_json_body_put", _COPIED),
        # Sanitized value at the top level: encoded, withheld (tg3442s shape)
        (
            "restart_json_body_sanitized",
            {
                "json_body": False,
                "body": "encoded",
                "body_evidence": {"keys": ["EncryptedData", "user"], "sanitized": ["user"]},
                "warning": "not copied",
            },
        ),
        # Sanitized value nested below the top level: encoded, withheld
        (
            "restart_json_body_nested_sanitized",
            {
                "json_body": False,
                "body": "encoded",
                "body_evidence": {"keys": ["action", "auth"], "sanitized": ["auth.user"]},
                "warning": "not copied",
            },
        ),
        # Endpoint only in page script: unobserved, a different state (f3896lg-zg shape)
        (
            "source_inferred_rest_unobserved",
            {"json_body": False, "body": "unobserved", "body_evidence": {}, "warning": "request body unobserved"},
        ),
        # Call-site params from source: no body state
        ("source_inferred_ajax_restart", {**_COPIED, "json_body": False}),
    ],
)
def test_restart_body_state(fixture_stem: str, expected: dict) -> None:
    """A restart body is copied, encoded (withheld, with evidence) or unobserved, never guessed."""
    data = load_fixture(FIXTURES_DIR / f"{fixture_stem}.json")
    warnings: list[str] = []
    result = detect_actions(data["_entries"], "http", warnings)
    assert result.restart is not None
    assert (result.restart.json_body is not None) == expected["json_body"]
    assert result.restart.body == expected["body"]
    assert result.restart.body_evidence == expected["body_evidence"]
    if expected["warning"]:
        assert any(expected["warning"] in w and "restart" in w for w in warnings), warnings
