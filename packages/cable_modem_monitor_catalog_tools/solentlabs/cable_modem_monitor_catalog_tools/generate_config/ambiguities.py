"""Ambiguity resolutions: apply resolved values; refuse unresolved blocking ones.

A resolution is the LLM's judgment from the evidence analysis cited,
confirmed by the user. ``{value}`` lands at the ambiguity's dotted path;
``{value: null, reason}`` is an explicit "none" and leaves the field
absent. A blocking ambiguity with no resolution stops generation.

Per docs/ONBOARDING_SPEC.md § Ambiguities.
"""

from __future__ import annotations

from typing import Any


def apply_resolutions(analysis: dict[str, Any], modem_dict: dict[str, Any], errors: list[str]) -> None:
    """Write each resolved value into modem_dict; record an error for every blocking gap."""
    for ambiguity in analysis.get("ambiguities") or []:
        path = ambiguity["field"]
        resolution = ambiguity.get("resolution")
        if resolution is None:
            if ambiguity.get("blocking"):
                values = ", ".join(c["value"] for c in ambiguity.get("candidates", [])) or "none found"
                errors.append(
                    f"unresolved ambiguity {path} (candidates: {values}); "
                    "resolve it from the cited evidence before generating"
                )
            continue
        value = resolution.get("value")
        if value is None:
            # A bare null is a blank; only a stated reason makes "none" a judgment.
            if not resolution.get("reason"):
                errors.append(f"{path} resolves to none without a reason; an explicit none must say why")
            continue
        _set_path(modem_dict, path, value)


def _set_path(target: dict[str, Any], dotted: str, value: Any) -> None:
    """Set ``value`` at a dotted path, creating intermediate mappings."""
    *parents, leaf = dotted.split(".")
    node = target
    for key in parents:
        node = node.setdefault(key, {})
    node[leaf] = value
