"""Run-over-run scorecard comparison: which captures' intake scores moved.

One HAR is a few percent of the fleet's field mass, so a large gain on
one modem barely moves the fleet percentage. The per-capture view is
where intake work shows. Reporting only; nothing here gates a build.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..grading import GRADE_SEVERITY
from .results import STATUS_SEVERITY


@dataclass(frozen=True)
class GradeChange:
    """One graded item whose status differs between the two cards; None means ungraded on that side."""

    dimension: str
    item: str
    before: str | None
    after: str | None

    @property
    def severity_delta(self) -> int:
        """Positive when the grade got worse; zero when either side is ungraded."""
        if self.before is None or self.after is None:
            return 0
        return GRADE_SEVERITY.get(self.after, 0) - GRADE_SEVERITY.get(self.before, 0)


@dataclass(frozen=True)
class ModemMove:
    """A capture present in both cards whose accuracy, status, or grades changed."""

    key: str
    before_pct: float
    after_pct: float
    before_fields: str
    after_fields: str
    before_status: str
    after_status: str
    grade_changes: tuple[GradeChange, ...]

    @property
    def delta_pct(self) -> float:
        """Percentage-point movement, positive when accuracy improved."""
        return round(self.after_pct - self.before_pct, 2)

    @property
    def status_delta(self) -> int:
        """Positive when clean/drift/failure got worse."""
        return STATUS_SEVERITY.get(self.after_status, 0) - STATUS_SEVERITY.get(self.before_status, 0)


@dataclass(frozen=True)
class RosterChange:
    """A capture present in only one of the two cards."""

    key: str
    accuracy_pct: float
    status: str


@dataclass(frozen=True)
class ScorecardComparison:
    """Per-capture movement between a baseline card and the current one."""

    before_label: str
    after_label: str
    before_fleet_pct: float
    after_fleet_pct: float
    moved: list[ModemMove]
    unchanged: int
    entered: list[RosterChange]
    left: list[RosterChange]


def _rows(card: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index a card's per-modem rows by ``modem:har_file``, the key ``result_key`` uses."""
    # A card is parsed JSON; its top level can be any JSON value.
    rows = card.get("modems") if isinstance(card, dict) else None
    if not isinstance(rows, list):
        raise ValueError("no 'modems' list; not an intake scorecard")
    return {f"{r['modem']}:{r['har_file']}": r for r in rows}


def _grades(row: dict[str, Any]) -> dict[tuple[str, str], str]:
    """Grade status per (dimension, item); a dimension is any dict-valued row field."""
    return {
        (dim, item): grade["status"]
        for dim, block in row.items()
        if isinstance(block, dict)
        for item, grade in block.items()
    }


def _fields(row: dict[str, Any]) -> str:
    return f"{row.get('matching_fields', 0)}/{row.get('total_fields', 0)}"


def _move(key: str, before: dict[str, Any], after: dict[str, Any]) -> ModemMove:
    before_grades, after_grades = _grades(before), _grades(after)
    changes = tuple(
        GradeChange(dim, item, before_grades.get((dim, item)), after_grades.get((dim, item)))
        for dim, item in sorted(before_grades.keys() | after_grades.keys())
        if before_grades.get((dim, item)) != after_grades.get((dim, item))
    )
    return ModemMove(
        key=key,
        before_pct=before.get("accuracy_pct", 0.0),
        after_pct=after.get("accuracy_pct", 0.0),
        before_fields=_fields(before),
        after_fields=_fields(after),
        before_status=before.get("status", ""),
        after_status=after.get("status", ""),
        grade_changes=changes,
    )


def _roster(rows: dict[str, dict[str, Any]], keys: set[str]) -> list[RosterChange]:
    return [RosterChange(k, rows[k].get("accuracy_pct", 0.0), rows[k].get("status", "")) for k in sorted(keys)]


def _label(card: dict[str, Any]) -> str:
    """Commit sha plus capture date."""
    commit = card.get("commit") or "unknown"
    stamp = str(card.get("timestamp") or "")[:10]
    return f"{commit} ({stamp})" if stamp else commit


def compare_scorecards(baseline: dict[str, Any], current: dict[str, Any]) -> ScorecardComparison:
    """Diff two scorecards into per-capture moves and roster changes, worst move first."""
    before_rows, after_rows = _rows(baseline), _rows(current)
    moves = [_move(k, before_rows[k], after_rows[k]) for k in before_rows.keys() & after_rows.keys()]
    moved = [m for m in moves if m.delta_pct or m.before_status != m.after_status or m.grade_changes]
    # Worst first: accuracy drop, then status worsening, then grade worsening.
    moved.sort(key=lambda m: (m.delta_pct, -m.status_delta, -sum(g.severity_delta for g in m.grade_changes), m.key))
    return ScorecardComparison(
        before_label=_label(baseline),
        after_label=_label(current),
        before_fleet_pct=baseline.get("fleet_accuracy_pct", 0.0),
        after_fleet_pct=current.get("fleet_accuracy_pct", 0.0),
        moved=moved,
        unchanged=len(moves) - len(moved),
        entered=_roster(after_rows, after_rows.keys() - before_rows.keys()),
        left=_roster(before_rows, before_rows.keys() - after_rows.keys()),
    )


def render_comparison(cmp: ScorecardComparison) -> str:
    """Console block the regression script prints for --compare."""
    lines = [
        f"INTAKE COMPARISON  {cmp.before_label} -> {cmp.after_label}",
        f"  FLEET  {cmp.before_fleet_pct:.2f}% -> {cmp.after_fleet_pct:.2f}%"
        f"  ({cmp.after_fleet_pct - cmp.before_fleet_pct:+.2f})",
        "",
    ]
    if not (cmp.moved or cmp.entered or cmp.left):
        lines.append(f"No movement: {cmp.unchanged} captures unchanged.")
        return "\n".join(lines)

    lines.append(f"MOVED ({len(cmp.moved)} of {len(cmp.moved) + cmp.unchanged} in both cards):")
    for m in cmp.moved:
        status = f"  [{m.before_status} -> {m.after_status}]" if m.before_status != m.after_status else ""
        lines.append(
            f"  {m.delta_pct:+7.2f}  {m.key}  {m.before_pct:.2f}% -> {m.after_pct:.2f}%"
            f"  ({m.before_fields} -> {m.after_fields}){status}"
        )
        for g in m.grade_changes:
            lines.append(f"           {g.dimension}.{g.item}: {g.before or 'ungraded'} -> {g.after or 'ungraded'}")

    for title, entries in (("ENTERED", cmp.entered), ("LEFT", cmp.left)):
        if entries:
            lines += ["", f"{title} ({len(entries)}):"]
            lines += [f"  {e.key}  {e.accuracy_pct:.2f}%  {e.status}" for e in entries]
    if cmp.entered and cmp.left:
        lines += ["", "A renamed capture shows as one LEFT plus one ENTERED."]
    return "\n".join(lines)
