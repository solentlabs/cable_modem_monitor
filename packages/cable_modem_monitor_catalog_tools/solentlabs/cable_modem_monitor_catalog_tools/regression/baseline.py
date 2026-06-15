"""Fleet baseline: load, save, and ratchet comparison for regression runs.

The committed baseline records each modem's pipeline status plus grade
statuses per capability dimension. Comparison is a ratchet: anything
moving to a higher severity is a regression; new entries are flagged
unless fully clean. Dimensions are generic — adding one (e.g. auth)
requires no changes here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..grading import GRADE_SEVERITY
from .results import STATUS_SEVERITY, ModemResult, result_key, result_status

_COMMENT = "Intake pipeline regression baseline. Update with --update-baseline."


@dataclass(frozen=True)
class BaselineEntry:
    """Recorded state for one modem:har — pipeline status + dimension grades."""

    pipeline: str
    dimensions: dict[str, dict[str, str]] = field(default_factory=dict)


def entries_from_results(results: list[ModemResult]) -> dict[str, BaselineEntry]:
    """Project regression results into baseline entries."""
    return {
        result_key(r): BaselineEntry(
            pipeline=result_status(r),
            dimensions={
                dim: {item: grade.status for item, grade in sorted(grades.items())}
                for dim, grades in sorted(r.grades.items())
            },
        )
        for r in results
    }


def load_baseline(path: Path) -> dict[str, BaselineEntry]:
    """Load a baseline file; legacy bare-string entries normalize to pipeline-only."""
    data = json.loads(path.read_text()).get("results", {})
    entries: dict[str, BaselineEntry] = {}
    for key, value in data.items():
        if isinstance(value, str):
            entries[key] = BaselineEntry(pipeline=value)
        else:
            dimensions = {dim: dict(items) for dim, items in value.items() if dim != "pipeline"}
            entries[key] = BaselineEntry(pipeline=value.get("pipeline", "clean"), dimensions=dimensions)
    return entries


def save_baseline(path: Path, entries: dict[str, BaselineEntry]) -> None:
    """Write entries as the new baseline (sorted, newline-terminated)."""
    results = {
        key: {"pipeline": entry.pipeline, **dict(sorted(entry.dimensions.items()))}
        for key, entry in sorted(entries.items())
    }
    data = {"_comment": _COMMENT, "results": results}
    path.write_text(json.dumps(data, indent=2) + "\n")


def compare_baseline(
    current: dict[str, BaselineEntry],
    baseline: dict[str, BaselineEntry],
) -> tuple[list[str], list[str]]:
    """Ratchet current entries against the baseline.

    Returns (regressions, improvements) as human-readable messages. A
    regression is a pipeline status or any dimension grade moving to a
    higher severity, or a new entry that is not fully clean.
    """
    regressions: list[str] = []
    improvements: list[str] = []

    for key, entry in current.items():
        base = baseline.get(key)

        if base is None:
            # New modem not in baseline — not a regression, but flag it
            all_match = all(g == "match" for items in entry.dimensions.values() for g in items.values())
            if entry.pipeline != "clean" or not all_match:
                regressions.append(f"  NEW {key}: {entry.pipeline} (not in baseline)")
            continue

        cur_sev = STATUS_SEVERITY[entry.pipeline]
        base_sev = STATUS_SEVERITY.get(base.pipeline, 0)
        if cur_sev > base_sev:
            regressions.append(f"  REGRESSED {key}: {base.pipeline} -> {entry.pipeline}")
        elif cur_sev < base_sev:
            improvements.append(f"  IMPROVED  {key}: {base.pipeline} -> {entry.pipeline}")

        _compare_dimensions(key, entry, base, regressions, improvements)

    for key in sorted(set(baseline) - set(current)):
        improvements.append(f"  REMOVED   {key}: was {baseline[key].pipeline}")

    return regressions, improvements


def _compare_dimensions(
    key: str,
    entry: BaselineEntry,
    base: BaselineEntry,
    regressions: list[str],
    improvements: list[str],
) -> None:
    """Ratchet every dimension's per-item grades for one modem."""
    worst = max(GRADE_SEVERITY.values())
    for dim in sorted(set(entry.dimensions) | set(base.dimensions)):
        cur_items = entry.dimensions.get(dim, {})
        base_items = base.dimensions.get(dim, {})
        for item, status in sorted(cur_items.items()):
            base_status = base_items.get(item)
            if base_status is None:
                if status != "match":
                    regressions.append(f"  NEW {key} {dim}.{item}: {status} (not in baseline)")
                continue
            cur_sev = GRADE_SEVERITY[status]
            # Unknown baseline grades read as worst severity, so a known
            # current grade can only register as an improvement
            base_sev = GRADE_SEVERITY.get(base_status, worst)
            if cur_sev > base_sev:
                regressions.append(f"  REGRESSED {key} {dim}.{item}: {base_status} -> {status}")
            elif cur_sev < base_sev:
                improvements.append(f"  IMPROVED  {key} {dim}.{item}: {base_status} -> {status}")
        for item in sorted(set(base_items) - set(cur_items)):
            improvements.append(f"  REMOVED   {key} {dim}.{item}: was {base_items[item]}")
