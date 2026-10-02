"""Tests for Phase 4: HTTP action detection.

Fixture-driven tests for HTTP logout and restart endpoint detection.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.actions import detect_actions
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


@pytest.mark.parametrize(
    ("post_data", "expected_category"),
    [
        # Form body with an action-like param name
        ({"params": [{"name": "RebootAction", "value": "1"}]}, "unmatched_restart"),
        # JSON body: its top-level keys are read the same way
        ({"mimeType": "application/json", "text": '{"rebootNow": {"enable": true}}'}, "unmatched_restart"),
        ({"mimeType": "application/json", "text": '{"doLogout": true}'}, "unmatched_logout"),
        # JSON body with no action-like key
        ({"mimeType": "application/json", "text": '{"language": "en"}'}, None),
    ],
)
def test_unmatched_action_post(post_data: dict, expected_category: str | None) -> None:
    """An action-like POST at an unknown URL is a core gap, whatever its body encoding."""
    core_gaps: list = []
    detect_actions([_post("/api/v9/devctl", post_data)], "http", [], core_gaps)
    assert [g.category for g in core_gaps] == ([expected_category] if expected_category else [])


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
