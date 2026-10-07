"""The regression grades an action resolved from candidates as the whole candidate.

Pins INTAKE_PIPELINE.md § Intake Pipeline Regression: an HTTP action the
pipeline offered as an endpoint candidate is resolved from the committed
config, then graded as the candidate's full request, not a bare endpoint.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.regression.ambiguities import resolve_from_committed
from solentlabs.cable_modem_monitor_catalog_tools.regression.results import ModemResult

# The regression runner is a script, not an installed module, so load it by path.
_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "intake_pipeline_regression.py"
_spec = importlib.util.spec_from_file_location("intake_pipeline_regression", _SCRIPT)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
_grade_actions_stage = _module._grade_actions_stage

_CANDIDATE = {
    "type": "http",
    "method": "PUT",
    "endpoint": "/actionHandler/ajaxSet_signout.php",
    "source": "observed",
    "json_body": {"DoLogOut": 1},
}
_COMMITTED_SAME = {"type": "http", "method": "PUT", "endpoint": _CANDIDATE["endpoint"], "json_body": {"DoLogOut": 1}}
_COMMITTED_ELSEWHERE = {**_COMMITTED_SAME, "endpoint": "/logout"}


def _analysis() -> dict[str, Any]:
    """No logout detected; one observed logout candidate."""
    return {
        "transport": "http",
        "actions": {"logout": None, "restart": None, "candidates": {"logout": {_CANDIDATE["endpoint"]: _CANDIDATE}}},
        "ambiguities": [
            {
                "field": "actions.logout.endpoint",
                "blocking": False,
                "candidates": [{"value": _CANDIDATE["endpoint"], "evidence": [], "corroborated_by": []}],
                "resolution": None,
            }
        ],
    }


# ┌──────────────────────┬────────────────┬──────────────────────────────────────┐
# │ committed logout     │ grade          │ description                          │
# ├──────────────────────┼────────────────┼──────────────────────────────────────┤
# │ the candidate        │ match          │ resolved, graded as the full request │
# │ another endpoint     │ committed_only │ not surfaced, nothing to grade       │
# └──────────────────────┴────────────────┴──────────────────────────────────────┘
#
# fmt: off
CASES: list[tuple[dict[str, Any], str, str]] = [
    # (committed logout,        grade,             id)
    (_COMMITTED_SAME,           "match",           "candidate-resolved"),
    (_COMMITTED_ELSEWHERE,      "committed_only",  "not-surfaced"),
]
# fmt: on


@pytest.mark.parametrize(("committed_logout", "grade"), [(c, g) for c, g, _ in CASES], ids=[c[2] for c in CASES])
def test_resolved_candidate_graded_whole(committed_logout: dict[str, Any], grade: str) -> None:
    """The grade sees the candidate's method and body, as generate_config would write them."""
    analysis = _analysis()
    committed = {"actions": {"logout": committed_logout}}
    resolve_from_committed(analysis, committed)
    result = ModemResult(modem="vendor/model", har_file="modem.har")
    _grade_actions_stage(result, analysis, committed)
    assert result.grades["actions"]["logout"].status == grade
