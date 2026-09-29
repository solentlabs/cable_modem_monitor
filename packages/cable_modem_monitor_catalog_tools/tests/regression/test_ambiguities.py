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


# =============================================================================
# Channel key paths (parser.<section>.<key>) read the committed parser.yaml
# =============================================================================

_KEY_PATH = "parser.downstream.status"
_AS_LOCK_STATUS = {"value": "lock_status"}


def _key_analysis(candidates: list[str]) -> dict[str, Any]:
    """An analysis dict carrying one channel key ambiguity at _KEY_PATH."""
    return {
        "ambiguities": [
            {
                "field": _KEY_PATH,
                "blocking": False,
                "candidates": [{"value": v, "evidence": [], "corroborated_by": []} for v in candidates],
                "resolution": None,
            }
        ]
    }


def _parser(field: str | None) -> dict[str, Any]:
    """A committed parser.yaml whose second downstream array maps status to ``field``."""
    second = [{"key": "status", "field": field, "type": "string"}] if field else []
    return {
        "downstream": {
            "format": "json",
            "arrays": [
                {"array_path": "dss", "fields": [{"key": "channel", "field": "channel_id", "type": "integer"}]},
                {"array_path": "ofdm", "fields": second},
            ],
        }
    }


_MAPS_LOCK = _parser("lock_status")

# ┌─────────────────────┬─────────────┬─────────────┬────────────────┬─────────────────────────┐
# │ candidates          │ committed   │ resolution  │ grade          │ description             │
# ├─────────────────────┼─────────────┼─────────────┼────────────────┼─────────────────────────┤
# │ lock_status, status │ lock_status │ lock_status │ partial        │ surfaced among several  │
# │ status, snr         │ lock_status │ lock_status │ committed_only │ new meaning, still read │
# │ lock_status, status │ key absent  │ none        │ pipeline_only  │ committed maps no key   │
# └─────────────────────┴─────────────┴─────────────┴────────────────┴─────────────────────────┘
# No case fails the HAR.
#
# fmt: off
KEY_CASES: list[tuple[dict[str, Any], dict[str, Any], Any, str, str]] = [
    # (analysis,                               committed parser, resolution,      grade,            id)
    (_key_analysis(["lock_status", "status"]), _MAPS_LOCK,       _AS_LOCK_STATUS, "partial",        "surfaced"),
    (_key_analysis(["status", "snr"]),         _MAPS_LOCK,       _AS_LOCK_STATUS, "committed_only", "new-meaning"),
    (_key_analysis(["lock_status", "status"]), _parser(None),    _NONE,           "pipeline_only",  "key-absent"),
]
# fmt: on


@pytest.mark.parametrize(
    "analysis,committed_parser,resolution,grade",
    [c[:4] for c in KEY_CASES],
    ids=[c[4] for c in KEY_CASES],
)
def test_resolve_channel_key_from_committed_parser(
    analysis: dict[str, Any],
    committed_parser: dict[str, Any],
    resolution: Any,
    grade: str,
) -> None:
    """A key path resolves from the committed parser.yaml; an unoffered meaning is graded, never a failure."""
    grades, failures = resolve_from_committed(analysis, _LOCKED, committed_parser)
    assert analysis["ambiguities"][0]["resolution"] == resolution
    assert grades[_KEY_PATH].status == grade
    assert failures == []


def test_unoffered_action_is_graded_not_failed() -> None:
    """An action the capture never sent is graded committed_only and applied; the HAR continues."""
    analysis = {
        "ambiguities": [
            {
                "field": "actions.restart.fun",
                "blocking": False,
                "candidates": [{"value": "16", "evidence": [], "corroborated_by": []}],
                "resolution": None,
            }
        ]
    }
    grades, failures = resolve_from_committed(analysis, {"actions": {"restart": {"type": "cbn", "fun": 8}}})
    assert grades["actions.restart.fun"].status == "committed_only"
    assert analysis["ambiguities"][0]["resolution"] == {"value": 8}
    assert failures == []
