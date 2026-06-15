"""Tests for action grading: pipeline-detected vs committed actions."""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.actions.grading import (
    grade_action,
    grade_actions,
)
from solentlabs.cable_modem_monitor_catalog_tools.grading import GRADE_SEVERITY

_HTTP_RESTART = {
    "type": "http",
    "method": "POST",
    "endpoint": "/actionHandler/ajaxSet_Reset_Restore.jst",
    "params": {"resetInfo": '["btn1","Device","admin"]', "csrfp_token": "{cookie:csrfp_token}"},
}

_HNAP_RESTART = {
    "type": "hnap",
    "action_name": "SetArrisConfigurationInfo",
    "params": {"Action": "reboot"},
}


@pytest.mark.parametrize(
    ("detected", "committed", "expected_status"),
    [
        # Neither side has the action — nothing to grade
        (None, None, None),
        # Committed config the pipeline did not produce
        (None, _HTTP_RESTART, "committed_only"),
        (None, _HNAP_RESTART, "committed_only"),
        # Pipeline detection the catalog never adopted
        (_HTTP_RESTART, None, "pipeline_only"),
        # Transport type disagrees (e.g. http detection on a cbn modem)
        ({"type": "http", "method": "GET", "endpoint": "/logout"}, {"type": "cbn", "fun": 16}, "mismatch"),
        # Identity match, params reproduced exactly
        (_HTTP_RESTART, _HTTP_RESTART, "match"),
        # Identity match, committed param not extracted (XB10 resetInfo case)
        (
            {**_HTTP_RESTART, "params": {"csrfp_token": "{cookie:csrfp_token}"}},
            _HTTP_RESTART,
            "partial",
        ),
        # Identity match, param value differs
        (
            {**_HTTP_RESTART, "params": {**_HTTP_RESTART["params"], "csrfp_token": "stale-literal"}},
            _HTTP_RESTART,
            "partial",
        ),
        # Identity match, pipeline extracted a param the catalog never adopted
        (
            {**_HTTP_RESTART, "params": {**_HTTP_RESTART["params"], "surplus": "1"}},
            _HTTP_RESTART,
            "partial",
        ),
        # Endpoint disagrees (netgear /reboot_btn vs /goform/RouterStatus case)
        (
            {**_HTTP_RESTART, "endpoint": "/reboot_btn"},
            _HTTP_RESTART,
            "mismatch",
        ),
        # Method disagrees
        ({**_HTTP_RESTART, "method": "GET"}, _HTTP_RESTART, "mismatch"),
        # No params on either side
        (
            {"type": "http", "method": "GET", "endpoint": "/Logout.htm"},
            {"type": "http", "method": "GET", "endpoint": "/Logout.htm"},
            "match",
        ),
        # hnap identity is action_name; extra committed config keys
        # (pre_fetch_action, response_key, ...) are out of grading scope
        (_HNAP_RESTART, {**_HNAP_RESTART, "pre_fetch_action": "GetArrisConfigurationInfo"}, "match"),
        ({**_HNAP_RESTART, "action_name": "SetOther"}, _HNAP_RESTART, "mismatch"),
        # Committed json_body the pipeline cannot produce (superhub5 shape)
        (
            {"type": "http", "method": "POST", "endpoint": "/rest/v1/system/reboot"},
            {
                "type": "http",
                "method": "POST",
                "endpoint": "/rest/v1/system/reboot",
                "json_body": {"reboot": {"enable": True}},
            },
            "partial",
        ),
        # Committed yaml params may be non-string scalars
        (
            {"type": "http", "method": "POST", "endpoint": "/x", "params": {"n": "1"}},
            {"type": "http", "method": "POST", "endpoint": "/x", "params": {"n": 1}},
            "match",
        ),
        # Detected pre-fetch shape the committed config lacks (c3700 case)
        (
            {
                "type": "http",
                "method": "POST",
                "endpoint": "/goform/RouterStatus",
                "pre_fetch_url": "/RouterStatus.htm",
                "endpoint_pattern": "RouterStatus",
            },
            {"type": "http", "method": "POST", "endpoint": "/goform/RouterStatus"},
            "partial",
        ),
        # Full pre-fetch shape reproduced (cm2000 case, params aside)
        (
            {
                "type": "http",
                "method": "POST",
                "endpoint": "/goform/RouterStatus",
                "pre_fetch_url": "/RouterStatus.htm",
                "endpoint_pattern": "RouterStatus",
            },
            {
                "type": "http",
                "method": "POST",
                "endpoint": "/goform/RouterStatus",
                "pre_fetch_url": "/RouterStatus.htm",
                "endpoint_pattern": "RouterStatus",
            },
            "match",
        ),
    ],
)
def test_grade_action(detected: dict | None, committed: dict | None, expected_status: str | None) -> None:
    """Each detected/committed pair grades to the expected status."""
    grade = grade_action(detected, committed)
    if expected_status is None:
        assert grade is None
    else:
        assert grade is not None
        assert grade.status == expected_status


def test_grade_actions_skips_absent() -> None:
    """grade_actions only grades actions present on at least one side."""
    grades = grade_actions({"logout": None, "restart": _HTTP_RESTART}, {"restart": _HTTP_RESTART})
    assert set(grades) == {"restart"}
    assert grades["restart"].status == "match"


def test_non_match_grades_carry_detail() -> None:
    """Every non-match grade explains itself."""
    grade = grade_action({**_HTTP_RESTART, "endpoint": "/reboot_btn"}, _HTTP_RESTART)
    assert grade is not None
    assert grade.detail


def test_severity_covers_all_statuses() -> None:
    """The ratchet ordering knows every status grade_action can emit."""
    assert set(GRADE_SEVERITY) == {"match", "partial", "pipeline_only", "committed_only", "mismatch"}
    assert GRADE_SEVERITY["match"] < GRADE_SEVERITY["partial"] < GRADE_SEVERITY["mismatch"]
