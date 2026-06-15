"""Tests for the regression baseline ratchet: load, save, compare."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.grading import Grade
from solentlabs.cable_modem_monitor_catalog_tools.regression import (
    BaselineEntry,
    ModemResult,
    compare_baseline,
    entries_from_results,
    load_baseline,
    save_baseline,
)


def _result(modem: str = "acme/a100", **kwargs) -> ModemResult:
    return ModemResult(modem=modem, har_file="modem.har", **kwargs)


def _entry(pipeline: str = "clean", **dimensions: dict[str, str]) -> BaselineEntry:
    return BaselineEntry(pipeline=pipeline, dimensions=dict(dimensions))


# =====================================================================
# entries_from_results
# =====================================================================


def test_entries_from_results() -> None:
    """Results map to entries keyed modem:har with grade statuses per dimension."""
    r = _result(golden_diffs=["x"], grades={"actions": {"restart": Grade("partial", "why")}})
    entries = entries_from_results([r])
    assert entries == {"acme/a100:modem.har": BaselineEntry("drift", {"actions": {"restart": "partial"}})}


def test_entries_preserve_empty_dimension() -> None:
    """A graded-but-empty dimension stays in the entry (schema stability)."""
    entries = entries_from_results([_result(grades={"actions": {}})])
    assert entries["acme/a100:modem.har"].dimensions == {"actions": {}}


# =====================================================================
# load / save round trip
# =====================================================================


def test_save_load_round_trip(tmp_path: Path) -> None:
    """Entries survive a save/load cycle unchanged."""
    entries = {
        "acme/a100:modem.har": _entry("drift", actions={"logout": "match", "restart": "partial"}),
        "acme/b200:modem.har": _entry("failure"),
    }
    path = tmp_path / "baseline.json"
    save_baseline(path, entries)
    assert load_baseline(path) == entries


def test_load_normalizes_legacy_string_schema(tmp_path: Path) -> None:
    """Pre-dimension baselines (bare status strings) load with no dimensions."""
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"results": {"acme/a100:modem.har": "drift"}}))
    assert load_baseline(path) == {"acme/a100:modem.har": _entry("drift")}


def test_saved_file_is_sorted_and_newline_terminated(tmp_path: Path) -> None:
    """On-disk format: sorted keys, trailing newline (matches committed baseline)."""
    path = tmp_path / "baseline.json"
    save_baseline(path, {"b:x": _entry("clean"), "a:x": _entry("drift", actions={"restart": "match"})})
    text = path.read_text()
    assert text.endswith("\n")
    keys = list(json.loads(text)["results"])
    assert keys == sorted(keys)


# =====================================================================
# compare_baseline — table-driven ratchet semantics
# =====================================================================


@pytest.mark.parametrize(
    ("current", "baseline", "expect_regressions", "expect_improvements"),
    [
        # Identical — silent
        (
            {"k": _entry("drift", actions={"restart": "partial"})},
            {"k": _entry("drift", actions={"restart": "partial"})},
            [],
            [],
        ),
        # Pipeline status worsens / improves
        ({"k": _entry("failure")}, {"k": _entry("drift")}, ["REGRESSED k: drift -> failure"], []),
        ({"k": _entry("clean")}, {"k": _entry("drift")}, [], ["IMPROVED  k: drift -> clean"]),
        # Action grade worsens / improves
        (
            {"k": _entry("drift", actions={"restart": "mismatch"})},
            {"k": _entry("drift", actions={"restart": "partial"})},
            ["REGRESSED k actions.restart: partial -> mismatch"],
            [],
        ),
        (
            {"k": _entry("drift", actions={"restart": "match"})},
            {"k": _entry("drift", actions={"restart": "committed_only"})},
            [],
            ["IMPROVED  k actions.restart: committed_only -> match"],
        ),
        # New modem: clean and all-match is silent; anything else flags
        ({"k": _entry("clean", actions={"logout": "match"})}, {}, [], []),
        ({"k": _entry("drift")}, {}, ["NEW k: drift (not in baseline)"], []),
        ({"k": _entry("clean", actions={"restart": "mismatch"})}, {}, ["NEW k: clean (not in baseline)"], []),
        # New graded item on a known modem
        (
            {"k": _entry("drift", actions={"logout": "pipeline_only"})},
            {"k": _entry("drift")},
            ["NEW k actions.logout: pipeline_only (not in baseline)"],
            [],
        ),
        # Removed modem / removed graded item
        ({}, {"k": _entry("drift")}, [], ["REMOVED   k: was drift"]),
        (
            {"k": _entry("drift", actions={})},
            {"k": _entry("drift", actions={"restart": "partial"})},
            [],
            ["REMOVED   k actions.restart: was partial"],
        ),
        # Unknown grade in baseline ratchets as worst severity — a known
        # current grade reads as an improvement, never a hidden regression
        (
            {"k": _entry("drift", actions={"restart": "partial"})},
            {"k": _entry("drift", actions={"restart": "someday_new_status"})},
            [],
            ["IMPROVED  k actions.restart: someday_new_status -> partial"],
        ),
    ],
)
def test_compare_baseline(
    current: dict[str, BaselineEntry],
    baseline: dict[str, BaselineEntry],
    expect_regressions: list[str],
    expect_improvements: list[str],
) -> None:
    """Ratchet messages match expectations for each scenario."""
    regressions, improvements = compare_baseline(current, baseline)
    assert [m.strip() for m in regressions] == expect_regressions
    assert [m.strip() for m in improvements] == expect_improvements


def test_compare_is_dimension_generic() -> None:
    """A second dimension (auth) ratchets with zero new plumbing."""
    current = {"k": _entry("drift", auth={"strategy": "mismatch"})}
    baseline = {"k": _entry("drift", auth={"strategy": "match"})}
    regressions, _ = compare_baseline(current, baseline)
    assert [m.strip() for m in regressions] == ["REGRESSED k auth.strategy: match -> mismatch"]
