"""Tests for orchestration/actions/hnap_action.py event emission."""

from __future__ import annotations

from unittest.mock import MagicMock

import requests
from solentlabs.cable_modem_monitor_core.orchestration.events import (
    ActionCompleted,
    ActionConnectionLost,
    ActionFailed,
    ActionPreFetchCompleted,
    ActionPreFetchFailed,
    ActionStarted,
    EventLevel,
)

from ..orchestration.event_capture import assert_event_emitted, capture_events


def _make_action(
    *,
    action_name: str = "Reboot",
    params: dict | None = None,
    pre_fetch_action: str = "",
    response_key: str = "RebootResponse",
    result_key: str = "RebootResult",
    success_value: str = "OK",
) -> MagicMock:
    action = MagicMock()
    action.action_name = action_name
    action.params = params or {}
    action.pre_fetch_action = pre_fetch_action
    action.response_key = response_key
    action.result_key = result_key
    action.success_value = success_value
    return action


def _make_session(
    *,
    json_body: object = None,
    raise_exc: Exception | None = None,
) -> MagicMock:
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    if json_body is not None:
        resp.json.return_value = json_body
    else:
        resp.json.return_value = {"RebootResponse": {"RebootResult": "OK"}}
    if raise_exc is not None:
        session.post.side_effect = raise_exc
    else:
        session.post.return_value = resp
    return session


def _call_execute(session, action, *, log_level: int = 20, model: str = "DG3450"):
    from solentlabs.cable_modem_monitor_core.orchestration.actions.hnap_action import execute_hnap_action

    return execute_hnap_action(
        session,
        "http://192.168.100.1",
        action,
        private_key="deadbeef",
        hmac_algorithm="md5",
        timeout=5,
        log_level=log_level,
        model=model,
    )


# ---------------------------------------------------------------------------
# ActionStarted + ActionCompleted — success path
# ---------------------------------------------------------------------------


def test_action_started_emitted():
    session = _make_session()
    action = _make_action()
    with capture_events() as events:
        _call_execute(session, action)
    assert_event_emitted(events, ActionStarted, model="DG3450", transport="hnap")
    event = next(e for e in events if isinstance(e, ActionStarted))
    assert event.action_name == "Reboot"


def test_action_completed_on_ok_result():
    session = _make_session(json_body={"RebootResponse": {"RebootResult": "OK"}})
    action = _make_action()
    with capture_events() as events:
        result = _call_execute(session, action)
    assert result.success is True
    assert_event_emitted(events, ActionCompleted, model="DG3450", transport="hnap")
    event = next(e for e in events if isinstance(e, ActionCompleted))
    assert event.status_code is None
    assert event.result == "OK"


def test_action_completed_level_matches_log_level():
    session = _make_session()
    action = _make_action()
    with capture_events() as events:
        _call_execute(session, action, log_level=10)
    event = next(e for e in events if isinstance(e, ActionCompleted))
    assert event.level == EventLevel.DEBUG


def test_action_completed_no_result_key():
    # When response_key/result_key are empty, action succeeds with "sent"
    session = _make_session(json_body={"SomeKey": "val"})
    action = _make_action(response_key="", result_key="", success_value="")
    with capture_events() as events:
        result = _call_execute(session, action)
    assert result.success is True
    event = next(e for e in events if isinstance(e, ActionCompleted))
    assert event.result == "sent"


# ---------------------------------------------------------------------------
# ActionConnectionLost
# ---------------------------------------------------------------------------


def test_action_connection_lost_emitted():
    session = _make_session(raise_exc=requests.ConnectionError())
    action = _make_action()
    with capture_events() as events:
        result = _call_execute(session, action)
    assert result.success is True
    assert_event_emitted(events, ActionConnectionLost, model="DG3450", transport="hnap")


# ---------------------------------------------------------------------------
# ActionFailed — bad response
# ---------------------------------------------------------------------------


def test_action_failed_on_invalid_json():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.side_effect = ValueError("no json")
    session = MagicMock()
    session.post.return_value = resp
    action = _make_action()
    with capture_events() as events:
        result = _call_execute(session, action)
    assert result.success is False
    assert_event_emitted(events, ActionFailed, model="DG3450", transport="hnap")
    event = next(e for e in events if isinstance(e, ActionFailed))
    assert event.level == EventLevel.WARNING


def test_action_failed_on_unexpected_result():
    session = _make_session(json_body={"RebootResponse": {"RebootResult": "ERROR"}})
    action = _make_action()
    with capture_events() as events:
        result = _call_execute(session, action)
    assert result.success is False
    assert_event_emitted(events, ActionFailed, model="DG3450", transport="hnap")
    event = next(e for e in events if isinstance(e, ActionFailed))
    assert "ERROR" in event.reason


# ---------------------------------------------------------------------------
# Pre-fetch — success path
# ---------------------------------------------------------------------------


def test_pre_fetch_completed_on_success():
    # Second post returns the main action response; first is the pre-fetch
    pre_fetch_resp = MagicMock()
    pre_fetch_resp.json.return_value = {"GetScheduleResponse": {"Schedule": "val", "Period": "60"}}
    main_resp = MagicMock()
    main_resp.status_code = 200
    main_resp.json.return_value = {"RebootResponse": {"RebootResult": "OK"}}
    session = MagicMock()
    session.post.side_effect = [pre_fetch_resp, main_resp]

    action = _make_action(pre_fetch_action="GetSchedule")
    with capture_events() as events:
        _call_execute(session, action)
    assert_event_emitted(events, ActionPreFetchCompleted, model="DG3450", transport="hnap")
    event = next(e for e in events if isinstance(e, ActionPreFetchCompleted))
    assert event.key_count == 2
    assert event.fallback_endpoint is None


# ---------------------------------------------------------------------------
# Pre-fetch — failure paths
# ---------------------------------------------------------------------------


def test_pre_fetch_failed_on_request_exception():
    pre_fetch_exc = requests.Timeout("timed out")
    main_resp = MagicMock()
    main_resp.status_code = 200
    main_resp.json.return_value = {"RebootResponse": {"RebootResult": "OK"}}
    session = MagicMock()
    session.post.side_effect = [pre_fetch_exc, main_resp]

    action = _make_action(pre_fetch_action="GetSchedule")
    with capture_events() as events:
        _call_execute(session, action)
    assert_event_emitted(events, ActionPreFetchFailed, model="DG3450", transport="hnap")
    event = next(e for e in events if isinstance(e, ActionPreFetchFailed))
    assert event.level == EventLevel.WARNING
    assert event.fallback_endpoint is None


def test_pre_fetch_failed_on_non_dict_response():
    pre_fetch_resp = MagicMock()
    pre_fetch_resp.json.return_value = ["not", "a", "dict"]
    main_resp = MagicMock()
    main_resp.status_code = 200
    main_resp.json.return_value = {"RebootResponse": {"RebootResult": "OK"}}
    session = MagicMock()
    session.post.side_effect = [pre_fetch_resp, main_resp]

    action = _make_action(pre_fetch_action="GetSchedule")
    with capture_events() as events:
        _call_execute(session, action)
    assert_event_emitted(events, ActionPreFetchFailed, model="DG3450", transport="hnap")
