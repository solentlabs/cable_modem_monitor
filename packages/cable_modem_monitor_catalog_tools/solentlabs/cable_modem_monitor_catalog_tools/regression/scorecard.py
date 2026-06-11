"""JSON scorecard built from regression results, for trend tracking."""

from __future__ import annotations

import os
import subprocess
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ..grading import GRADE_SEVERITY
from .results import ModemResult, fleet_accuracy, result_status


def build_scorecard(results: list[ModemResult]) -> dict[str, Any]:
    """Build a JSON-serialisable scorecard for trend tracking."""
    matching, total, fleet_pct = fleet_accuracy(results)
    failed_count = sum(1 for r in results if r.stage_failed)

    card: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "commit": _git_sha(),
        "fleet_accuracy_pct": round(fleet_pct, 2),
        "pipeline_pass_rate_pct": round((len(results) - failed_count) / len(results) * 100, 2) if results else 0.0,
        "total_fields": total,
        "matching_fields": matching,
        "total_hars": len(results),
        "pipeline_passed": len(results) - failed_count,
    }

    for dim in sorted({dim for r in results for dim in r.grades}):
        tally = Counter(grade.status for r in results for grade in r.grades.get(dim, {}).values())
        card[f"{dim}_summary"] = {status: tally.get(status, 0) for status in GRADE_SEVERITY}

    card["modems"] = [
        {
            "modem": r.modem,
            "har_file": r.har_file,
            "status": result_status(r),
            "accuracy_pct": round(r.accuracy_pct, 2),
            "total_fields": r.total_fields,
            "matching_fields": r.matching_fields,
            "diff_count": len(r.golden_diffs),
            "stage_failed": r.stage_failed,
            "error": r.error,
            **{
                dim: {item: {"status": g.status, "detail": g.detail} for item, g in sorted(grades.items())}
                for dim, grades in sorted(r.grades.items())
            },
        }
        for r in results
    ]
    return card


def _git_sha() -> str:
    """Short HEAD sha, falling back to GITHUB_SHA in CI."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:  # noqa: BLE001 — any git failure falls back to env
        return os.environ.get("GITHUB_SHA", "")[:8]
