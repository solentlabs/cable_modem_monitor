"""Post-processor for ARRIS CM3500B — OFDM channel enrichment.

Computes OFDM center frequency from first/last subcarrier frequencies
(both in MHz, averaged and converted to Hz). parser.yaml cannot
express computed fields across two source columns.

``channel_id`` is set from ``source_channel_number`` — the label
index extracted by parser.yaml (``"Downstream 1"`` → ``1``). The
CM3500B firmware does not expose OFDM DCIDs.

System info extraction is handled by parser.yaml (html_fields format).
"""

from __future__ import annotations

from typing import Any


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
                _enrich_ofdm_channel(ch)
        return channels

    def parse_upstream(
        self,
        channels: list[dict[str, Any]],
        resources: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Enrich upstream OFDMA channels with computed fields."""
        for ch in channels:
            if ch.get("channel_type") == "ofdma":
                _enrich_ofdm_channel(ch)
        return channels


def _enrich_ofdm_channel(channel: dict[str, Any]) -> None:
    """Compute center frequency and set channel ID for an OFDM channel.

    Modifies the channel dict in place:
    - ``channel_id``: from ``source_channel_number`` (label index).
    - ``frequency``: center of first/last subcarrier in Hz.
    """
    # Use label index as channel_id (no DCID available in firmware)
    channel["channel_id"] = channel.get("source_channel_number", 0)

    # Compute center frequency from first/last subcarrier (both in MHz)
    first_mhz = channel.pop("first_subcarrier_freq", None)
    last_mhz = channel.pop("last_subcarrier_freq", None)
    if first_mhz is not None and last_mhz is not None:
        center_mhz = (float(first_mhz) + float(last_mhz)) / 2
        channel["frequency"] = int(center_mhz * 1_000_000)
