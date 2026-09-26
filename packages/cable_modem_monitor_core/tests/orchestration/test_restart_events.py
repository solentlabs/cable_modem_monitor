"""Tests for orchestration/restart.py event emission.

Verifies that run_restart() emits the correct typed events via log_event()
rather than calling _logger directly.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
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
