"""Per-modem regression result and status classification."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..grading import Grade

# Severity ordering: clean < drift < failure
STATUS_SEVERITY: dict[str, int] = {"clean": 0, "drift": 1, "failure": 2}


@dataclass
class ModemResult:
    """Result of running the full pipeline regression on one modem HAR."""

    modem: str
    har_file: str
    stage_failed: str = ""
    error: str = ""
    golden_diffs: list[str] = field(default_factory=list)
    config_diffs: list[str] = field(default_factory=list)
    # Capability grades keyed by dimension ("actions", "auth", ...) then item
    grades: dict[str, dict[str, Grade]] = field(default_factory=dict)
    channel_counts: dict[str, int] = field(default_factory=dict)
    total_fields: int = 0
    matching_fields: int = 0

    @property
    def passed(self) -> bool:
        """No stage failures and no golden file drift."""
        return not self.stage_failed and not self.golden_diffs

    @property
    def accuracy_pct(self) -> float:
        """Field-level accuracy against committed golden file."""
        if self.total_fields == 0:
            return 0.0
        return self.matching_fields / self.total_fields * 100


def result_status(result: ModemResult) -> str:
    """Classify a result as clean, drift, or failure."""
    if result.stage_failed:
        return "failure"
    if result.golden_diffs:
        return "drift"
    return "clean"


def result_key(result: ModemResult) -> str:
    """Unique key for a result: modem_id:har_filename."""
    return f"{result.modem}:{result.har_file}"


def fleet_accuracy(results: list[ModemResult]) -> tuple[int, int, float]:
    """Fleet-wide (matching, total, pct) over modems with committed golden files."""
    scored = [r for r in results if r.total_fields > 0]
    total = sum(r.total_fields for r in scored)
    matching = sum(r.matching_fields for r in scored)
    pct = (matching / total * 100) if total else 0.0
    return matching, total, pct
