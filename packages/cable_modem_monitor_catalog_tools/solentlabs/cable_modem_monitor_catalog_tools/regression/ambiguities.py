"""The regression's stand-in for the LLM: resolve ambiguities from the committed config.

The committed value answers each ambiguity, but only from among the
candidates analysis offered. A committed value the tool never surfaced
is a pipeline failure: intake would have handed the LLM the wrong
evidence. Every ambiguity is graded, so the report shows whether
analysis surfaced the answer and whether it was the only candidate.

A channel key path reads the committed parser.yaml instead. Its
candidates come from other modems, so an unoffered meaning is a new one:
it is applied and graded ``committed_only``, never a failure. An action
path is treated the same way: a capture without the action is normal.

See INTAKE_PIPELINE.md § Intake Pipeline Regression.
"""

from __future__ import annotations

from typing import Any

from ..analysis.ambiguity import split_parser_path
from ..grading import Grade

NONE_REASON = "committed config declares none"


def resolve_from_committed(
    analysis: dict[str, Any], committed: dict[str, Any], committed_parser: dict[str, Any] | None = None
) -> tuple[dict[str, Grade], list[str]]:
    """Set each resolution from the committed value; return per-field grades and the not-surfaced failures."""
    grades: dict[str, Grade] = {}
    failures: list[str] = []
    for ambiguity in analysis.get("ambiguities") or []:
        path = ambiguity["field"]
        offered = [str(c["value"]) for c in ambiguity.get("candidates", [])]
        parser_target = split_parser_path(path)
        value = _key_field(committed_parser or {}, *parser_target) if parser_target else _at_path(committed, path)
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
            listed = ", ".join(offered) or "none"
            grades[path] = Grade("committed_only", f"committed {value} not surfaced (candidates: {listed})")
            # Key meanings come from other modems, and a capture without an action is
            # normal: both grade the gap and continue. Auth codes must be in the capture.
            if parser_target or path.startswith("actions."):
                ambiguity["resolution"] = {"value": value}
            else:
                ambiguity["resolution"] = None
                failures.append(f"committed value not surfaced: {path} = {value} (candidates: {listed})")
    return grades, failures


def _key_field(parser: dict[str, Any], section_name: str, key: str) -> Any:
    """The field a committed section maps ``key`` to, from its first list that declares it, or None."""
    section = parser.get(section_name)
    if not isinstance(section, dict):
        return None
    for holder in [section, *(section.get("arrays") or [])]:
        # json names its list fields; javascript_json names it mappings.
        for mapping in (holder.get("fields") or []) + (holder.get("mappings") or []):
            if mapping.get("key") == key:
                return mapping.get("field")
    return None


def _at_path(config: dict[str, Any], dotted: str) -> Any:
    """The value at a dotted path, or None when any step is absent."""
    node: Any = config
    for key in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node
