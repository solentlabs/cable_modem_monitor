"""Tests for scorecard building and result classification."""

from __future__ import annotations

from solentlabs.cable_modem_monitor_catalog_tools.grading import Grade
from solentlabs.cable_modem_monitor_catalog_tools.regression import (
    ModemResult,
    build_scorecard,
    fleet_accuracy,
    result_status,
)


def _result(modem: str = "acme/a100", **kwargs) -> ModemResult:
    return ModemResult(modem=modem, har_file="modem.har", **kwargs)


def test_result_status_classification() -> None:
    """Stage failure beats drift beats clean."""
    assert result_status(_result()) == "clean"
    assert result_status(_result(golden_diffs=["d"])) == "drift"
    assert result_status(_result(stage_failed="analyze_har", golden_diffs=["d"])) == "failure"


def test_fleet_accuracy_skips_modems_without_golden_fields() -> None:
    """Modems without committed golden fields don't dilute the percentage."""
    scored = _result(total_fields=10, matching_fields=9)
    no_golden = _result(modem="acme/b200")
    matching, total, pct = fleet_accuracy([scored, no_golden])
    assert (matching, total) == (9, 10)
    assert pct == 90.0


def test_build_scorecard_shape() -> None:
    """Scorecard carries fleet metrics, per-dimension summaries, and per-modem grades."""
    r = _result(
        total_fields=10,
        matching_fields=8,
        golden_diffs=["d"],
        grades={"actions": {"restart": Grade("partial", "params not extracted: ['x']")}},
    )
    card = build_scorecard([r])
    assert card["fleet_accuracy_pct"] == 80.0
    assert card["total_hars"] == 1
    assert card["pipeline_passed"] == 1
    assert card["actions_summary"] == {"match": 0, "partial": 1, "pipeline_only": 0, "committed_only": 0, "mismatch": 0}
    modem = card["modems"][0]
    assert modem["status"] == "drift"
    assert modem["actions"] == {"restart": {"status": "partial", "detail": "params not extracted: ['x']"}}


def test_build_scorecard_second_dimension() -> None:
    """A new dimension gets its own summary and per-modem block automatically."""
    r = _result(grades={"auth": {"strategy": Grade("match")}})
    card = build_scorecard([r])
    assert card["auth_summary"]["match"] == 1
    assert card["modems"][0]["auth"] == {"strategy": {"status": "match", "detail": ""}}
