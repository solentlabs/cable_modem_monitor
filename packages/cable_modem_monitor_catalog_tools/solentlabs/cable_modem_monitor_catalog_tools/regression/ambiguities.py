"""The regression's stand-in for the LLM: resolve ambiguities from the committed config.

The committed value answers each ambiguity, but only from among the
candidates analysis offered. A committed value the tool never surfaced
is a pipeline failure: intake would have handed the LLM the wrong
evidence. Every ambiguity is graded, so the report shows whether
analysis surfaced the answer and whether it was the only candidate.

See INTAKE_PIPELINE.md § Intake Pipeline Regression.
"""

from __future__ import annotations

from typing import Any

from ..grading import Grade

NONE_REASON = "committed config declares none"


def resolve_from_committed(analysis: dict[str, Any], committed: dict[str, Any]) -> tuple[dict[str, Grade], list[str]]:
    """Set each resolution from the committed value; return per-field grades and the not-surfaced failures."""
    grades: dict[str, Grade] = {}
    failures: list[str] = []
    for ambiguity in analysis.get("ambiguities") or []:
        path = ambiguity["field"]
        offered = [str(c["value"]) for c in ambiguity.get("candidates", [])]
        value = _at_path(committed, path)
        if value is None:
            ambiguity["resolution"] = {"value": None, "reason": NONE_REASON}
            grades[path] = (
                Grade("pipeline_only", f"committed declares none; {len(offered)} candidates offered")
                if offered
                else Grade("match", "none offered, none declared")
            )
        elif str(value) in offered:
            ambiguity["resolution"] = {"value": value}
            grades[path] = (
                Grade("match", "surfaced, only candidate")
                if len(offered) == 1
                else Grade("partial", f"surfaced among {len(offered)} candidates")
            )
        else:
            ambiguity["resolution"] = None
            listed = ", ".join(offered) or "none"
            grades[path] = Grade("committed_only", f"committed {value} not surfaced (candidates: {listed})")
            failures.append(f"committed value not surfaced: {path} = {value} (candidates: {listed})")
    return grades, failures


def _at_path(config: dict[str, Any], dotted: str) -> Any:
    """The value at a dotted path, or None when any step is absent."""
    node: Any = config
    for key in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node
