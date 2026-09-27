"""Post-processor for SDMC NE6037: OFDM lower-edge frequency.

The firmware reports an OFDM channel's band as "Carrier Zero" (the
frequency of subcarrier 0, Hz), "First Carrier" (the first active
subcarrier's index) and "Spacing" (kHz), per the docssignal.htm grid
labels. Subcarrier k sits at ``zero + k * spacing``, so the lower edge
of the active band is ``zero + first * spacing`` (FIELD_REGISTRY.md
§ frequency semantics). The firmware's ``frequency`` key is not that
edge and is not mapped.
"""

from __future__ import annotations

from typing import Any

# parser.yaml maps these only to compute frequency; none is output.
_OFDM_INPUTS = ("carrier_zero_frequency", "first_active_subcarrier", "subcarrier_spacing")


class PostProcessor:
    """OFDM post-processor for NE6037."""

    def parse_downstream(
        self,
        channels: list[dict[str, Any]],
        resources: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Set each OFDM channel's frequency to the lower edge of its active band."""
        for ch in channels:
            if ch.get("channel_type") == "ofdm":
                zero, first, spacing_khz = (ch.pop(key, None) for key in _OFDM_INPUTS)
                if zero is not None and first is not None and spacing_khz is not None:
                    ch["frequency"] = zero + first * spacing_khz * 1000
        return channels
