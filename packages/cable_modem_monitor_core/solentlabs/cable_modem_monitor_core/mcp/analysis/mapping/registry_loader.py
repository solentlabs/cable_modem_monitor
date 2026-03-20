"""Load field registry from JSON and build lookup maps.

Single source of truth for header-to-field, JSON-key-to-field, and
channel label detection. All maps are derived from ``field_registry.json``.

Per docs/FIELD_REGISTRY.md three-tier system.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REGISTRY_PATH = Path(__file__).parent / "field_registry.json"

# Module-level cache — loaded once on first access
_registry: dict[str, Any] | None = None


def _load_registry() -> dict[str, Any]:
    """Load and cache the field registry JSON."""
    global _registry  # noqa: PLW0603
    if _registry is None:
        _registry = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    return _registry


def get_header_field_map() -> dict[str, tuple[str, int]]:
    """Build header-text -> (field_name, tier) lookup.

    Includes both plain headers and unit-bearing variants
    from ``header_units``.
    """
    registry = _load_registry()
    result: dict[str, tuple[str, int]] = {}

    for field_name, spec in registry["fields"].items():
        tier: int = spec["tier"]
        for header in spec.get("headers", []):
            result[header] = (field_name, tier)
        for header in spec.get("header_units", {}):
            result[header] = (field_name, tier)

    return result


def get_json_key_map() -> dict[str, tuple[str, int]]:
    """Build JSON-key -> (field_name, tier) lookup."""
    registry = _load_registry()
    result: dict[str, tuple[str, int]] = {}

    for field_name, spec in registry["fields"].items():
        tier: int = spec["tier"]
        for key in spec.get("json_keys", []):
            result[key] = (field_name, tier)

    return result


def get_header_unit_map() -> dict[str, str]:
    """Build header-text -> unit lookup for unit-bearing headers.

    Only headers with an explicit unit are included.
    Example: ``"freq. (mhz)"`` -> ``"MHz"``.
    """
    registry = _load_registry()
    result: dict[str, str] = {}

    for spec in registry["fields"].values():
        for header, unit in spec.get("header_units", {}).items():
            result[header] = unit

    return result


def get_channel_field_labels() -> tuple[str, ...]:
    """Build tuple of all known channel-data header labels.

    Used by table classification to detect whether a table
    contains channel data.
    """
    registry = _load_registry()
    labels: list[str] = []

    for spec in registry["fields"].values():
        labels.extend(spec.get("headers", []))
        labels.extend(spec.get("header_units", {}).keys())

    return tuple(sorted(set(labels)))


def get_field_type_map() -> dict[str, str]:
    """Build field_name -> type_name lookup."""
    registry = _load_registry()
    return {name: spec["type"] for name, spec in registry["fields"].items()}
