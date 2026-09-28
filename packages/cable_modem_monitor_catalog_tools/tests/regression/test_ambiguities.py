"""Tests for the regression's ambiguity resolution: the committed config answers, among the tool's candidates.

Table-driven: each case is one ambiguity's candidates plus the committed
config, and the resolution, feedback grade, and failure the regression
must record.
"""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.regression.ambiguities import resolve_from_committed

_PATH = "auth.lockout_code"
_NONE = {"value": None, "reason": "committed config declares none"}


def _analysis(candidates: list[str], resolution: dict[str, Any] | None = None) -> dict[str, Any]:
    """An analysis dict carrying one ambiguity at _PATH."""
    return {
        "ambiguities": [
            {
                "field": _PATH,
                "blocking": True,
                "candidates": [{"value": v, "evidence": [], "corroborated_by": []} for v in candidates],
                "resolution": resolution,
            }
        ]
    }


_LOCKED = {"auth": {"lockout_code": "a"}}
_ELSEWHERE = {"auth": {"lockout_code": "z"}}
_NO_CODE: dict[str, Any] = {"auth": {}}
_FLEET = {"value": "b", "source": "fleet"}

# =============================================================================
# resolve_from_committed test data
# =============================================================================
#
# ┌────────────┬───────────────┬─────────────┬────────────────┬──────────┬───────────────────────────┐
# │ candidates │ committed     │ resolution  │ grade          │ failure  │ description               │
# ├────────────┼───────────────┼─────────────┼────────────────┼──────────┼───────────────────────────┤
# │ a          │ a             │ a           │ match          │ no       │ surfaced, only candidate  │
# │ a, b       │ a             │ a           │ partial        │ no       │ surfaced among several    │
# │ a          │ absent        │ none        │ pipeline_only  │ no       │ committed declares none   │
# │ (none)     │ absent        │ none        │ match          │ no       │ none offered, none needed │
# │ a          │ z             │ unresolved  │ committed_only │ yes      │ committed value missed    │
# │ a, b (b*)  │ a             │ a           │ partial        │ no       │ committed overrides fleet │
# └────────────┴───────────────┴─────────────┴────────────────┴──────────┴───────────────────────────┘
# (b*: pre-filled from the fleet)
#
# fmt: off
CASES: list[tuple[dict[str, Any], dict[str, Any], Any, str, bool, str]] = [
    # (analysis,                     committed,  resolution,      grade,            failure, id)
    (_analysis(["a"]),               _LOCKED,    {"value": "a"},  "match",          False,   "only-candidate"),
    (_analysis(["a", "b"]),          _LOCKED,    {"value": "a"},  "partial",        False,   "among-several"),
    (_analysis(["a"]),               _NO_CODE,   _NONE,           "pipeline_only",  False,   "committed-none"),
    (_analysis([]),                  _NO_CODE,   _NONE,           "match",          False,   "none-offered"),
    (_analysis(["a"]),               _ELSEWHERE, None,            "committed_only", True,    "not-surfaced"),
    (_analysis(["a", "b"], _FLEET),  _LOCKED,    {"value": "a"},  "partial",        False,   "overrides-fleet"),
]
# fmt: on


@pytest.mark.parametrize(
    "analysis,committed,resolution,grade,failure",
    [c[:5] for c in CASES],
    ids=[c[5] for c in CASES],
)
def test_resolve_from_committed(
    analysis: dict[str, Any],
    committed: dict[str, Any],
    resolution: Any,
    grade: str,
    failure: bool,
) -> None:
    """The committed value resolves only when the tool offered it; every ambiguity is graded."""
    grades, failures = resolve_from_committed(analysis, committed)
    assert analysis["ambiguities"][0]["resolution"] == resolution
    assert grades[_PATH].status == grade
    assert bool(failures) is failure


def test_failure_names_the_value_and_candidates() -> None:
    """A committed value the tool missed is reported with what it did offer."""
    _, failures = resolve_from_committed(_analysis(["a", "b"]), _ELSEWHERE)
    assert failures == ["committed value not surfaced: auth.lockout_code = z (candidates: a, b)"]
