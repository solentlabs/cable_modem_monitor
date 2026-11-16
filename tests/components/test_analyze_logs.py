"""Tests for the HA log analysis script.

Fixture-driven tests for parse_ha_logs, inline tests for report
formatting and enrichment behaviour.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from custom_components.cable_modem_monitor import _log_operational_summary
from scripts.dev.analyze_logs import (
    HAAnalysis,
    format_report,
    parse_ha_logs,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "analysis"

# ---------------------------------------------------------------------------
# Intervals — rendered by _log_operational_summary, read back in seconds
# ---------------------------------------------------------------------------

# ┌─────────────────┬────────┬──────────┬──────────────────────────────────┐
# │ id              │ scan_s │ health_s │ rendered                         │
# ├─────────────────┼────────┼──────────┼──────────────────────────────────┤
# │ 5m_30s          │ 300    │ 30       │ every 5m, every 30s              │
# │ 10m30s_1m30s    │ 630    │ 90       │ every 10m 30s, every 1m 30s      │
# │ 1h_1m           │ 3600   │ 60       │ every 1h, every 1m               │
# │ manual_disabled │ 0      │ 0        │ manual only, disabled            │
# └─────────────────┴────────┴──────────┴──────────────────────────────────┘
#
# fmt: off
INTERVAL_CASES = [
    # (id,               scan_s, health_s)
    ("5m_30s",           300,    30),
    ("10m30s_1m30s",     630,    90),
    ("1h_1m",            3600,   60),
    ("manual_disabled",  0,      0),
]
# fmt: on

# The line prefix HA's log formatter writes ahead of the message: time, level, logger.
_HA_PREFIX = "2025-04-01 {}.000-04:00 {} (SyncWorker_5) [{}] "
_CORE = "solentlabs.cable_modem_monitor_core.orchestration"
_INTEGRATION = "custom_components.cable_modem_monitor"

# One poll that succeeds and one that fails later, as an INFO log shows them:
# successful polls after the first log at DEBUG, so they are absent.
_INFO_ONLY_LINES = [
    _HA_PREFIX.format("10:00:00", "INFO", _CORE) + "Collection complete [T100] — DS: 24, US: 4 (2429ms)",
    _HA_PREFIX.format("11:14:00", "WARNING", _CORE)
    + "Connection failed during auth [T100] strategy=form — ReadTimeout",
]
_DEBUG_POLL_LINE = _HA_PREFIX.format("10:10:00", "DEBUG", _CORE) + "Collection complete [T100] — DS: 24, US: 4 (1800ms)"

# ---------------------------------------------------------------------------
# parse_ha_logs — table-driven fixture tests
# ---------------------------------------------------------------------------

# ┌────────────────────────┬───────┬────────┬─────────┬──────────┬──────────────┐
# │ fixture                │ polls │ health │ backoffs│ ha_recov │ model        │
# ├────────────────────────┼───────┼────────┼─────────┼──────────┼──────────────┤
# │ ha_full_session.txt    │ 2     │ 1      │ 0       │ 0        │ Acme T100    │
# │ ha_recovery_session    │ 1     │ 4      │ 1       │ 1        │ Acme T100    │
# └────────────────────────┴───────┴────────┴─────────┴──────────┴──────────────┘
#
# fmt: off
PARSE_CASES = [
    # (fixture,                     polls, health, backoffs, ha_recoveries, model)
    ("ha_full_session.txt",         2,     1,      0,        0,             "Acme T100"),
    ("ha_recovery_session.txt",     1,     4,      1,        1,             "Acme T100"),
]
# fmt: on


@pytest.mark.parametrize(
    "fixture,exp_polls,exp_health,exp_backoffs,exp_ha_recoveries,exp_model",
    PARSE_CASES,
    ids=[c[0] for c in PARSE_CASES],
)
def test_parse_ha_logs_counts(
    fixture: str,
    exp_polls: int,
    exp_health: int,
    exp_backoffs: int,
    exp_ha_recoveries: int,
    exp_model: str,
) -> None:
    """Each fixture produces expected event counts and metadata."""
    lines = (FIXTURES_DIR / fixture).read_text().splitlines()
    result = parse_ha_logs(lines)

    assert len(result.core.polls) == exp_polls
    assert len(result.core.health_checks) == exp_health
    assert len(result.core.backoffs) == exp_backoffs
    assert len(result.ha_recoveries) == exp_ha_recoveries
    assert result.model == exp_model


# ---------------------------------------------------------------------------
# HA metadata — inline behavioral tests
# ---------------------------------------------------------------------------


class TestHAMetadata:
    """HA lifecycle fields parsed from startup/config lines."""

    def test_startup_fields(self) -> None:
        lines = (FIXTURES_DIR / "ha_full_session.txt").read_text().splitlines()
        result = parse_ha_logs(lines)

        assert result.version == "v3.14.0-alpha.9"
        assert result.model == "Acme T100"
        assert result.poll_interval_s == 300
        assert result.health_interval_s == 30

    def test_compound_intervals(self) -> None:
        lines = (FIXTURES_DIR / "ha_recovery_session.txt").read_text().splitlines()
        result = parse_ha_logs(lines)

        assert result.poll_interval_s == 630
        assert result.health_interval_s == 90

    def test_first_poll_no_data(self) -> None:
        lines = (FIXTURES_DIR / "ha_full_session.txt").read_text().splitlines()
        result = parse_ha_logs(lines)

        assert result.first_poll_no_data is True

    def test_deferred_entity_count(self) -> None:
        lines = (FIXTURES_DIR / "ha_full_session.txt").read_text().splitlines()
        result = parse_ha_logs(lines)

        assert result.deferred_entity_count == 24


@pytest.mark.parametrize(("case_id", "scan", "health"), INTERVAL_CASES, ids=[c[0] for c in INTERVAL_CASES])
def test_intervals_read_from_the_summary_line_ha_emits(
    case_id: str, scan: int, health: int, caplog: pytest.LogCaptureFixture
) -> None:
    """The Initialized pattern reads what _log_operational_summary writes, not a hand-typed copy."""
    with caplog.at_level(logging.INFO, logger="custom_components.cable_modem_monitor"):
        _log_operational_summary(scan, health, "T100")

    line = f"2025-04-01 10:00:00.400-04:00 INFO (MainThread) [x] {caplog.records[0].getMessage()}"
    result = parse_ha_logs([line])

    assert result.poll_interval_s == scan
    assert result.health_interval_s == health


@pytest.mark.parametrize("suffix", ["", " (local dev)"], ids=["release", "local_dev"])
def test_startup_line_with_or_without_local_dev_marker(suffix: str) -> None:
    """async_setup_entry appends _local_dev_suffix() to the version."""
    line = (
        "2025-04-01 10:00:00.100-04:00 INFO (MainThread) [custom_components.cable_modem_monitor] "
        f"Cable Modem Monitor v3.14.15-beta.8{suffix} starting [Acme T100] — core: v3.14.15-beta.8"
    )
    result = parse_ha_logs([line])

    assert result.version == "v3.14.15-beta.8"
    assert result.model == "Acme T100"


def test_skipped_tcp_probe_is_not_a_zero_latency() -> None:
    """A check that skipped TCP (collection active) has no TCP sample to average."""
    prefix = "2025-04-01 10:00:{}.000-04:00 DEBUG (SyncWorker_3) [solentlabs.cable_modem_monitor_core.modem_health] "
    details = ["ICMP 1.0ms, TCP 40.0ms", "ICMP 1.0ms, TCP 50.0ms", "ICMP 1.0ms, TCP/HEAD skipped (collection active)"]
    lines = [prefix.format(f"{i:02d}") + f"Health check [T100]: responsive — {d}" for i, d in enumerate(details)]
    report = format_report(parse_ha_logs(lines))

    assert "TCP (avg):  45.0ms" in report
    assert "spike" not in report


class TestVerdict:
    """The verdict never calls a log clean when it read nothing, or misnames a late failure."""

    def test_no_recognized_events_is_not_clean(self) -> None:
        lines = ["2025-04-01 10:00:00.000-04:00 INFO (MainThread) [custom_components.cable_modem_monitor] unrecognized"]
        report = format_report(parse_ha_logs(lines))

        assert "CLEAN" not in report
        assert "NO DATA" in report

    def test_failure_after_a_successful_first_poll_is_not_cold_start(self) -> None:
        report = format_report(parse_ha_logs(_INFO_ONLY_LINES))

        assert "cold start" not in report
        assert "1 poll failure(s) logged" in report


class TestLogLevel:
    """Rates need every poll; an INFO log holds only the first success and the failures."""

    def test_info_log_reports_counts_not_rates(self) -> None:
        report = format_report(parse_ha_logs(_INFO_ONLY_LINES))

        assert "Success rate" not in report
        assert "1 poll failure(s) logged" in report
        assert "INFO log" in report

    def test_debug_from_the_integration_alone_is_still_an_info_log(self) -> None:
        # Polls and health checks are Core's lines; integration DEBUG does not reveal them.
        ha_debug = _HA_PREFIX.format("10:05:00", "DEBUG", _INTEGRATION) + "x"
        report = format_report(parse_ha_logs([*_INFO_ONLY_LINES, ha_debug]))

        assert "Success rate" not in report
        assert "INFO log" in report

    def test_debug_log_reports_rates(self) -> None:
        report = format_report(parse_ha_logs([*_INFO_ONLY_LINES, _DEBUG_POLL_LINE]))

        assert "Success rate:    66.7%" in report
        assert "1 poll failure(s) (33.3%)" in report
        assert "INFO log" not in report


def test_failed_poll_without_a_measured_duration_shows_none() -> None:
    """A failed poll has a duration only from HA's DEBUG fetch line; 0.0s would read as measured."""
    report = format_report(parse_ha_logs(_INFO_ONLY_LINES))

    assert "    11:14:00\n" in report
    assert "0.0s" not in report


def test_period_ends_at_the_last_integration_line_not_the_last_poll() -> None:
    """The window closes after the last poll; the reported period must include it."""
    lines = [
        _HA_PREFIX.format("10:00:00", "INFO", _INTEGRATION)
        + "Cable Modem Monitor v3.14.15-beta.8 starting [Acme T100]",
        _HA_PREFIX.format("10:01:00", "INFO", _CORE) + "Collection complete [T100] — DS: 24, US: 4 (2429ms)",
        _HA_PREFIX.format("10:30:00", "INFO", _CORE)
        + "Recovery window closed [T100] — elapsed: 210s, last snapshot docsis: x",
    ]
    report = format_report(parse_ha_logs(lines))

    assert "Duration: 30m 0s" in report


class TestPollDurationEnrichment:
    """fetch_complete lines enrich Core poll events with duration."""

    def test_duration_filled_from_fetch_complete(self) -> None:
        lines = (FIXTURES_DIR / "ha_full_session.txt").read_text().splitlines()
        result = parse_ha_logs(lines)

        assert result.core.polls[0].duration_s == pytest.approx(2.1)
        assert result.core.polls[1].duration_s == pytest.approx(1.4)

    def test_recovery_session_poll_duration(self) -> None:
        lines = (FIXTURES_DIR / "ha_recovery_session.txt").read_text().splitlines()
        result = parse_ha_logs(lines)

        assert len(result.core.polls) == 1
        assert result.core.polls[0].duration_s == pytest.approx(1.4)


class TestRecoveryMerge:
    """Core and HA recovery events are both captured."""

    def test_core_backoff_cleared(self) -> None:
        lines = (FIXTURES_DIR / "ha_recovery_session.txt").read_text().splitlines()
        result = parse_ha_logs(lines)

        assert [r.transition for r in result.core.recoveries] == [
            "recovery_window_open (connectivity_outage)",
            "backoff_cleared",
            "recovery_window_closed (90s)",
        ]

    def test_ha_health_recovery(self) -> None:
        lines = (FIXTURES_DIR / "ha_recovery_session.txt").read_text().splitlines()
        result = parse_ha_logs(lines)

        assert len(result.ha_recoveries) == 1
        assert result.ha_recoveries[0].transition == "health_recovery"


# ---------------------------------------------------------------------------
# format_report — smoke test
# ---------------------------------------------------------------------------


class TestFormatReport:
    """Report formatting produces expected sections."""

    def test_report_contains_sections(self) -> None:
        lines = (FIXTURES_DIR / "ha_full_session.txt").read_text().splitlines()
        result = parse_ha_logs(lines)
        report = format_report(result)

        assert "SOAK TEST ANALYSIS" in report
        assert "DATA POLLING" in report
        assert "HEALTH CHECKS" in report
        assert "VERDICT" in report

    def test_report_shows_model(self) -> None:
        lines = (FIXTURES_DIR / "ha_full_session.txt").read_text().splitlines()
        result = parse_ha_logs(lines)
        report = format_report(result)

        assert "T100" in report

    def test_recovery_section_present(self) -> None:
        lines = (FIXTURES_DIR / "ha_recovery_session.txt").read_text().splitlines()
        result = parse_ha_logs(lines)
        report = format_report(result)

        assert "RECOVERY & TRANSITIONS" in report
        assert "backoff_cleared" in report

    def test_empty_input_no_sections(self) -> None:
        result = HAAnalysis()
        report = format_report(result)

        assert "SOAK TEST ANALYSIS" in report
        assert "Total polls:     0" in report
