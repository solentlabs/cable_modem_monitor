"""Channel mapping manager — translates Core channel lists to HA entity slots.

Pure module with no HA imports.  The mapping manager reads the user's
channel identity mode and builds slot maps that sensor entities use for
O(1) lookup.

See CHANNEL_IDENTIFICATION_SPEC.md § 5, § 10.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import ChannelIdentity

# Slot key types per mode:
#   Position mode: int (channel_number)
#   ID mode: tuple[str, int | str] (channel_type, channel_id)
SlotKey = int | tuple[str, int | str]


@dataclass
class ChannelMap:
    """Downstream and upstream slot maps for entity lookup."""

    downstream: dict[SlotKey, dict[str, Any]] = field(default_factory=dict)
    upstream: dict[SlotKey, dict[str, Any]] = field(default_factory=dict)


def _null_unlocked(ch: dict[str, Any]) -> dict[str, Any]:
    """Return a nulled channel dict for an unlocked position.

    Only channel_number and lock_status are preserved.
    All other fields are set to None.
    """
    nulled: dict[str, Any] = {key: None for key in ch}
    nulled["channel_number"] = ch["channel_number"]
    nulled["lock_status"] = ch["lock_status"]
    return nulled


def _build_direction_slots(
    channels: list[dict[str, Any]],
    mode: ChannelIdentity,
) -> dict[SlotKey, dict[str, Any]]:
    """Build slot map for one direction (downstream or upstream)."""
    slots: dict[SlotKey, dict[str, Any]] = {}

    for ch in channels:
        is_locked = ch.get("lock_status") == "locked"

        if mode == ChannelIdentity.NUMBER:
            ch_num = ch.get("channel_number")
            if ch_num is None:
                continue
            slots[ch_num] = ch if is_locked else _null_unlocked(ch)

        else:
            # ID mode — unlocked channels excluded (no valid key)
            if not is_locked:
                continue
            ch_type = ch.get("channel_type")
            ch_id = ch.get("channel_id")
            if ch_type is None or ch_id is None:
                continue
            slots[(ch_type, ch_id)] = ch

    return slots


def build_channel_map(
    downstream: list[dict[str, Any]],
    upstream: list[dict[str, Any]],
    mode: ChannelIdentity,
) -> ChannelMap:
    """Build slot maps from Core's channel lists.

    Args:
        downstream: Downstream channel dicts from modem_data.
        upstream: Upstream channel dicts from modem_data.
        mode: The user's channel identity selection.

    Returns:
        ChannelMap with downstream and upstream dicts keyed by slot.
    """
    return ChannelMap(
        downstream=_build_direction_slots(downstream, mode),
        upstream=_build_direction_slots(upstream, mode),
    )
