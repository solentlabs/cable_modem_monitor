"""PostProcessor for Sercomm DM1000 — OFDMA and system_info extraction.

Extends the parser.yaml-driven extraction with two hooks:

- ``parse_upstream``: appends OFDMA channels from RF_US_31_param. The
  pivot from name+indexN rows is delegated to Core via the public
  ``post_processor_helpers.transpose_indexed_rows`` helper; this hook
  keeps only the firmware-specific filter (``Power == "ON"`` and
  ``"OPERATE" in STATE``) and the OFDMA channel build.
- ``parse_system_info``: extracts firmware, hardware, vendor, and
  build info from Version_Info (prefix-parsing — can't be expressed
  declaratively).

OFDM downstream channels are fully declarative in parser.yaml via
per-array resources.
"""

from __future__ import annotations

import re
from typing import Any

from solentlabs.cable_modem_monitor_core.post_processor_helpers import (
    transpose_indexed_rows,
)

# Resource endpoints.
_VERSION_INFO = "/setup.cgi?todo=Version_Info"
_OFDMA_US = "/setup.cgi?todo=RF_US_31_param"

# Maps "info" field prefixes to system_info field names.
_INFO_PREFIX_MAP = {
    "HW_REV ": "hardware_version",
    "SW_REV ": "software_version",
    "MODEL ": "model_name",
    "VENDOR ": "vendor",
    "BOOTR ": "bootloader_version",
}

# Pattern to detect the DOCSIS description line (e.g.,
# "Docsis 3.1/DOCSIS 3.1 Cable Modem").
_DOCSIS_RE = re.compile(r"DOCSIS", re.IGNORECASE)


class PostProcessor:
    """Extract OFDMA upstream channels and enrich system_info."""

    # Resources the hooks read — nothing in parser.yaml maps these;
    # the orchestrator merges them into the fetch list (PARSING_SPEC).
    resources = {
        _VERSION_INFO: "json",
        _OFDMA_US: "json",
    }

    def parse_upstream(
        self,
        channels: list[dict[str, Any]],
        resources: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Append OFDMA upstream channels from RF_US_31_param.

        Only active channels (Power=ON, STATE contains OPERATE) are
        included. The STATE substring check is firmware-specific and
        not expressible via declarative ``filter:`` operators today.
        """
        rows = resources.get(_OFDMA_US, {}).get("nodes", [])
        per_channel = transpose_indexed_rows(rows)
        for ch_data in per_channel:
            if ch_data.get("Power") != "ON":
                continue
            state = ch_data.get("STATE", "")
            if "OPERATE" not in state:
                continue

            # "Center Freq SC0" is the only OFDMA frequency-shaped value
            # sercomm exposes; semantic is sercomm-specific and likely the
            # CMTS-assigned channel placement frequency rather than the
            # active-band lower edge required by FIELD_REGISTRY.md §
            # frequency semantics. Not mapping to canonical `frequency`
            # until hardware verification clarifies. See parser.yaml's
            # OFDM section for the parallel reasoning.
            channels.append(
                {
                    "channel_id": int(ch_data.get("CH", "0")),
                    "channel_type": "ofdma",
                    "power": float(ch_data.get("rep power", "0")),
                }
            )
        return channels

    def parse_system_info(
        self,
        system_info: dict[str, Any],
        resources: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract system_info from the Version_Info response."""
        items = resources.get(_VERSION_INFO, {}).get("nodes", [])

        for item in items:
            _extract_info_fields(item, system_info)
            fwinfo = item.get("fwinfo")
            if isinstance(fwinfo, str) and fwinfo:
                system_info["firmware_name"] = fwinfo
            fwbt = item.get("fwbt")
            if isinstance(fwbt, str) and fwbt:
                system_info["firmware_build_time"] = fwbt

        return system_info


def _extract_info_fields(item: dict[str, Any], system_info: dict[str, Any]) -> None:
    """Extract prefixed info fields from a Version_Info node."""
    info = item.get("info", "")
    if not info:
        return

    for prefix, field_name in _INFO_PREFIX_MAP.items():
        if info.startswith(prefix):
            system_info[field_name] = info[len(prefix) :]
            return

    # Docsis description line (no recognized prefix, contains "DOCSIS").
    if _DOCSIS_RE.search(info) and "docsis_description" not in system_info:
        system_info["docsis_description"] = info
