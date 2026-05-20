"""Channel type classification for field mapping.

Detects channel_type configuration from table, transposed table,
JSON, and fixed (direction-based) formats.

Per docs/ONBOARDING_SPEC.md Phase 6.
"""

from __future__ import annotations

from typing import Any

from solentlabs.cable_modem_monitor_core.spec_conformance import canonicalize_modulation

from ..format.types import DetectedTable
from .types import FieldMapping

# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------


def _collect_col_values(table: DetectedTable, col_idx: int) -> set[str]:
    """Return non-empty stripped values from a single column across all rows."""
    return {row[col_idx].strip() for row in table.rows if col_idx < len(row) and row[col_idx].strip()}


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

    Priority order:
    1. Dedicated ``channel_type`` column — normalize values (ATDMA→atdma,
       etc.) and return ``{index, map}``.  The caller removes the raw
       mapping from the columns list so the enriched version is not
       duplicated.
    2. Modulation column (downstream only) — QAM/OFDM values imply
       channel type.  Upstream modulation (e.g., QAM64 on ATDMA channels)
       does NOT indicate channel type and is skipped.
    3. Fixed fallback per direction (downstream → qam, upstream → atdma).
    """
    # 1. Dedicated channel_type column takes precedence
    ct_mapping = FieldMapping.find_by(mappings, "channel_type")
    if ct_mapping is not None and ct_mapping.index is not None:
        observed_values = _collect_col_values(table, ct_mapping.index)
        if observed_values:
            type_map = _build_channel_type_map(observed_values)
            if type_map:
                return {"index": ct_mapping.index, "map": type_map}

    # 2. Modulation-derived (downstream only — upstream QAM64 ≠ qam channel type)
    if direction != "upstream":
        mod_mapping = FieldMapping.find_by(mappings, "modulation")
        if mod_mapping is not None and mod_mapping.index is not None:
            observed_values = _collect_col_values(table, mod_mapping.index)
            if observed_values:
                type_map = _build_modulation_map(observed_values)
                if type_map:
                    return {"field": "modulation", "map": type_map}

    # 3. Fallback: fixed type based on DOCSIS 3.0 assumption
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
    """Detect channel_type from JSON channel array.

    Uses case-insensitive key lookup so that ``ChannelType``,
    ``channelType``, and ``channeltype`` are all recognised.
    Returns the original-cased key so generated configs match the
    source data exactly.
    """
    if not channel_array:
        return None

    # Find the original-cased key from the first item
    ct_key: str | None = None
    for key in channel_array[0]:
        if key.lower().replace("_", "") == "channeltype":
            ct_key = key
            break

    if ct_key is None:
        return None

    observed: set[str] = set()
    for item in channel_array:
        val = item.get(ct_key, "")
        if val:
            observed.add(str(val))

    if observed:
        type_map = _build_channel_type_map(observed)
        if type_map:
            return {"key": ct_key, "map": type_map}

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
    """Build modulation value -> channel_type map.

    Map keys use the canonical modulation form (``QAM256`` not ``256QAM``)
    because Core normalizes modulation values before applying the map
    lookup — a raw ``256QAM`` becomes ``QAM256`` in the parsed field,
    so the map key must match the normalized form to be found.
    """
    result: dict[str, str] = {}
    for val in sorted(values):
        lower = val.lower()
        # Use canonical form as key; fall back to raw for non-QAM values
        # (OFDM, OFDMA, ATDMA) that canonicalize_modulation returns None for.
        canonical_key = canonicalize_modulation(val) or val
        if "qam" in lower and "ofdm" not in lower:
            result[canonical_key] = "qam"
        elif "ofdma" in lower:
            result[canonical_key] = "ofdma"
        elif "ofdm" in lower or lower == "other":
            result[canonical_key] = "ofdm"
        elif "atdma" in lower:
            result[canonical_key] = "atdma"
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
