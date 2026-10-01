"""Tests for run-over-run scorecard comparison.

Table-driven over pairs of scorecards built inline; each card holds the
per-modem rows ``build_scorecard`` writes (status, accuracy, and one
block per grade dimension).
"""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.regression.compare import (
    compare_scorecards,
    render_comparison,
)


def _row(
    modem: str = "acme/a100",
    pct: float = 100.0,
    status: str = "clean",
    har: str = "modem.har",
    **dims: dict[str, str],
) -> dict[str, Any]:
    """One per-modem scorecard row; ``dims`` maps dimension to {item: grade status}."""
    return {
        "modem": modem,
        "har_file": har,
        "status": status,
        "accuracy_pct": pct,
        "total_fields": 100,
        "matching_fields": round(pct),
        "diff_count": 0,
        "stage_failed": "",
        "error": "",
        **{dim: {item: {"status": s, "detail": ""} for item, s in items.items()} for dim, items in dims.items()},
    }


def _card(*rows: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": "2026-10-01T00:00:00+00:00",
        "commit": "abc1234",
        "fleet_accuracy_pct": 90.0,
        "modems": list(rows),
    }


KEY = "acme/a100:modem.har"

# ┌──────────────────────┬────────────────────────────────────┬──────────────────────────────────────┐
# │ case                 │ change between cards               │ expected                             │
# ├──────────────────────┼────────────────────────────────────┼──────────────────────────────────────┤
# │ unchanged            │ none                               │ 1 unchanged, nothing moved           │
# │ moved-up             │ accuracy 80 -> 90                  │ moved +10                            │
# │ moved-down           │ accuracy 90 -> 80                  │ moved -10                            │
# │ status-only          │ clean -> drift, same accuracy      │ moved 0, status change               │
# │ grade-changed        │ auth.strategy match -> mismatch    │ moved 0, one grade change            │
# │ grade-appeared       │ actions.restart absent -> p_only   │ moved 0, grade from None             │
# │ entered              │ capture only in current            │ entered                              │
# │ left                 │ capture only in baseline           │ left                                 │
# │ renamed-capture      │ har a.har -> b.har                 │ one left plus one entered            │
# └──────────────────────┴────────────────────────────────────┴──────────────────────────────────────┘
#
# expected: (moved as (key, delta, status pair, grade changes), unchanged, entered keys, left keys)
#
# fmt: off
COMPARE_CASES = [
    ([_row()],                                  [_row()],
     ([], 1, [], []),                                                                    "unchanged"),
    ([_row(pct=80.0, status="drift")],          [_row(pct=90.0, status="drift")],
     ([(KEY, 10.0, ("drift", "drift"), [])], 0, [], []),                                 "moved-up"),
    ([_row(pct=90.0, status="drift")],          [_row(pct=80.0, status="drift")],
     ([(KEY, -10.0, ("drift", "drift"), [])], 0, [], []),                                "moved-down"),
    ([_row()],                                  [_row(status="drift")],
     ([(KEY, 0.0, ("clean", "drift"), [])], 0, [], []),                                  "status-only"),
    ([_row(auth={"strategy": "match"})],        [_row(auth={"strategy": "mismatch"})],
     ([(KEY, 0.0, ("clean", "clean"), [("auth", "strategy", "match", "mismatch")])], 0, [], []),
                                                                                         "grade-changed"),
    ([_row()],                                  [_row(actions={"restart": "pipeline_only"})],
     ([(KEY, 0.0, ("clean", "clean"), [("actions", "restart", None, "pipeline_only")])], 0, [], []),
                                                                                         "grade-appeared"),
    ([_row()],                                  [_row(), _row(modem="acme/b200")],
     ([], 1, ["acme/b200:modem.har"], []),                                               "entered"),
    ([_row(), _row(modem="acme/b200")],         [_row()],
     ([], 1, [], ["acme/b200:modem.har"]),                                               "left"),
    ([_row(har="a.har")],                       [_row(har="b.har")],
     ([], 0, ["acme/a100:b.har"], ["acme/a100:a.har"]),                                  "renamed-capture"),
]
# fmt: on


@pytest.mark.parametrize(
    "baseline_rows,current_rows,expected",
    [(b, c, e) for b, c, e, _ in COMPARE_CASES],
    ids=[case_id for *_, case_id in COMPARE_CASES],
)
def test_compare_scorecards(
    baseline_rows: list[dict[str, Any]],
    current_rows: list[dict[str, Any]],
    expected: tuple[list[Any], int, list[str], list[str]],
) -> None:
    """Each per-modem change lands in the right bucket with the right detail."""
    cmp = compare_scorecards(_card(*baseline_rows), _card(*current_rows))
    moved = [
        (
            m.key,
            m.delta_pct,
            (m.before_status, m.after_status),
            [(g.dimension, g.item, g.before, g.after) for g in m.grade_changes],
        )
        for m in cmp.moved
    ]
    assert (moved, cmp.unchanged, [e.key for e in cmp.entered], [e.key for e in cmp.left]) == expected


def test_grade_detail_change_is_not_movement() -> None:
    """Only the grade status is compared; reworded detail text is not a move."""
    before = _row(auth={"strategy": "partial"})
    after = _row(auth={"strategy": "partial"})
    after["auth"]["strategy"]["detail"] = "reworded"
    cmp = compare_scorecards(_card(before), _card(after))
    assert (cmp.moved, cmp.unchanged) == ([], 1)


def test_moved_orders_worst_first() -> None:
    """Accuracy drop first, then status and grade regressions, then improvements."""
    baseline = _card(
        _row(modem="v/up", pct=80.0, status="drift"),
        _row(modem="v/down", pct=90.0, status="drift"),
        _row(modem="v/grade-worse", auth={"strategy": "match"}),
        _row(modem="v/grade-better", auth={"strategy": "mismatch"}),
        _row(modem="v/status-worse"),
    )
    current = _card(
        _row(modem="v/up", pct=85.0, status="drift"),
        _row(modem="v/down", pct=80.0, status="drift"),
        _row(modem="v/grade-worse", auth={"strategy": "mismatch"}),
        _row(modem="v/grade-better", auth={"strategy": "match"}),
        _row(modem="v/status-worse", status="failure"),
    )
    cmp = compare_scorecards(baseline, current)
    assert [m.key.split(":")[0] for m in cmp.moved] == [
        "v/down",
        "v/status-worse",
        "v/grade-worse",
        "v/grade-better",
        "v/up",
    ]


def test_compare_rejects_card_without_modems() -> None:
    """A JSON file that is not an intake scorecard is refused, not compared as empty."""
    with pytest.raises(ValueError, match="modems"):
        compare_scorecards({"fleet_accuracy_pct": 1.0}, _card(_row()))


def test_render_same_card_reports_no_movement() -> None:
    """Comparing a card against itself says so in one line."""
    card = _card(_row(), _row(modem="acme/b200"))
    text = render_comparison(compare_scorecards(card, card))
    assert "No movement: 2 captures unchanged." in text


def test_render_lists_grade_change_under_its_modem() -> None:
    """A moved modem's grade changes print beneath it as dimension.item."""
    text = render_comparison(
        compare_scorecards(_card(_row(auth={"strategy": "match"})), _card(_row(auth={"strategy": "mismatch"})))
    )
    assert KEY in text
    assert "auth.strategy: match -> mismatch" in text
