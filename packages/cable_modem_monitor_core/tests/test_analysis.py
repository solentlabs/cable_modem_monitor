"""Tests for the Core analysis module.

Fixture-driven tests for log parsing, inline tests for diagnostics
and computed properties.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.analysis import (
    CoreAnalysis,
    HealthEvent,
    compute_outage_durations,
    parse_core_logs,
    parse_diagnostics,
    parse_ts,
)
from solentlabs.cable_modem_monitor_core.orchestration.models import (
    OrchestratorDiagnostics,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "analysis"

# ---------------------------------------------------------------------------
# parse_core_logs — table-driven over fixture files
# ---------------------------------------------------------------------------

# ┌──────────────────────┬───────┬────────┬─────────┬────────────┬─────────────┐
# │ fixture              │ polls │ health │ backoffs│ recoveries │ transitions │
# ├──────────────────────┼───────┼────────┼─────────┼────────────┼─────────────┤
# │ poll_success.log     │ 2     │ 0      │ 0       │ 0          │ 0           │
# │ poll_failure.log     │ 1     │ 0      │ 0       │ 0          │ 0           │
# │ health_responsive    │ 0     │ 3      │ 0       │ 0          │ 0           │
# │ health_mixed.log     │ 0     │ 4      │ 0       │ 0          │ 0           │
# │ connectivity.log     │ 0     │ 0      │ 2       │ 1          │ 1           │
# │ empty.log            │ 0     │ 0      │ 0       │ 0          │ 0           │
# └──────────────────────┴───────┴────────┴─────────┴────────────┴─────────────┘
#
# fmt: off
PARSE_CASES = [
    # (fixture,                polls, health, backoffs, recoveries, transitions)
    ("poll_success.log",       2,     0,      0,        0,          0),
    ("poll_failure.log",       1,     0,      0,        0,          0),
    ("health_responsive.log",  0,     3,      0,        0,          0),
    ("health_mixed.log",       0,     4,      0,        0,          0),
    ("connectivity.log",       0,     0,      2,        1,          1),
    ("empty.log",              0,     0,      0,        0,          0),
]
# fmt: on


@pytest.mark.parametrize(
    "fixture,exp_polls,exp_health,exp_backoffs,exp_recoveries,exp_transitions",
    PARSE_CASES,
    ids=[c[0] for c in PARSE_CASES],
)
def test_parse_core_logs_counts(
    fixture: str,
    exp_polls: int,
    exp_health: int,
    exp_backoffs: int,
    exp_recoveries: int,
    exp_transitions: int,
) -> None:
    """Each fixture produces the expected event counts."""
    lines = (FIXTURES_DIR / fixture).read_text().splitlines()
    result = parse_core_logs(lines)

    assert len(result.polls) == exp_polls
    assert len(result.health_checks) == exp_health
    assert len(result.backoffs) == exp_backoffs
    assert len(result.recoveries) == exp_recoveries
    assert len(result.transitions) == exp_transitions


# ---------------------------------------------------------------------------
# parse_core_logs — behavioral tests (inline, field-level checks)
# ---------------------------------------------------------------------------


class TestPollFields:
    """Verify field values on parsed poll events."""

    def test_successful_poll_channels(self) -> None:
        lines = (FIXTURES_DIR / "poll_success.log").read_text().splitlines()
        result = parse_core_logs(lines)
        poll = result.polls[0]

        assert poll.success is True
        assert poll.ds_channels == 32
        assert poll.us_channels == 8
        assert poll.model == "T100"
        assert poll.duration_s == 0.0

    def test_failed_poll_defaults(self) -> None:
        lines = (FIXTURES_DIR / "poll_failure.log").read_text().splitlines()
        result = parse_core_logs(lines)
        poll = result.polls[0]

        assert poll.success is False
        assert poll.ds_channels == 0
        assert poll.us_channels == 0


class TestHealthFields:
    """Verify field values on parsed health events."""

    def test_responsive_latencies(self) -> None:
        lines = (FIXTURES_DIR / "health_responsive.log").read_text().splitlines()
        result = parse_core_logs(lines)
        h = result.health_checks[0]

        assert h.status == "responsive"
        assert h.icmp_ms == pytest.approx(1.2)
        assert h.http_ms == pytest.approx(45.6)

    def test_unresponsive_zero_latencies(self) -> None:
        lines = (FIXTURES_DIR / "health_mixed.log").read_text().splitlines()
        result = parse_core_logs(lines)
        unresp = [h for h in result.health_checks if h.status == "unresponsive"]

        assert len(unresp) == 1
        assert unresp[0].icmp_ms == 0.0
        assert unresp[0].http_ms == 0.0

    def test_degraded_status(self) -> None:
        lines = (FIXTURES_DIR / "health_mixed.log").read_text().splitlines()
        result = parse_core_logs(lines)
        degraded = [h for h in result.health_checks if h.status == "degraded"]

        assert len(degraded) == 1


class TestConnectivityFields:
    """Verify backoff, recovery, and transition field values."""

    def test_backoff_streak(self) -> None:
        lines = (FIXTURES_DIR / "connectivity.log").read_text().splitlines()
        result = parse_core_logs(lines)

        assert result.backoffs[0].streak == 1
        assert result.backoffs[0].backoff == 1
        assert result.backoffs[1].streak == 2
        assert result.backoffs[1].backoff == 2

    def test_recovery_transition(self) -> None:
        lines = (FIXTURES_DIR / "connectivity.log").read_text().splitlines()
        result = parse_core_logs(lines)

        assert result.recoveries[0].transition == "backoff_cleared"
        assert result.recoveries[0].model == "T100"

    def test_status_transition_text(self) -> None:
        lines = (FIXTURES_DIR / "connectivity.log").read_text().splitlines()
        result = parse_core_logs(lines)

        ts, desc = result.transitions[0]
        assert desc == "offline -> online"
        assert isinstance(ts, datetime)


# ---------------------------------------------------------------------------
# parse_ts
# ---------------------------------------------------------------------------


class TestParseTs:
    """Timestamp parsing."""

    def test_parses_millisecond_timestamp(self) -> None:
        result = parse_ts("2025-04-01 10:00:01.123")
        assert result == datetime(2025, 4, 1, 10, 0, 1, 123000)


# ---------------------------------------------------------------------------
# compute_outage_durations
# ---------------------------------------------------------------------------


class TestOutageDurations:
    """Outage window detection from health events."""

    def test_closed_outage(self) -> None:
        events = [
            HealthEvent(datetime(2025, 4, 1, 10, 0), "T100", "responsive"),
            HealthEvent(datetime(2025, 4, 1, 10, 1), "T100", "unresponsive"),
            HealthEvent(datetime(2025, 4, 1, 10, 3), "T100", "responsive"),
        ]
        durations = compute_outage_durations(events)

        assert len(durations) == 1
        assert durations[0] == timedelta(minutes=2)

    def test_open_ended_outage_excluded(self) -> None:
        events = [
            HealthEvent(datetime(2025, 4, 1, 10, 0), "T100", "responsive"),
            HealthEvent(datetime(2025, 4, 1, 10, 1), "T100", "unresponsive"),
        ]
        durations = compute_outage_durations(events)

        assert len(durations) == 0

    def test_empty_input(self) -> None:
        assert compute_outage_durations([]) == []

    def test_all_responsive(self) -> None:
        events = [
            HealthEvent(datetime(2025, 4, 1, 10, 0), "T100", "responsive"),
            HealthEvent(datetime(2025, 4, 1, 10, 1), "T100", "responsive"),
        ]
        assert compute_outage_durations(events) == []

    def test_multiple_outages(self) -> None:
        events = [
            HealthEvent(datetime(2025, 4, 1, 10, 0), "T100", "unresponsive"),
            HealthEvent(datetime(2025, 4, 1, 10, 2), "T100", "responsive"),
            HealthEvent(datetime(2025, 4, 1, 10, 5), "T100", "unresponsive"),
            HealthEvent(datetime(2025, 4, 1, 10, 6), "T100", "responsive"),
        ]
        durations = compute_outage_durations(events)

        assert len(durations) == 2
        assert durations[0] == timedelta(minutes=2)
        assert durations[1] == timedelta(minutes=1)


# ---------------------------------------------------------------------------
# parse_diagnostics
# ---------------------------------------------------------------------------


class TestParseDiagnostics:
    """Diagnostics-to-CoreAnalysis bridge."""

    def test_healthy_diagnostics_empty(self) -> None:
        diag = OrchestratorDiagnostics(
            poll_duration=1.5,
            auth_failure_streak=0,
            circuit_breaker_open=False,
            session_is_valid=True,
            connectivity_streak=0,
            connectivity_backoff_remaining=0,
        )
        result = parse_diagnostics(diag)

        assert isinstance(result, CoreAnalysis)
        assert result.backoffs == []
        assert result.polls == []

    def test_connectivity_backoff_produces_event(self) -> None:
        diag = OrchestratorDiagnostics(
            poll_duration=None,
            auth_failure_streak=0,
            circuit_breaker_open=False,
            session_is_valid=False,
            connectivity_streak=3,
            connectivity_backoff_remaining=2,
        )
        result = parse_diagnostics(diag)

        assert len(result.backoffs) == 1
        assert result.backoffs[0].streak == 3
        assert result.backoffs[0].backoff == 2
