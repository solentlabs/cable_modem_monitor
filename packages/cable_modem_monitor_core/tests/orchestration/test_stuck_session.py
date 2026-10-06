"""A reused session that keeps failing while the modem answers probes is dropped.

ORCHESTRATION_SPEC § Signal → Policy Mapping ("A reachable modem whose
reused session keeps failing"), UC-21b. A failed collection counts when
it was on a reused session and a fresh health probe afterwards reads the
data path up. ``SESSION_STUCK_THRESHOLD`` such failures in a row drop the
session (best-effort logout, then clear). Every failure is judged once.

TEST DATA TABLES
================
``SCENARIOS``: one row per poll sequence, each poll (probe state at its
start, collection result, whether the session was reused), and the number
of times the session was cleared.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
from solentlabs.cable_modem_monitor_core.orchestration.models import HealthInfo, ModemResult
from solentlabs.cable_modem_monitor_core.orchestration.orchestrator import Orchestrator
from solentlabs.cable_modem_monitor_core.orchestration.signals import CollectorSignal, HealthStatus

_UP = "up"  # a probe taken after the failure reads the data path up
_DOWN = "down"  # a probe taken after the failure reads it down
_STALE = "stale"  # the latest probe pre-dates the failure

_FAIL = "fail"
_OK = "ok"

# fmt: off
SCENARIOS = [
    # (id, [(probe, result, reused), ...], clears)
    ("three reachable failures drop the session",
     [(_UP, _FAIL, True)] * 4, 1),
    ("two are not enough",
     [(_UP, _FAIL, True)] * 3, 0),
    ("a success resets the count",
     [(_UP, _FAIL, True), (_UP, _FAIL, True), (_UP, _OK, True),
      (_UP, _FAIL, True), (_UP, _FAIL, True), (_UP, _FAIL, True)], 0),
    ("failures on a fresh session never count",
     [(_UP, _FAIL, False)] * 6, 0),
    ("a probe reading down resets the count",
     [(_UP, _FAIL, True), (_UP, _FAIL, True), (_DOWN, _FAIL, True),
      (_UP, _FAIL, True), (_UP, _FAIL, True)], 0),
    ("three more reachable failures after a down probe still drop it",
     [(_UP, _FAIL, True), (_UP, _FAIL, True), (_DOWN, _FAIL, True),
      (_UP, _FAIL, True), (_UP, _FAIL, True), (_UP, _FAIL, True)], 1),
    ("a stale probe counts nothing",
     [(_STALE, _FAIL, True)] * 8, 0),
    ("the count restarts after a drop",
     [(_UP, _FAIL, True)] * 7, 2),
]
# fmt: on


def _result(kind: str) -> ModemResult:
    if kind == _OK:
        return ModemResult(success=True, modem_data={"downstream": [], "upstream": [], "system_info": {}})
    return ModemResult(success=False, signal=CollectorSignal.CONNECTIVITY, error="connection dropped")


def _config() -> MagicMock:
    config = MagicMock()
    config.timeout = 10
    config.model = "T100"
    config.actions = None
    return config


def _probe(monitor: MagicMock, state: str) -> None:
    reads_up = state != _DOWN
    monitor.latest = HealthInfo(health_status=HealthStatus.RESPONSIVE if reads_up else HealthStatus.UNRESPONSIVE)
    # A fresh probe post-dates every failure; a stale one pre-dates them.
    monitor.latest_probe_at = float("inf") if state != _STALE else 0.0


def _drive(
    polls: list[tuple[str, str, bool]], *, monitor: bool = True
) -> tuple[MagicMock, MagicMock | None, Orchestrator]:
    collector = MagicMock()
    collector.session_is_valid = True
    health = MagicMock() if monitor else None
    orchestrator = Orchestrator(collector=collector, health_monitor=health, modem_config=_config())
    for probe, result, reused in polls:
        collector.session_reused = reused
        collector.execute.side_effect = lambda kind=result: _result(kind)
        if health is not None:
            _probe(health, probe)
        orchestrator.get_modem_data()
    return collector, health, orchestrator


@pytest.mark.parametrize(("case_id", "polls", "clears"), SCENARIOS, ids=[c[0] for c in SCENARIOS])
def test_stuck_session_is_dropped_only_after_repeated_reachable_failures(
    case_id: str, polls: list[tuple[str, str, bool]], clears: int
) -> None:
    collector, _, _ = _drive(polls)
    assert collector.clear_session.call_count == clears
    assert collector.attempt_logout_before_retry.call_count == clears


def test_no_health_monitor_never_counts() -> None:
    """Without a monitor nothing says the modem is reachable, so nothing is counted."""
    collector, _, _ = _drive([(_UP, _FAIL, True)] * 10, monitor=False)
    collector.clear_session.assert_not_called()


def test_the_drop_logs_one_line(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        _drive([(_UP, _FAIL, True)] * 4)
    assert caplog.text.count("Reused session dropped [T100]") == 1
    assert "3 connection failures" in caplog.text


def test_logout_comes_before_the_clear() -> None:
    """The best-effort logout releases a single-session modem's slot before the local clear."""
    collector, _, _ = _drive([(_UP, _FAIL, True)] * 4)
    names = [call[0] for call in collector.method_calls if call[0] in ("attempt_logout_before_retry", "clear_session")]
    assert names == ["attempt_logout_before_retry", "clear_session"]
