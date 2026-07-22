"""Tests for orchestrator.py event emission."""

from __future__ import annotations

from unittest.mock import MagicMock

from solentlabs.cable_modem_monitor_core.orchestration.events import (
    ConnectivityBackoffReset,
    EventLevel,
)
from solentlabs.cable_modem_monitor_core.orchestration.orchestrator import Orchestrator

from .event_capture import assert_event_emitted, capture_events


def _make_orchestrator(model: str = "SB8200") -> Orchestrator:
    collector = MagicMock()
    collector.session_is_valid = True
    collector.last_resource_fetches = []
    collector.last_stub_bodies = {}
    collector._username = "admin"
    collector._password = "password"
    collector._base_url = "http://192.168.100.1"

    modem_config = MagicMock()
    modem_config.model = model
    modem_config.auth = None
    modem_config.actions = None

    return Orchestrator(collector, health_monitor=None, modem_config=modem_config)


# ---------------------------------------------------------------------------
# ConnectivityBackoffReset
# ---------------------------------------------------------------------------


def test_connectivity_backoff_reset_emitted_when_backoff_active():
    orch = _make_orchestrator(model="SBG6900AC")
    # Force a non-zero connectivity streak so was_backing_off is True
    orch._policy._connectivity_streak = 2
    orch._policy._connectivity_backoff = 1
    with capture_events() as events:
        orch.reset_connectivity()
    assert_event_emitted(events, ConnectivityBackoffReset, model="SBG6900AC")
    event = next(e for e in events if isinstance(e, ConnectivityBackoffReset))
    assert event.level == EventLevel.INFO


def test_connectivity_backoff_reset_not_emitted_when_no_backoff():
    orch = _make_orchestrator()
    # No active backoff
    with capture_events() as events:
        orch.reset_connectivity()
    assert not any(isinstance(e, ConnectivityBackoffReset) for e in events)
