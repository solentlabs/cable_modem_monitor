"""Channel JSON keys the fleet has mapped: one meaning is learned, several are an ambiguity.

The baseline registry maps first. A key it leaves at Tier 3 takes the
field committed parser.yaml files declare for it; when they declare
different fields, the key stays at Tier 3 and the LLM judges it.

Per docs/ONBOARDING_SPEC.md § Ambiguities (Channel key meanings).
"""

from __future__ import annotations

from typing import Any

from ..ambiguity import Ambiguity, Candidate, Evidence, parser_path
from ..types import FleetPatterns
from .types import SectionDetail

# Enough distinct capture values to show what a key holds, without
# listing every channel's frequency.
_MAX_SAMPLE_VALUES = 5


def learned_field(key: str, fleet: FleetPatterns | None) -> str:
    """The one field the fleet declares for ``key``; empty when it declares none or several."""
    meanings = _meanings(key, fleet)
    return next(iter(meanings)) if len(meanings) == 1 else ""


def key_candidates(
    key: str, channels: list[dict[str, Any]], resource: str, fleet: FleetPatterns | None
) -> list[Candidate]:
    """One candidate per fleet meaning when the fleet disagrees on ``key``; empty otherwise."""
    meanings = _meanings(key, fleet)
    if len(meanings) < 2:
        return []
    capture = Evidence(source=resource, snippet=f'"{key}": {_sample_values(key, channels)}')
    normalized = key.strip().lower()
    return [
        Candidate(
            value=field_name,
            evidence=[Evidence(f"{entry}/parser.yaml", f"{normalized} → {field_name}") for entry in entries]
            + [capture],
        )
        for field_name, entries in sorted(meanings.items())
    ]


def address_key_ambiguities(section: SectionDetail, direction: str, ambiguities: list[Ambiguity] | None) -> None:
    """Raise the section's contested keys as non-blocking ambiguities, once its direction is known."""
    if ambiguities is None:
        return
    for key, candidates in section.contested_keys:
        ambiguities.append(Ambiguity(field=parser_path(direction, key), blocking=False, candidates=candidates))


def _meanings(key: str, fleet: FleetPatterns | None) -> dict[str, list[str]]:
    """Each field the fleet declares for ``key``, with its declaring entries."""
    if fleet is None:
        return {}
    return fleet.channel_json_keys.get(key.strip().lower(), {})


def _sample_values(key: str, channels: list[dict[str, Any]]) -> str:
    """The capture's distinct values for ``key``, in channel order."""
    seen: list[str] = []
    for channel in channels:
        value = channel.get(key) if isinstance(channel, dict) else None
        if value is not None and str(value) not in seen:
            seen.append(str(value))
    return ", ".join(seen[:_MAX_SAMPLE_VALUES])
