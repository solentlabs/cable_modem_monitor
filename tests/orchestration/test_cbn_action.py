"""Tests for orchestration/actions/cbn_action.py event emission."""

from __future__ import annotations

from unittest.mock import MagicMock

import requests
from solentlabs.cable_modem_monitor_core.orchestration.events import (
    ActionCompleted,
    ActionConnectionLost,
    ActionFailed,
    ActionStarted,
    EventLevel,
)

from ..orchestration.event_capture import assert_event_emitted, capture_events


def _make_session(*, status_code: int = 200, raise_exc: Exception | None = None) -> MagicMock:
    session = MagicMock()
    session.cookies.get.return_value = "tok123"
    if raise_exc is not None:
        session.post.side_effect = raise_exc
    else:
        resp = MagicMock()
        resp.status_code = status_code
        resp.ok = status_code < 400
        session.post.return_value = resp
    return session


def _make_action(fun: int = 3) -> MagicMock:
    action = MagicMock()
    action.fun = fun
    return action


def _call_execute(session, action, *, log_level: int = 20, model: str = "CH7465LG"):
    from solentlabs.cable_modem_monitor_core.orchestration.actions.cbn_action import execute_cbn_action

    return execute_cbn_action(
        session,
        "http://192.168.100.1",
        action,
        setter_endpoint="/setter.xml",
        session_cookie_name="sessionToken",
        timeout=5,
        log_level=log_level,
        model=model,
    )


# ---------------------------------------------------------------------------
# ActionStarted
# ---------------------------------------------------------------------------


def test_action_started_emitted_on_success():
    session = _make_session(status_code=200)
    action = _make_action(fun=5)
    with capture_events() as events:
        _call_execute(session, action)
    assert_event_emitted(events, ActionStarted, model="CH7465LG", transport="cbn")
    event = next(e for e in events if isinstance(e, ActionStarted))
    assert "5" in event.action_name


def test_action_started_level_matches_log_level():
    session = _make_session(status_code=200)
    action = _make_action()
    with capture_events() as events:
        _call_execute(session, action, log_level=10)
    event = next(e for e in events if isinstance(e, ActionStarted))
    assert event.level == EventLevel.DEBUG


# ---------------------------------------------------------------------------
# ActionConnectionLost (expected restart path)
# ---------------------------------------------------------------------------


def test_connection_lost_emitted_on_connection_error():
    session = _make_session(raise_exc=requests.ConnectionError())
    action = _make_action(fun=3)
    with capture_events() as events:
        result = _call_execute(session, action)
    assert result.success is True
    assert_event_emitted(events, ActionConnectionLost, model="CH7465LG", transport="cbn")


def test_connection_lost_level_matches_log_level():
    session = _make_session(raise_exc=requests.ConnectionError())
    action = _make_action()
    with capture_events() as events:
        _call_execute(session, action, log_level=10)
    event = next(e for e in events if isinstance(e, ActionConnectionLost))
    assert event.level == EventLevel.DEBUG


# ---------------------------------------------------------------------------
# ActionFailed (request exception other than ConnectionError)
# ---------------------------------------------------------------------------


def test_action_failed_emitted_on_request_exception():
    exc = requests.Timeout("timed out")
    session = _make_session(raise_exc=exc)
    action = _make_action(fun=3)
    with capture_events() as events:
        result = _call_execute(session, action)
    assert result.success is False
    assert_event_emitted(events, ActionFailed, model="CH7465LG", transport="cbn")
    event = next(e for e in events if isinstance(e, ActionFailed))
    assert event.level == EventLevel.WARNING
    assert "timed out" in event.reason


# ---------------------------------------------------------------------------
# ActionCompleted (HTTP response received)
# ---------------------------------------------------------------------------


def test_action_completed_emitted_on_http_response():
    session = _make_session(status_code=200)
    action = _make_action(fun=5)
    with capture_events() as events:
        result = _call_execute(session, action)
    assert result.success is True
    assert_event_emitted(events, ActionCompleted, model="CH7465LG", transport="cbn")
    event = next(e for e in events if isinstance(e, ActionCompleted))
    assert event.status_code == 200


def test_action_completed_level_matches_log_level():
    session = _make_session(status_code=200)
    action = _make_action()
    with capture_events() as events:
        _call_execute(session, action, log_level=10)
    event = next(e for e in events if isinstance(e, ActionCompleted))
    assert event.level == EventLevel.DEBUG
