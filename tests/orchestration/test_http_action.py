"""Tests for orchestration/actions/http_action.py event emission."""

from __future__ import annotations

from unittest.mock import MagicMock

import requests
from solentlabs.cable_modem_monitor_core.orchestration.events import (
    ActionCompleted,
    ActionConnectionLost,
    ActionPreFetchCompleted,
    ActionPreFetchFailed,
    ActionStarted,
    EventLevel,
)

from ..orchestration.event_capture import assert_event_emitted, capture_events


def _make_action(
    *,
    method: str = "GET",
    endpoint: str = "/logout.cgi",
    endpoint_pattern: str = "",
    pre_fetch_url: str = "",
    params: dict | None = None,
    json_body: dict | None = None,
    headers: dict | None = None,
) -> MagicMock:
    action = MagicMock()
    action.method = method
    action.endpoint = endpoint
    action.endpoint_pattern = endpoint_pattern
    action.pre_fetch_url = pre_fetch_url
    action.params = params
    action.json_body = json_body
    action.headers = headers
    return action


def _make_session(
    *,
    status_code: int = 200,
    text: str = "",
    content: bytes = b"",
    raise_on_request: Exception | None = None,
    raise_on_get: Exception | None = None,
) -> MagicMock:
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = status_code < 400
    resp.text = text
    resp.content = content or text.encode()

    if raise_on_request is not None:
        session.request.side_effect = raise_on_request
    else:
        session.request.return_value = resp

    if raise_on_get is not None:
        session.get.side_effect = raise_on_get
    else:
        session.get.return_value = resp

    return session


def _call_execute(session, action, *, log_level: int = 20, model: str = "SBG6900AC"):
    from solentlabs.cable_modem_monitor_core.orchestration.actions.http_action import execute_http_action

    return execute_http_action(
        session,
        "http://192.168.100.1",
        action,
        timeout=5,
        log_level=log_level,
        model=model,
    )


# ---------------------------------------------------------------------------
# Main action — no pre-fetch
# ---------------------------------------------------------------------------


def test_action_started_emitted():
    action = _make_action()
    session = _make_session()
    with capture_events() as events:
        _call_execute(session, action)
    assert_event_emitted(events, ActionStarted, model="SBG6900AC", transport="http")


def test_action_completed_emitted():
    action = _make_action()
    session = _make_session(status_code=200)
    with capture_events() as events:
        _call_execute(session, action)
    assert_event_emitted(events, ActionCompleted, model="SBG6900AC", transport="http")
    event = next(e for e in events if isinstance(e, ActionCompleted))
    assert event.status_code == 200


def test_action_completed_level_matches_log_level():
    action = _make_action()
    session = _make_session()
    with capture_events() as events:
        _call_execute(session, action, log_level=10)
    event = next(e for e in events if isinstance(e, ActionCompleted))
    assert event.level == EventLevel.DEBUG


def test_action_connection_lost_emitted():
    action = _make_action()
    session = _make_session(raise_on_request=requests.ConnectionError())
    with capture_events() as events:
        result = _call_execute(session, action)
    assert result.success is True
    assert_event_emitted(events, ActionConnectionLost, model="SBG6900AC", transport="http")


def test_action_connection_lost_on_timeout():
    action = _make_action()
    session = _make_session(raise_on_request=requests.Timeout())
    with capture_events() as events:
        result = _call_execute(session, action)
    assert result.success is True
    assert_event_emitted(events, ActionConnectionLost, model="SBG6900AC", transport="http")


# ---------------------------------------------------------------------------
# Pre-fetch — extraction succeeds
# ---------------------------------------------------------------------------


def test_pre_fetch_completed_when_extraction_succeeds():
    html = '<form action="/cgi-bin/restart.cgi" method="post"><input/></form>'
    action = _make_action(
        endpoint_pattern="restart",
        pre_fetch_url="/setup.cgi",
        endpoint="",
    )
    session = _make_session(text=html)
    with capture_events() as events:
        _call_execute(session, action)
    assert_event_emitted(events, ActionPreFetchCompleted, model="SBG6900AC", transport="http")
    event = next(e for e in events if isinstance(e, ActionPreFetchCompleted))
    assert event.fallback_endpoint is None
    assert event.key_count is not None


# ---------------------------------------------------------------------------
# Pre-fetch — extraction fails, static fallback present
# ---------------------------------------------------------------------------


def test_pre_fetch_completed_with_fallback_when_extraction_fails():
    action = _make_action(
        endpoint_pattern="nope",
        pre_fetch_url="/setup.cgi",
        endpoint="/fallback.cgi",
    )
    session = _make_session(text="<html>no form action here</html>")
    with capture_events() as events:
        _call_execute(session, action)
    assert_event_emitted(events, ActionPreFetchCompleted, model="SBG6900AC", transport="http")
    event = next(e for e in events if isinstance(e, ActionPreFetchCompleted))
    assert event.fallback_endpoint == "/fallback.cgi"


# ---------------------------------------------------------------------------
# Pre-fetch — extraction fails, no fallback
# ---------------------------------------------------------------------------


def test_pre_fetch_failed_when_no_fallback():
    action = _make_action(
        endpoint_pattern="nope",
        pre_fetch_url="/setup.cgi",
        endpoint="",
    )
    session = _make_session(text="<html>no form action here</html>")
    with capture_events() as events:
        result = _call_execute(session, action)
    assert result.success is False
    assert_event_emitted(events, ActionPreFetchFailed, model="SBG6900AC", transport="http")
    event = next(e for e in events if isinstance(e, ActionPreFetchFailed))
    assert event.fallback_endpoint is None
    assert event.level == EventLevel.WARNING


# ---------------------------------------------------------------------------
# Pre-fetch — connection error during GET
# ---------------------------------------------------------------------------


def test_pre_fetch_failed_on_connection_error():
    action = _make_action(
        pre_fetch_url="/setup.cgi",
        endpoint="/fallback.cgi",
        endpoint_pattern="",
    )
    session = _make_session(raise_on_get=requests.ConnectionError())
    with capture_events() as events:
        _call_execute(session, action)
    assert_event_emitted(events, ActionPreFetchFailed, model="SBG6900AC", transport="http")
    event = next(e for e in events if isinstance(e, ActionPreFetchFailed))
    assert event.fallback_endpoint == "/fallback.cgi"
