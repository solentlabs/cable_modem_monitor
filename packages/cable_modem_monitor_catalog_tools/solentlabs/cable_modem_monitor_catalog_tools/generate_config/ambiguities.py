"""Ambiguity resolutions: apply resolved values; refuse unresolved blocking ones.

A resolution is the LLM's judgment from the evidence analysis cited,
confirmed by the user. ``{value}`` lands at the ambiguity's dotted path;
``{value: null, reason}`` is an explicit "none" and leaves the field
absent. A blocking ambiguity with no resolution stops generation.

A ``parser.<section>.<key>`` path names a channel JSON key: its value is
the key's field, written into the analysis sections before parser.yaml
is built. None, or no resolution, drops the key.

Per docs/ONBOARDING_SPEC.md § Ambiguities.
"""

from __future__ import annotations

from typing import Any

from ..analysis.ambiguity import split_parser_path
from ..analysis.mapping.field_resolution import known_field_type


def apply_resolutions(
    analysis: dict[str, Any],
    modem_dict: dict[str, Any],
    sections: dict[str, Any] | None,
    errors: list[str],
) -> None:
    """Write each resolved value into modem_dict or sections; record an error for every blocking gap."""
    for ambiguity in analysis.get("ambiguities") or []:
        path = ambiguity["field"]
        value = _resolved_value(ambiguity, errors)
        parser_target = split_parser_path(path)
        if parser_target is not None:
            _set_key_field(sections or {}, parser_target, value, path, errors)
        elif value is not None:
            _set_path(modem_dict, path, value)


def _resolved_value(ambiguity: dict[str, Any], errors: list[str]) -> Any:
    """The resolved value, or None for none and unresolved; errors for blanks and blocking gaps."""
    path = ambiguity["field"]
    resolution = ambiguity.get("resolution")
    if resolution is None:
        if ambiguity.get("blocking"):
            values = ", ".join(c["value"] for c in ambiguity.get("candidates", [])) or "none found"
            errors.append(
                f"unresolved ambiguity {path} (candidates: {values}); "
                "resolve it from the cited evidence before generating"
            )
        return None
    value = resolution.get("value")
    # A bare null is a blank; only a stated reason makes "none" a judgment.
    if value is None and not resolution.get("reason"):
        errors.append(f"{path} resolves to none without a reason; an explicit none must say why")
    return value


def _set_key_field(sections: dict[str, Any], target: tuple[str, str], value: Any, path: str, errors: list[str]) -> None:
    """Map a section's channel key to ``value``, or drop the key when it is None."""
    section_name, key = target
    section = sections.get(section_name)
    if not isinstance(section, dict):
        section = {}
    mappings = section.get("mappings", [])
    matches = [m for m in mappings if m.get("key") == key]
    if not matches:
        errors.append(f"{path}: the analysis maps no such channel key")
        return
    if value is None:
        section["mappings"] = [m for m in mappings if m.get("key") != key]
        return
    for mapping in matches:
        mapping["field"] = value
        # A known field has one type; a new meaning keeps the type its values showed.
        mapping["type"] = known_field_type(value) or mapping["type"]


def _set_path(target: dict[str, Any], dotted: str, value: Any) -> None:
    """Set ``value`` at a dotted path, creating intermediate mappings."""
    *parents, leaf = dotted.split(".")
    node = target
    for key in parents:
        node = node.setdefault(key, {})
    node[leaf] = value
