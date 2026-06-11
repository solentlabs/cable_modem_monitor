"""Grades the pipeline-generated auth block against the committed modem.yaml auth.

Two graded items: ``strategy`` (the detected auth strategy is the
headline capability) and ``fields`` (the rest of the auth block —
endpoints, field names, cookie names, nested success criteria). Fields
are only graded when the strategy matches; comparing field layouts of
two different strategies is meaningless.
"""

from __future__ import annotations

from typing import Any

from ...grading import Grade


def grade_auth(
    generated: dict[str, Any] | None,
    committed: dict[str, Any] | None,
) -> dict[str, Grade]:
    """Grade one generated/committed auth pair; empty when both absent."""
    if not generated and not committed:
        return {}
    if not generated:
        assert committed is not None
        return {
            "strategy": Grade(
                "committed_only",
                f"committed {committed.get('strategy', '?')} auth not produced by pipeline",
            )
        }
    if not committed:
        return {
            "strategy": Grade(
                "pipeline_only",
                f"generated {generated.get('strategy', '?')} auth absent from committed config",
            )
        }

    gen_strategy = generated.get("strategy")
    com_strategy = committed.get("strategy")
    if gen_strategy != com_strategy:
        return {
            "strategy": Grade("mismatch", f"detected {gen_strategy} vs committed {com_strategy}"),
        }

    return {"strategy": Grade("match"), "fields": _grade_fields(generated, committed)}


def _grade_fields(generated: dict[str, Any], committed: dict[str, Any]) -> Grade:
    """Strategy already matches — grade everything else in the block."""
    gen_fields = {k: v for k, v in generated.items() if k != "strategy"}
    com_fields = {k: v for k, v in committed.items() if k != "strategy"}

    missing = sorted(set(com_fields) - set(gen_fields))
    extra = sorted(set(gen_fields) - set(com_fields))
    differ = sorted(k for k in set(gen_fields) & set(com_fields) if gen_fields[k] != com_fields[k])

    notes: list[str] = []
    if missing:
        notes.append(f"fields not produced: {missing}")
    if extra:
        notes.append(f"extra fields generated: {extra}")
    if differ:
        notes.append(f"field values differ: {differ}")

    if notes:
        return Grade("partial", "; ".join(notes))
    return Grade("match")
