"""Tests for the HA log analysis script.

Fixture-driven tests for parse_ha_logs, inline tests for report
formatting and enrichment behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.dev.analyze_logs import (
    HAAnalysis,
    format_report,
    parse_ha_logs,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "analysis"

# ---------------------------------------------------------------------------
# parse_ha_logs — table-driven fixture tests
# ---------------------------------------------------------------------------

# ┌────────────────────────┬───────┬────────┬─────────┬──────────┬──────────────┐
# │ fixture                │ polls │ health │ backoffs│ ha_recov │ model        │
# ├────────────────────────┼───────┼────────┼─────────┼──────────┼──────────────┤
# │ ha_full_session.log    │ 2     │ 1      │ 0       │ 0        │ T100         │
# │ ha_recovery_session    │ 1     │ 4      │ 1       │ 1        │ T100         │
# └────────────────────────┴───────┴────────┴─────────┴──────────┴──────────────┘
#
# fmt: off
PARSE_CASES = [
    # (fixture,                     polls, health, backoffs, ha_recoveries, model)
    ("ha_full_session.log",         2,     1,      0,        0,             "T100"),
    ("ha_recovery_session.log",     1,     4,      1,        1,             "T100"),
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
        lines = (FIXTURES_DIR / "ha_full_session.log").read_text().splitlines()
        result = parse_ha_logs(lines)

        assert result.version == "v3.14.0-alpha.9"
        assert result.model == "T100"
        assert result.poll_interval_m == 5
        assert result.health_interval_s == 30

    def test_first_poll_no_data(self) -> None:
        lines = (FIXTURES_DIR / "ha_full_session.log").read_text().splitlines()
        result = parse_ha_logs(lines)

        assert result.first_poll_no_data is True

    def test_deferred_entity_count(self) -> None:
        lines = (FIXTURES_DIR / "ha_full_session.log").read_text().splitlines()
        result = parse_ha_logs(lines)

        assert result.deferred_entity_count == 24


class TestPollDurationEnrichment:
    """fetch_complete lines enrich Core poll events with duration."""

    def test_duration_filled_from_fetch_complete(self) -> None:
        lines = (FIXTURES_DIR / "ha_full_session.log").read_text().splitlines()
        result = parse_ha_logs(lines)

        assert result.core.polls[0].duration_s == pytest.approx(2.1)
        assert result.core.polls[1].duration_s == pytest.approx(1.4)

    def test_recovery_session_poll_duration(self) -> None:
        lines = (FIXTURES_DIR / "ha_recovery_session.log").read_text().splitlines()
        result = parse_ha_logs(lines)

        assert len(result.core.polls) == 1
        assert result.core.polls[0].duration_s == pytest.approx(1.4)


class TestRecoveryMerge:
    """Core and HA recovery events are both captured."""

    def test_core_backoff_cleared(self) -> None:
        lines = (FIXTURES_DIR / "ha_recovery_session.log").read_text().splitlines()
        result = parse_ha_logs(lines)

        assert len(result.core.recoveries) == 1
        assert result.core.recoveries[0].transition == "backoff_cleared"

    def test_ha_health_recovery(self) -> None:
        lines = (FIXTURES_DIR / "ha_recovery_session.log").read_text().splitlines()
        result = parse_ha_logs(lines)

        assert len(result.ha_recoveries) == 1
        assert result.ha_recoveries[0].transition == "health_recovery"


# ---------------------------------------------------------------------------
# format_report — smoke test
# ---------------------------------------------------------------------------


class TestFormatReport:
    """Report formatting produces expected sections."""

    def test_report_contains_sections(self) -> None:
        lines = (FIXTURES_DIR / "ha_full_session.log").read_text().splitlines()
        result = parse_ha_logs(lines)
        report = format_report(result)

        assert "SOAK TEST ANALYSIS" in report
        assert "DATA POLLING" in report
        assert "HEALTH CHECKS" in report
        assert "VERDICT" in report

    def test_report_shows_model(self) -> None:
        lines = (FIXTURES_DIR / "ha_full_session.log").read_text().splitlines()
        result = parse_ha_logs(lines)
        report = format_report(result)

        assert "T100" in report

    def test_recovery_section_present(self) -> None:
        lines = (FIXTURES_DIR / "ha_recovery_session.log").read_text().splitlines()
        result = parse_ha_logs(lines)
        report = format_report(result)

        assert "RECOVERY & TRANSITIONS" in report
        assert "backoff_cleared" in report

    def test_empty_input_no_sections(self) -> None:
        result = HAAnalysis()
        report = format_report(result)

        assert "SOAK TEST ANALYSIS" in report
        assert "Total polls:     0" in report
