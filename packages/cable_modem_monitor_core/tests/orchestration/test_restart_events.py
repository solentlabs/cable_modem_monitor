"""Tests for orchestration/restart.py event emission.

Verifies that run_restart() emits the correct typed events via log_event()
rather than calling _logger directly.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from solentlabs.cable_modem_monitor_core.orchestration.actions.base import ActionResult
from solentlabs.cable_modem_monitor_core.orchestration.events import (
    RestartCommandFailed,
    RestartCommandSent,
)
from solentlabs.cable_modem_monitor_core.orchestration.restart import (
    RestartNotSupportedError,
    run_restart,
)

from .event_capture import assert_event_emitted, capture_events


def _make_collector(auth_success: bool = True, auth_error: str = "") -> MagicMock:
    collector = MagicMock()
    auth_result = MagicMock()
    auth_result.success = auth_success
    auth_result.error = auth_error
    collector.authenticate.return_value = auth_result
    return collector


def _make_modem_config(model: str = "MB7621", has_restart: bool = True, has_action_auth: bool = False) -> MagicMock:
    config = MagicMock()
    config.model = model
    if has_restart:
        restart_action = MagicMock()
        restart_action.action_auth = MagicMock() if has_action_auth else None
        config.actions.restart = restart_action
    else:
        config.actions = None
    return config


def _make_recovery() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# RestartNotSupportedError
# ---------------------------------------------------------------------------


def test_no_restart_action_raises():
    collector = _make_collector()
    modem_config = _make_modem_config(has_restart=False)
    recovery = _make_recovery()
    with pytest.raises(RestartNotSupportedError):
        run_restart(collector, modem_config, recovery)


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_success_emits_restart_command_sent():
    collector = _make_collector(auth_success=True)
    modem_config = _make_modem_config(model="MB7621")
    recovery = _make_recovery()

    with (
        patch("solentlabs.cable_modem_monitor_core.orchestration.restart.execute_action"),
        capture_events() as events,
    ):
        result = run_restart(collector, modem_config, recovery)

    assert result.success is True
    assert_event_emitted(events, RestartCommandSent, model="MB7621")


def test_success_calls_recovery_begin():
    collector = _make_collector()
    modem_config = _make_modem_config()
    recovery = _make_recovery()

    with patch("solentlabs.cable_modem_monitor_core.orchestration.restart.execute_action"):
        run_restart(collector, modem_config, recovery)

    recovery.begin.assert_called_once_with("restart_command")


def test_success_clears_session():
    collector = _make_collector()
    modem_config = _make_modem_config()
    recovery = _make_recovery()

    with patch("solentlabs.cable_modem_monitor_core.orchestration.restart.execute_action"):
        run_restart(collector, modem_config, recovery)

    collector.clear_session.assert_called_once()


# ---------------------------------------------------------------------------
# Auth failure path
# ---------------------------------------------------------------------------


def test_auth_failure_emits_restart_command_failed():
    collector = _make_collector(auth_success=False, auth_error="401 Unauthorized")
    modem_config = _make_modem_config(model="MB7621")
    recovery = _make_recovery()

    with capture_events() as events:
        result = run_restart(collector, modem_config, recovery)

    assert result.success is False
    assert result.error == "command_failed"
    assert_event_emitted(events, RestartCommandFailed, model="MB7621")


def test_auth_failure_does_not_begin_recovery():
    collector = _make_collector(auth_success=False)
    modem_config = _make_modem_config()
    recovery = _make_recovery()

    run_restart(collector, modem_config, recovery)

    recovery.begin.assert_not_called()


# ---------------------------------------------------------------------------
# Exception path
# ---------------------------------------------------------------------------


def test_exception_emits_restart_command_failed():
    collector = _make_collector()
    modem_config = _make_modem_config(model="MB7621")
    recovery = _make_recovery()

    with (
        patch(
            "solentlabs.cable_modem_monitor_core.orchestration.restart.execute_action",
            side_effect=RuntimeError("connection reset"),
        ),
        capture_events() as events,
    ):
        result = run_restart(collector, modem_config, recovery)

    assert result.success is False
    assert_event_emitted(events, RestartCommandFailed, model="MB7621")


# ---------------------------------------------------------------------------
# Refused action — session age reported
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("has_action_auth", "collector_age", "expected_age"),
    [
        (False, 18342.5, 18342.5),
        (False, 2.0, 2.0),
        (True, 18342.5, None),
    ],
    ids=["aged_monitoring_session", "fresh_monitoring_session", "action_auth_session_not_used"],
)
def test_refused_action_reports_session_age(has_action_auth: bool, collector_age: float, expected_age: float | None):
    # A refusal on a long-held session reads differently from one on a fresh login (#218)
    collector = _make_collector()
    collector.session_age_seconds = collector_age
    modem_config = _make_modem_config(model="MB8611")
    recovery = _make_recovery()

    with (
        patch(
            "solentlabs.cable_modem_monitor_core.orchestration.restart._has_action_auth",
            return_value=has_action_auth,
        ),
        patch(
            "solentlabs.cable_modem_monitor_core.orchestration.restart.execute_action",
            return_value=ActionResult(success=False, message="Unexpected result: UN-AUTH"),
        ),
        capture_events() as events,
    ):
        result = run_restart(collector, modem_config, recovery)

    assert result.success is False
    event = next(e for e in events if isinstance(e, RestartCommandFailed))
    assert event.reason == "Unexpected result: UN-AUTH"
    assert event.session_age_seconds == expected_age


# ---------------------------------------------------------------------------
# action_auth path — monitoring session skipped
# ---------------------------------------------------------------------------


def test_action_auth_skips_monitoring_authenticate():
    collector = _make_collector()
    modem_config = _make_modem_config()
    recovery = _make_recovery()

    with (
        patch(
            "solentlabs.cable_modem_monitor_core.orchestration.restart._has_action_auth",
            return_value=True,
        ),
        patch("solentlabs.cable_modem_monitor_core.orchestration.restart.execute_action"),
    ):
        run_restart(collector, modem_config, recovery)

    collector.authenticate.assert_not_called()
