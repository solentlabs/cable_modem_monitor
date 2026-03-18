"""Channel type classification for field mapping.

Detects channel_type configuration from table, transposed table,
JSON, and fixed (direction-based) formats.

Per docs/ONBOARDING_SPEC.md Phase 6.
"""

from __future__ import annotations

from typing import Any

from ..format.types import DetectedTable
from .types import FieldMapping, find_mapping

# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------


def detect_channel_type_table(
    table: DetectedTable,
    mappings: list[FieldMapping],
    direction: str,
) -> dict[str, Any] | None:
    """Detect channel_type config for a standard table.

    Maps only values observed in the HAR.
    """
    mod_mapping = find_mapping(mappings, "modulation")
    if mod_mapping is not None and mod_mapping.index is not None:
        col_idx = mod_mapping.index
        observed_values = set()
        for row in table.rows:
            if col_idx < len(row):
                val = row[col_idx].strip()
                if val:
                    observed_values.add(val)

        if observed_values:
            type_map = _build_modulation_map(observed_values)
            if type_map:
                return {"field": "modulation", "map": type_map}

    # Fallback: fixed type based on DOCSIS 3.0 assumption
    return detect_channel_type_fixed(direction)


def detect_channel_type_transposed(
    table: DetectedTable,
    mappings: list[FieldMapping],
    direction: str,
) -> dict[str, Any] | None:
    """Detect channel_type for a transposed table."""
    # Transposed tables rarely have per-channel type info
    return detect_channel_type_fixed(direction)


def detect_channel_type_json(
    channel_array: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Detect channel_type from JSON channel array."""
    for key_name in ("channelType", "channel_type", "channeltype"):
        observed = set()
        for item in channel_array:
            val = item.get(key_name, "")
            if val:
                observed.add(str(val))
        if observed:
            type_map = _build_channel_type_map(observed)
            if type_map:
                return {"key": key_name, "map": type_map}

    return None


def detect_channel_type_fixed(direction: str) -> dict[str, Any] | None:
    """Default fixed channel type for DOCSIS 3.0 modems."""
    if direction == "downstream":
        return {"fixed": "qam"}
    if direction == "upstream":
        return {"fixed": "atdma"}
    return None


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------


def _build_modulation_map(values: set[str]) -> dict[str, str]:
    """Build modulation value -> channel_type map."""
    result: dict[str, str] = {}
    for val in sorted(values):
        lower = val.lower()
        if "qam" in lower and "ofdm" not in lower:
            result[val] = "qam"
        elif "ofdm" in lower or lower == "other":
            result[val] = "ofdm"
        elif "atdma" in lower:
            result[val] = "atdma"
        elif "ofdma" in lower:
            result[val] = "ofdma"
    return result


def _build_channel_type_map(values: set[str]) -> dict[str, str]:
    """Build channelType value -> canonical type map."""
    result: dict[str, str] = {}
    for val in sorted(values):
        lower = val.lower().replace("-", "").replace("_", "")
        if "scqam" in lower or ("qam" in lower and "ofdm" not in lower):
            result[val] = "qam"
        elif "ofdma" in lower:
            result[val] = "ofdma"
        elif "ofdm" in lower:
            result[val] = "ofdm"
        elif "atdma" in lower:
            result[val] = "atdma"
    return result
