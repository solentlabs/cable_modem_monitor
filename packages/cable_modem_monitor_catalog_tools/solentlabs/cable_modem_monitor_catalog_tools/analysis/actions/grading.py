"""Grades pipeline-detected actions against committed modem.yaml actions.

Used by the intake regression to track onboarding capability per action:
how much of each committed action config the deterministic pipeline
reproduces from the HAR alone. Grading covers type, identity (method +
endpoint for http, action_name for hnap), params, and json_body presence.
Other committed fields (pre_fetch_action, action_auth, requires_session,
response keys) are human-authored config outside what a HAR can show —
they are deliberately out of grading scope.
"""

from __future__ import annotations

from typing import Any

from ...grading import Grade


def grade_actions(
    detected: dict[str, Any] | None,
    committed: dict[str, Any] | None,
) -> dict[str, Grade]:
    """Grade logout and restart; actions absent on both sides are skipped."""
    detected = detected or {}
    committed = committed or {}
    grades: dict[str, Grade] = {}
    for kind in ("logout", "restart"):
        grade = grade_action(detected.get(kind), committed.get(kind))
        if grade is not None:
            grades[kind] = grade
    return grades


def grade_action(
    detected: dict[str, Any] | None,
    committed: dict[str, Any] | None,
) -> Grade | None:
    """Grade one detected/committed action pair; None when both absent."""
    if not detected and not committed:
        return None
    if not detected:
        assert committed is not None
        return Grade(
            "committed_only",
            f"committed {committed.get('type', '?')} action not produced by pipeline",
        )
    if not committed:
        return Grade("pipeline_only", f"detected {_identity_str(detected)} absent from committed config")
    if detected.get("type") != committed.get("type"):
        return Grade(
            "mismatch",
            f"type: detected {detected.get('type')} vs committed {committed.get('type')}",
        )
    if _identity(detected) != _identity(committed):
        return Grade(
            "mismatch",
            f"detected {_identity_str(detected)} vs committed {_identity_str(committed)}",
        )
    return _grade_params(detected, committed)


def _identity(action: dict[str, Any]) -> tuple[Any, ...]:
    """What makes two actions the same action."""
    if action.get("type") == "hnap":
        return (action.get("action_name"),)
    return (action.get("method"), action.get("endpoint"))


def _identity_str(action: dict[str, Any]) -> str:
    if action.get("type") == "hnap":
        return f"hnap {action.get('action_name')}"
    return f"{action.get('method')} {action.get('endpoint')}"


def _grade_params(detected: dict[str, Any], committed: dict[str, Any]) -> Grade:
    """Identity already matches — grade the payload."""
    det_params = detected.get("params") or {}
    com_params = committed.get("params") or {}

    # Committed yaml params may be ints/bools; detected are always str.
    missing = sorted(set(com_params) - set(det_params))
    extra = sorted(set(det_params) - set(com_params))
    differ = sorted(k for k in set(det_params) & set(com_params) if str(det_params[k]) != str(com_params[k]))

    notes: list[str] = []
    if missing:
        notes.append(f"params not extracted: {missing}")
    if extra:
        notes.append(f"extra params detected: {extra}")
    if differ:
        notes.append(f"param values differ: {differ}")
    if committed.get("json_body") and not detected.get("json_body"):
        notes.append("json_body not produced")

    if notes:
        return Grade("partial", "; ".join(notes))
    return Grade("match")
