"""Marker accuracy: how far each landing-response marker narrows, and which real entries it would remove.

Feeds ``intake_pipeline_regression.py``. A marker may remove an entry only
when the catalog shows the entry cannot present the observed value, so a
marker is scored per HAR against the values its own entry shows in its
other captures. See INTAKE_PIPELINE.md § Marker accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from solentlabs.cable_modem_monitor_core.detection import Observation

MARKERS = ("scheme", "server", "www_authenticate", "password_field")


@dataclass(frozen=True)
class Capture:
    """One HAR's landing observation, tied to the catalog entry it belongs to."""

    modem: str
    har_file: str
    entry: Path
    observation: Observation

    @property
    def label(self) -> str:
        return f"{self.modem} ({self.har_file})"


@dataclass(frozen=True)
class MarkerScore:
    """One marker on one HAR: entries kept, and whether the HAR's own entry was removed (None: not scored)."""

    narrowing: int
    wrongly_removed: bool | None


@dataclass(frozen=True)
class HarScore:
    """Every marker's score for one HAR."""

    label: str
    markers: dict[str, MarkerScore]


@dataclass(frozen=True)
class MarkerSummary:
    """Fleet totals for one marker."""

    scored: int
    wrongly_removed: list[str]
    mean_narrowing: float


def marker_values(observation: Observation) -> dict[str, str | bool]:
    """The comparable value of each marker; the ``Server`` product is the text before ``/``."""
    return {
        "scheme": observation.scheme,
        "server": (observation.server or "").split("/")[0].strip(),
        "www_authenticate": bool(observation.www_authenticate),
        "password_field": observation.password_field,
    }


def score_markers(captures: list[Capture], entries: list[Path]) -> list[HarScore]:
    """Score every marker on every capture against the catalog's ``entries``.

    An entry is kept when any of its captures shows the observed value, or
    when it has no capture to judge by. The HAR's own entry is judged by its
    other captures only.
    """
    values = [marker_values(c.observation) for c in captures]
    by_entry: dict[Path, list[int]] = {}
    for index, capture in enumerate(captures):
        by_entry.setdefault(capture.entry, []).append(index)

    scores: list[HarScore] = []
    for index, capture in enumerate(captures):
        markers: dict[str, MarkerScore] = {}
        for marker in MARKERS:
            kept = 0
            own_removed: bool | None = None
            for entry in entries:
                pool = [i for i in by_entry.get(entry, []) if i != index]
                vouched = not pool or any(values[i][marker] == values[index][marker] for i in pool)
                kept += vouched
                if entry == capture.entry and pool:
                    own_removed = not vouched
            markers[marker] = MarkerScore(kept, own_removed)
        scores.append(HarScore(capture.label, markers))
    return scores


def summarize_markers(scores: list[HarScore]) -> dict[str, MarkerSummary]:
    """Per-marker totals: HARs scored, which were wrongly removed, mean entries kept."""
    summary: dict[str, MarkerSummary] = {}
    for marker in MARKERS:
        marker_scores = [(s.label, s.markers[marker]) for s in scores]
        summary[marker] = MarkerSummary(
            scored=sum(1 for _, m in marker_scores if m.wrongly_removed is not None),
            wrongly_removed=[label for label, m in marker_scores if m.wrongly_removed],
            mean_narrowing=sum(m.narrowing for _, m in marker_scores) / len(marker_scores) if marker_scores else 0.0,
        )
    return summary


def render_marker_report(scores: list[HarScore], total_entries: int) -> str:
    """Render per-marker totals with each wrongly removed HAR listed, then entries kept per HAR."""
    summary = summarize_markers(scores)
    lines = [f"MARKER ACCURACY — entries each marker keeps, of {total_entries} (report only):"]
    for marker, totals in summary.items():
        lines.append(
            f"  {marker}: scored {totals.scored}, wrongly removed {len(totals.wrongly_removed)},"
            f" mean kept {totals.mean_narrowing:.1f}"
        )
        lines.extend(f"    wrongly removed: {label}" for label in totals.wrongly_removed)
    if scores:
        lines.append("  Entries kept per HAR (" + ", ".join(MARKERS) + "):")
        for score in scores:
            kept = ", ".join(f"{score.markers[m].narrowing:>2}" for m in MARKERS)
            lines.append(f"    {score.label}: {kept}")
    return "\n".join(lines)
