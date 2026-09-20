"""Tests for orchestration/modem_health.py event emission."""

from __future__ import annotations

from solentlabs.cable_modem_monitor_core.orchestration.events import (
    EventLevel,
    HealthStatusReport,
)
from solentlabs.cable_modem_monitor_core.orchestration.models import HealthInfo
from solentlabs.cable_modem_monitor_core.orchestration.modem_health import HealthMonitor
from solentlabs.cable_modem_monitor_core.orchestration.signals import HealthStatus

from .event_capture import assert_event_emitted, capture_events


def _make_monitor(model: str = "SB8200") -> HealthMonitor:
    return HealthMonitor(
        "http://192.168.100.1",
        model=model,
        supports_icmp=False,
        http_probe=False,
    )


def _call_log_result(monitor: HealthMonitor, health_status: HealthStatus) -> list:
    info = HealthInfo(health_status=health_status)
    with capture_events() as events:
        monitor._log_result(info, icmp_ok=None, tcp_ok=None, http_ok=None)
    return events


# ---------------------------------------------------------------------------
# HealthStatusReport — level computed from status + changed
# ---------------------------------------------------------------------------


def test_degraded_transition_emits_warning():
    monitor = _make_monitor()
    events = _call_log_result(monitor, HealthStatus.DEGRADED)
    assert_event_emitted(events, HealthStatusReport, model="SB8200")
    event = next(e for e in events if isinstance(e, HealthStatusReport))
    assert event.level == EventLevel.WARNING
    assert event.changed is True


def test_unresponsive_transition_emits_warning():
    monitor = _make_monitor()
    events = _call_log_result(monitor, HealthStatus.UNRESPONSIVE)
    event = next(e for e in events if isinstance(e, HealthStatusReport))
    assert event.level == EventLevel.WARNING


def test_other_status_change_emits_info():
    monitor = _make_monitor()
    # First call transitions from UNKNOWN → RESPONSIVE (INFO).
    events = _call_log_result(monitor, HealthStatus.RESPONSIVE)
    event = next(e for e in events if isinstance(e, HealthStatusReport))
    assert event.level == EventLevel.INFO
    assert event.changed is True


def test_steady_state_emits_debug():
    monitor = _make_monitor()
    # First call establishes RESPONSIVE.
    _call_log_result(monitor, HealthStatus.RESPONSIVE)
    # Second call — same status, no change.
    events = _call_log_result(monitor, HealthStatus.RESPONSIVE)
    event = next(e for e in events if isinstance(e, HealthStatusReport))
    assert event.level == EventLevel.DEBUG
    assert event.changed is False


def test_health_status_report_model_field():
    monitor = _make_monitor(model="HUB5")
    events = _call_log_result(monitor, HealthStatus.RESPONSIVE)
    assert_event_emitted(events, HealthStatusReport, model="HUB5")


def test_health_status_report_status_field():
    monitor = _make_monitor()
    events = _call_log_result(monitor, HealthStatus.RESPONSIVE)
    event = next(e for e in events if isinstance(e, HealthStatusReport))
    assert event.status == HealthStatus.RESPONSIVE.value
