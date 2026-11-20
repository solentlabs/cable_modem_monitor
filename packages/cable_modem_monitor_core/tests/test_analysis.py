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
    parse_core_logs,
    parse_diagnostics,
    parse_ts,
)
from solentlabs.cable_modem_monitor_core.analysis.log_parser import CORE_PATTERNS
from solentlabs.cable_modem_monitor_core.orchestration.events import (
    AuthFailed,
    AuthSucceeded,
    CollectionComplete,
    ConnectivityFailureDetected,
    EventLevel,
    HealthBackoffCleared,
    HealthStatusReport,
    RecoveryWindowClosed,
    RecoveryWindowOpened,
    StatusTransition,
)
from solentlabs.cable_modem_monitor_core.orchestration.logging import _format
from solentlabs.cable_modem_monitor_core.orchestration.models import (
    OrchestratorDiagnostics,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "analysis"

# A log formatter's prefix ahead of the message; patterns skip it with " .+".
_TS_PREFIX = "2025-04-01 10:00:01.123 INFO solentlabs.cable_modem_monitor_core — "

# ---------------------------------------------------------------------------
# CORE_PATTERNS — one line rendered by log_event() per pattern
# ---------------------------------------------------------------------------

# ┌─────────────────────┬───────────────────────────────────────────────┐
# │ pattern key         │ event rendered by _format()                   │
# ├─────────────────────┼───────────────────────────────────────────────┤
# │ auth_success        │ AuthSucceeded                                 │
# │ auth_fail           │ AuthFailed (connection error, no response)    │
# │ collection_complete │ CollectionComplete                            │
# │ health_*            │ HealthStatusReport, one per status            │
# │ status_transition   │ StatusTransition                              │
# │ connectivity_fail   │ ConnectivityFailureDetected                   │
# │ backoff_clear       │ HealthBackoffCleared                          │
# │ recovery_open/close │ RecoveryWindowOpened / RecoveryWindowClosed   │
# └─────────────────────┴───────────────────────────────────────────────┘
#
# fmt: off
RENDERED_CASES = [
    # (pattern key,         rendered message)
    ("auth_success",        _format(AuthSucceeded("T100", "form", 200, "", EventLevel.INFO))),
    ("auth_fail",           _format(AuthFailed("T100", "form", "ReadTimeout", None, None, None, None, None))),
    ("collection_complete", _format(CollectionComplete("T100", 24, 4, 2429.0, EventLevel.INFO))),
    ("health_responsive",   _format(HealthStatusReport("T100", "responsive", True, "ICMP 1.3ms, TCP 1.3ms"))),
    ("health_unresponsive", _format(HealthStatusReport("T100", "unresponsive", True, "ICMP timeout"))),
    ("health_degraded",     _format(HealthStatusReport("T100", "degraded", True, "ICMP 2.0ms, TCP timeout"))),
    ("status_transition",   _format(StatusTransition("T100", "online", "unreachable"))),
    ("connectivity_fail",   _format(ConnectivityFailureDetected("T100", 1, 1))),
    ("backoff_clear",       _format(HealthBackoffCleared("T100"))),
    ("recovery_open",       _format(RecoveryWindowOpened("T100", "connectivity_outage", 300.0))),
    ("recovery_close",      _format(RecoveryWindowClosed("T100", 210.0, "Operational"))),
]
# fmt: on

# ---------------------------------------------------------------------------
# Timestamps — with and without a UTC offset
# ---------------------------------------------------------------------------

# ┌───────────────┬───────────────────────────────┐
# │ id            │ stamp                         │
# ├───────────────┼───────────────────────────────┤
# │ minus_offset  │ 2025-04-01 10:00:01.123-04:00 │
# │ plus_offset   │ 2025-04-01 10:00:01.123+05:30 │
# │ no_offset     │ 2025-04-01 10:00:01.123       │
# └───────────────┴───────────────────────────────┘
#
# fmt: off
TIMESTAMP_CASES = [
    # (id,            stamp,                            expected local time)
    ("minus_offset",  "2025-04-01 10:00:01.123-04:00",  datetime(2025, 4, 1, 10, 0, 1, 123000)),
    ("plus_offset",   "2025-04-01 10:00:01.123+05:30",  datetime(2025, 4, 1, 10, 0, 1, 123000)),
    ("no_offset",     "2025-04-01 10:00:01.123",        datetime(2025, 4, 1, 10, 0, 1, 123000)),
]
# fmt: on

# ---------------------------------------------------------------------------
# parse_core_logs — table-driven over fixture files
# ---------------------------------------------------------------------------

# ┌──────────────────────┬───────┬────────┬─────────┬────────────┬─────────────┐
# │ fixture              │ polls │ health │ backoffs│ recoveries │ transitions │
# ├──────────────────────┼───────┼────────┼─────────┼────────────┼─────────────┤
# │ poll_success.txt     │ 2     │ 0      │ 0       │ 0          │ 0           │
# │ poll_failure.txt     │ 1     │ 0      │ 0       │ 0          │ 0           │
# │ health_responsive    │ 0     │ 3      │ 0       │ 0          │ 0           │
# │ health_mixed.txt     │ 0     │ 4      │ 0       │ 0          │ 0           │
# │ connectivity.txt     │ 0     │ 0      │ 2       │ 1          │ 1           │
# │ recovery_window.txt  │ 0     │ 0      │ 0       │ 2          │ 0           │
# │ empty.txt            │ 0     │ 0      │ 0       │ 0          │ 0           │
# └──────────────────────┴───────┴────────┴─────────┴────────────┴─────────────┘
#
# fmt: off
PARSE_CASES = [
    # (fixture,                polls, health, backoffs, recoveries, transitions)
    ("poll_success.txt",       2,     0,      0,        0,          0),
    ("poll_failure.txt",       1,     0,      0,        0,          0),
    ("health_responsive.txt",  0,     3,      0,        0,          0),
    ("health_mixed.txt",       0,     4,      0,        0,          0),
    ("connectivity.txt",       0,     0,      2,        1,          1),
    ("recovery_window.txt",    0,     0,      0,        2,          0),
    ("empty.txt",              0,     0,      0,        0,          0),
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
        lines = (FIXTURES_DIR / "poll_success.txt").read_text().splitlines()
        result = parse_core_logs(lines)
        poll = result.polls[0]

        assert poll.success is True
        assert poll.ds_channels == 32
        assert poll.us_channels == 8
        assert poll.model == "T100"
        assert poll.duration_s == pytest.approx(1.333)

    def test_failed_poll_defaults(self) -> None:
        lines = (FIXTURES_DIR / "poll_failure.txt").read_text().splitlines()
        result = parse_core_logs(lines)
        poll = result.polls[0]

        assert poll.success is False
        assert poll.ds_channels == 0
        assert poll.us_channels == 0


class TestHealthFields:
    """Verify field values on parsed health events."""

    def test_responsive_latencies(self) -> None:
        lines = (FIXTURES_DIR / "health_responsive.txt").read_text().splitlines()
        result = parse_core_logs(lines)
        h = result.health_checks[0]

        assert h.status == "responsive"
        assert h.icmp_ms == pytest.approx(1.2)
        assert h.tcp_ms == pytest.approx(45.6)

    def test_unresponsive_zero_latencies(self) -> None:
        lines = (FIXTURES_DIR / "health_mixed.txt").read_text().splitlines()
        result = parse_core_logs(lines)
        unresp = [h for h in result.health_checks if h.status == "unresponsive"]

        assert len(unresp) == 1
        assert unresp[0].icmp_ms == 0.0
        assert unresp[0].tcp_ms == 0.0

    def test_degraded_status(self) -> None:
        lines = (FIXTURES_DIR / "health_mixed.txt").read_text().splitlines()
        result = parse_core_logs(lines)
        degraded = [h for h in result.health_checks if h.status == "degraded"]

        assert len(degraded) == 1


class TestConnectivityFields:
    """Verify backoff, recovery, and transition field values."""

    def test_backoff_streak(self) -> None:
        lines = (FIXTURES_DIR / "connectivity.txt").read_text().splitlines()
        result = parse_core_logs(lines)

        assert result.backoffs[0].streak == 1
        assert result.backoffs[0].backoff == 1
        assert result.backoffs[1].streak == 2
        assert result.backoffs[1].backoff == 2

    def test_recovery_transition(self) -> None:
        lines = (FIXTURES_DIR / "connectivity.txt").read_text().splitlines()
        result = parse_core_logs(lines)

        assert result.recoveries[0].transition == "backoff_cleared"
        assert result.recoveries[0].model == "T100"

    def test_recovery_window_open_and_close(self) -> None:
        lines = (FIXTURES_DIR / "recovery_window.txt").read_text().splitlines()
        result = parse_core_logs(lines)

        assert [r.transition for r in result.recoveries] == [
            "recovery_window_open (connectivity_outage)",
            "recovery_window_closed (210s)",
        ]

    def test_status_transition_text(self) -> None:
        lines = (FIXTURES_DIR / "connectivity.txt").read_text().splitlines()
        result = parse_core_logs(lines)

        ts, desc = result.transitions[0]
        assert desc == "unreachable → online"
        assert isinstance(ts, datetime)


# ---------------------------------------------------------------------------
# CORE_PATTERNS vs the adapter that produces the lines
# ---------------------------------------------------------------------------


def test_every_pattern_has_a_rendered_case() -> None:
    """A pattern added without an adapter-rendered case would drift unseen."""
    assert {case[0] for case in RENDERED_CASES} == set(CORE_PATTERNS)


@pytest.mark.parametrize(("key", "message"), RENDERED_CASES, ids=[c[0] for c in RENDERED_CASES])
def test_pattern_matches_rendered_line(key: str, message: str) -> None:
    """Each pattern reads the line log_event() renders today."""
    match = CORE_PATTERNS[key].search(_TS_PREFIX + message)
    assert match is not None, f"{key} cannot read: {message}"
    assert match.group(1) == "2025-04-01 10:00:01.123"
    assert match.group(2) == "T100"


@pytest.mark.parametrize(("case_id", "stamp", "expected"), TIMESTAMP_CASES, ids=[c[0] for c in TIMESTAMP_CASES])
def test_timestamp_with_or_without_utc_offset(case_id: str, stamp: str, expected: datetime) -> None:
    """A UTC offset after the milliseconds is dropped; the local time is kept."""
    line = f"{stamp} INFO solentlabs.cable_modem_monitor_core — " + _format(
        CollectionComplete("T100", 24, 4, 100.0, EventLevel.INFO)
    )
    result = parse_core_logs([line])
    assert len(result.polls) == 1
    assert result.polls[0].timestamp == expected


class TestPatternsMatchAdapterOutput:
    """Field groups on auth_success, which no handler consumes."""

    @pytest.mark.parametrize(
        ("response_url", "expected_landed"),
        [("/status.html", "/status.html"), ("", None)],
    )
    def test_auth_success(self, response_url: str, expected_landed: str | None) -> None:
        line = _TS_PREFIX + _format(
            AuthSucceeded(
                model="T100",
                strategy="form",
                status_code=200,
                response_url=response_url,
                level=EventLevel.INFO,
            )
        )
        match = CORE_PATTERNS["auth_success"].search(line)
        assert match is not None
        assert match.group(2) == "T100"
        assert match.group(3) == "form"
        assert match.group(4) == "200"
        assert match.group(5) == expected_landed


# ---------------------------------------------------------------------------
# parse_ts
# ---------------------------------------------------------------------------


class TestParseTs:
    """Timestamp parsing."""

    def test_parses_millisecond_timestamp(self) -> None:
        result = parse_ts("2025-04-01 10:00:01.123")
        assert result == datetime(2025, 4, 1, 10, 0, 1, 123000)


# ---------------------------------------------------------------------------
# CoreAnalysis.outage_durations
# ---------------------------------------------------------------------------


class TestOutageDurations:
    """Outage window detection from health events."""

    def test_closed_outage(self) -> None:
        events = [
            HealthEvent(datetime(2025, 4, 1, 10, 0), "T100", "responsive"),
            HealthEvent(datetime(2025, 4, 1, 10, 1), "T100", "unresponsive"),
            HealthEvent(datetime(2025, 4, 1, 10, 3), "T100", "responsive"),
        ]
        durations = CoreAnalysis(health_checks=events).outage_durations()

        assert len(durations) == 1
        assert durations[0] == timedelta(minutes=2)

    def test_open_ended_outage_excluded(self) -> None:
        events = [
            HealthEvent(datetime(2025, 4, 1, 10, 0), "T100", "responsive"),
            HealthEvent(datetime(2025, 4, 1, 10, 1), "T100", "unresponsive"),
        ]
        durations = CoreAnalysis(health_checks=events).outage_durations()

        assert len(durations) == 0

    def test_empty_input(self) -> None:
        assert CoreAnalysis().outage_durations() == []

    def test_all_responsive(self) -> None:
        events = [
            HealthEvent(datetime(2025, 4, 1, 10, 0), "T100", "responsive"),
            HealthEvent(datetime(2025, 4, 1, 10, 1), "T100", "responsive"),
        ]
        assert CoreAnalysis(health_checks=events).outage_durations() == []

    def test_multiple_outages(self) -> None:
        events = [
            HealthEvent(datetime(2025, 4, 1, 10, 0), "T100", "unresponsive"),
            HealthEvent(datetime(2025, 4, 1, 10, 2), "T100", "responsive"),
            HealthEvent(datetime(2025, 4, 1, 10, 5), "T100", "unresponsive"),
            HealthEvent(datetime(2025, 4, 1, 10, 6), "T100", "responsive"),
        ]
        durations = CoreAnalysis(health_checks=events).outage_durations()

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
