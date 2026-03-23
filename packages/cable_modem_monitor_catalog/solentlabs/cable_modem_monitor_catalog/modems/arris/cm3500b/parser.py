"""Post-processor for ARRIS CM3500B — OFDM channel enrichment.

Handles two things that parser.yaml cannot express:

1. **OFDM center frequency** — computed from first/last subcarrier
   frequencies (both in MHz, averaged and converted to Hz).
2. **OFDM channel ID formatting** — ``OFDM-N`` / ``OFDMA-N`` from
   the label text (``"Downstream 1"`` → ``"OFDM-1"``).

System info extraction is handled by parser.yaml (html_fields format).
"""

from __future__ import annotations

import re
from typing import Any

# Regex to extract channel number from OFDM label ("Downstream 1" → "1")
_LABEL_RE = re.compile(r"(?:Downstream|Upstream)\s*(\d+)")


class PostProcessor:
    """OFDM/OFDMA post-processor for CM3500B."""

    def parse_downstream(
        self,
        channels: list[dict[str, Any]],
        resources: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Enrich downstream OFDM channels with computed fields."""
        for ch in channels:
            if ch.get("channel_type") == "ofdm":
                _enrich_ofdm_channel(ch, prefix="OFDM")
        return channels

    def parse_upstream(
        self,
        channels: list[dict[str, Any]],
        resources: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Enrich upstream OFDMA channels with computed fields."""
        for ch in channels:
            if ch.get("channel_type") == "ofdma":
                _enrich_ofdm_channel(ch, prefix="OFDMA")
        return channels


def _enrich_ofdm_channel(channel: dict[str, Any], *, prefix: str) -> None:
    """Compute center frequency and format channel ID for an OFDM channel.

    Modifies the channel dict in place:
    - ``channel_id``: formatted as ``{prefix}-{N}`` from the label.
    - ``frequency``: center of first/last subcarrier in Hz.
    - ``is_ofdm``: set to ``True``.
    - ``modulation``: set to the prefix value.
    - ``ofdm_label``: removed (intermediate field).
    """
    # Format channel_id from label
    label = channel.pop("ofdm_label", "")
    match = _LABEL_RE.search(str(label))
    channel_num = match.group(1) if match else "0"
    channel["channel_id"] = f"{prefix}-{channel_num}"

    # Compute center frequency from first/last subcarrier (both in MHz)
    first_mhz = channel.pop("first_subcarrier_freq", None)
    last_mhz = channel.pop("last_subcarrier_freq", None)
    if first_mhz is not None and last_mhz is not None:
        center_mhz = (float(first_mhz) + float(last_mhz)) / 2
        channel["frequency"] = int(center_mhz * 1_000_000)

    channel["is_ofdm"] = True
    channel["modulation"] = prefix
