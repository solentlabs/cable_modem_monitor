"""Tests for ambiguity corroboration: confirmed catalog values annotate and pre-fill.

Table-driven: each case is one ambiguity's candidate values plus the
confirmed fleet's values at its path, and the annotations and resolution
analysis must produce.
"""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.ambiguity import (
    Ambiguity,
    Candidate,
    Evidence,
    corroborate,
)

_PATH = "auth.lockout_code"

# =============================================================================
# corroborate test data
# =============================================================================
#
# ┌───────────┬───────────────────────────┬──────────────┬──────────────┬──────────────────────┐
# │ candidates│ confirmed values at path  │ corroborated │ resolution   │ description          │
# ├───────────┼───────────────────────────┼──────────────┼──────────────┼──────────────────────┤
# │ a, b      │ {}                        │ none         │ None         │ nothing confirmed    │
# │ a, b      │ {a: [x/1]}                │ a by x/1     │ a, fleet     │ one corroborated     │
# │ a, b      │ {a: [x/1], b: [y/2]}      │ a and b      │ None         │ two corroborated     │
# │ a         │ {z: [x/1]}                │ none         │ None         │ value elsewhere      │
# │ a         │ other path {a: [x/1]}     │ none         │ None         │ path must match      │
# └───────────┴───────────────────────────┴──────────────┴──────────────┴──────────────────────┘
#
_ONE = {"value": "a", "source": "fleet"}
_OTHER_PATH = "auth.session_expired_code"

# fmt: off
CORROBORATE_CASES: list[tuple[list[str], dict[str, dict[str, list[str]]], dict[str, list[str]], Any, str]] = [
    # (candidates, confirmed,                             corroborated_by,              resolution, id)
    (["a", "b"],  {},                                    {},                           None,       "nothing-confirmed"),
    (["a", "b"],  {_PATH: {"a": ["x/1"]}},               {"a": ["x/1"]},               _ONE,       "one-corroborated"),
    (["a", "b"],  {_PATH: {"a": ["x/1"], "b": ["y/2"]}}, {"a": ["x/1"], "b": ["y/2"]}, None,       "two-corroborated"),
    (["a"],       {_PATH: {"z": ["x/1"]}},               {},                           None,       "value-elsewhere"),
    (["a"],       {_OTHER_PATH: {"a": ["x/1"]}},         {},                           None,       "path-must-match"),
]
# fmt: on


@pytest.mark.parametrize(
    "values,confirmed,corroborated_by,resolution",
    [c[:4] for c in CORROBORATE_CASES],
    ids=[c[4] for c in CORROBORATE_CASES],
)
def test_corroborate(
    values: list[str],
    confirmed: dict[str, dict[str, list[str]]],
    corroborated_by: dict[str, list[str]],
    resolution: Any,
) -> None:
    """Confirmed values annotate their candidates; exactly one corroborated candidate pre-fills the resolution."""
    ambiguity = Ambiguity(
        field=_PATH,
        blocking=True,
        candidates=[Candidate(value=v, evidence=[Evidence(source="/page", snippet=v)]) for v in values],
    )
    corroborate([ambiguity], confirmed)
    assert {c.value: c.corroborated_by for c in ambiguity.candidates if c.corroborated_by} == corroborated_by
    assert ambiguity.resolution == resolution


def test_to_dict_contract() -> None:
    """Serialized shape matches ONBOARDING_SPEC § Ambiguities."""
    ambiguity = Ambiguity(
        field=_PATH,
        blocking=True,
        candidates=[Candidate(value="a", evidence=[Evidence(source="/login.htm", snippet='code==="a"')])],
    )
    assert ambiguity.to_dict() == {
        "field": _PATH,
        "blocking": True,
        "candidates": [
            {
                "value": "a",
                "evidence": [{"source": "/login.htm", "snippet": 'code==="a"'}],
                "corroborated_by": [],
            }
        ],
        "resolution": None,
    }
