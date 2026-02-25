"""Channel normalization and lookup utilities.

Provides functions for:
- Normalizing channel types (QAM/OFDM for downstream, ATDMA/OFDMA for upstream)
- Extracting channel IDs from various formats
- Indexing channels for O(1) lookup by (type, id) tuple
- Grouping channels by type for dashboard generation
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def normalize_channel_type(channel: dict[str, Any], direction: str) -> str:
    """Normalize channel type from parser data.

    Maps raw parser values to standardized types:
    - Downstream: 'qam' (DOCSIS 3.0) or 'ofdm' (DOCSIS 3.1)
    - Upstream: 'atdma' (DOCSIS 3.0) or 'ofdma' (DOCSIS 3.1)

    Checks fields in order: channel_type, modulation, is_ofdm flag.
    Falls back to 'qam'/'atdma' if type cannot be determined.
    """
    # Check explicit channel_type first (e.g., "ATDMA", "OFDMA", "qam", "ofdm")
    channel_type = channel.get("channel_type", "").lower()
    modulation = channel.get("modulation", "").lower()
    is_ofdm = channel.get("is_ofdm", False)

    if direction == "downstream":
        if channel_type == "ofdm" or "ofdm" in modulation or is_ofdm:
            return "ofdm"
        return "qam"  # Default for DOCSIS 3.0 or unspecified
    else:  # upstream
        if channel_type == "ofdma" or "ofdma" in modulation or is_ofdm:
            return "ofdma"
        return "atdma"  # Default for DOCSIS 3.0 or unspecified


def extract_channel_id(channel: dict[str, Any], default: int) -> int:
    """Extract numeric channel ID from channel data.

    Handles both numeric IDs ("1", "32") and prefixed IDs ("OFDM-0", "OFDMA-1").
    For prefixed IDs, extracts the number after the dash.

    Args:
        channel: Channel data dict with channel_id or channel field
        default: Default value if parsing fails

    Returns:
        Numeric channel ID
    """
    ch_id = channel.get("channel_id", channel.get("channel"))
    if ch_id is None:
        return default

    # Already numeric
    if isinstance(ch_id, int):
        return ch_id

    # String - try direct conversion first
    ch_id_str = str(ch_id).strip()
    try:
        return int(ch_id_str)
    except ValueError:
        pass

    # Try extracting number after dash (e.g., "OFDM-0" -> 0)
    if "-" in ch_id_str:
        try:
            return int(ch_id_str.split("-")[-1])
        except ValueError:
            pass

    return default


def normalize_channels(channels: list[dict[str, Any]], direction: str) -> dict[tuple[str, int], dict[str, Any]]:
    """Normalize and index channels by (type, id) tuple.

    Groups channels by type, sorts by frequency within each type,
    and assigns stable indices based on frequency order.

    Returns dict mapping (channel_type, channel_id) -> channel data with added metadata.
    """
    # Group channels by type
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for idx, ch in enumerate(channels):
        ch_type = normalize_channel_type(ch, direction)
        ch_id = extract_channel_id(ch, idx + 1)
        by_type[ch_type].append({**ch, "_channel_type": ch_type, "_channel_id": ch_id})

    # Sort each type by frequency and assign index
    result: dict[tuple[str, int], dict[str, Any]] = {}
    for _channel_type, group in by_type.items():
        # Sort by frequency (use 0 if not present)
        sorted_group = sorted(group, key=lambda x: float(x.get("frequency", 0) or 0))
        for index, ch in enumerate(sorted_group):
            ch["_index"] = index + 1  # 1-based index
            key = (ch["_channel_type"], ch["_channel_id"])
            result[key] = ch

    return result


def get_channel_info(
    coordinator,
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Extract downstream and upstream channel info from coordinator data.

    Returns tuples of (channel_type, channel_id) for each direction.
    """
    downstream_info: list[tuple[str, int]] = []
    upstream_info: list[tuple[str, int]] = []

    if not coordinator.data:
        return downstream_info, upstream_info

    if "_downstream_by_id" in coordinator.data:
        # Keys are already (channel_type, channel_id) tuples
        downstream_info = sorted(coordinator.data["_downstream_by_id"].keys())
    elif "cable_modem_downstream" in coordinator.data:
        for idx, ch in enumerate(coordinator.data["cable_modem_downstream"]):
            ch_type = normalize_channel_type(ch, "downstream")
            ch_id = extract_channel_id(ch, idx + 1)
            downstream_info.append((ch_type, ch_id))
        downstream_info = sorted(downstream_info)

    if "_upstream_by_id" in coordinator.data:
        # Keys are already (channel_type, channel_id) tuples
        upstream_info = sorted(coordinator.data["_upstream_by_id"].keys())
    elif "cable_modem_upstream" in coordinator.data:
        for idx, ch in enumerate(coordinator.data["cable_modem_upstream"]):
            ch_type = normalize_channel_type(ch, "upstream")
            ch_id = extract_channel_id(ch, idx + 1)
            upstream_info.append((ch_type, ch_id))
        upstream_info = sorted(upstream_info)

    return downstream_info, upstream_info


def group_channels_by_type(
    channel_info: list[tuple[str, int]],
) -> dict[str, list[tuple[str, int]]]:
    """Group channels by their type.

    Returns dict mapping channel_type -> list of (channel_type, channel_id) tuples.
    """
    grouped: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for ch_type, ch_id in channel_info:
        grouped[ch_type].append((ch_type, ch_id))
    return dict(grouped)


def get_channel_types(channel_info: list[tuple[str, int]]) -> set[str]:
    """Get unique channel types from channel info."""
    return {ch_type for ch_type, _ in channel_info}
