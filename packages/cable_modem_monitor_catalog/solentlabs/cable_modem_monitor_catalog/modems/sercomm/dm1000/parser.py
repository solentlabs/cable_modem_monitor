"""PostProcessor for {manufacturer}/{model} — OFDMA and system_info extraction.

Extends the parser.yaml-driven extraction with two hooks:

- ``parse_upstream``: appends OFDMA channels from RF_US_31_param
  (transposed name/index format — can't be expressed declaratively)
- ``parse_system_info``: extracts firmware, hardware, vendor, and
  build info from Version_Info (prefix-parsing — can't be expressed
  declaratively)

OFDM downstream channels are fully declarative in parser.yaml via
per-array resources.
"""

from __future__ import annotations

import re
from typing import Any

# Resource endpoints.
_VERSION_INFO = "/setup.cgi?todo=Version_Info"
_OFDMA_US = "/setup.cgi?todo=RF_US_31_param"

# Maps "info" field prefixes to system_info field names.
_INFO_PREFIX_MAP = {
    "HW_REV ": "hardware_version",
    "SW_REV ": "software_version",
    "MODEL ": "model",
    "VENDOR ": "vendor",
    "BOOTR ": "bootloader_version",
}

# Pattern to detect the DOCSIS description line (e.g.,
# "Docsis 3.1/DOCSIS 3.1 Cable Modem").
_DOCSIS_RE = re.compile(r"DOCSIS", re.IGNORECASE)


class PostProcessor:
    """Extract OFDMA upstream channels and enrich system_info."""

    def parse_upstream(
        self,
        channels: list[dict[str, Any]],
        resources: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Append OFDMA upstream channels from RF_US_31_param.

        The RF_US_31_param response uses a transposed format where each
        row is a parameter name and columns (index1, index2, ...) are
        channels. Only active channels (Power=ON, STATE=OPERATE) are
        included.
        """
        per_channel = _transpose_nodes(resources, _OFDMA_US)
        for ch_data in per_channel:
            if ch_data.get("Power") != "ON":
                continue
            state = ch_data.get("STATE", "")
            if "OPERATE" not in state:
                continue

            freq_mhz = float(ch_data.get("Center Freq SC0", "0"))
            channels.append(
                {
                    "channel_id": int(ch_data.get("CH", "0")),
                    "channel_type": "ofdma",
                    "frequency": int(freq_mhz * 1_000_000),
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
        items = _get_nodes(resources, _VERSION_INFO)

        for item in items:
            _extract_info_fields(item, system_info)
            fwinfo = item.get("fwinfo")
            if isinstance(fwinfo, str) and fwinfo:
                system_info["firmware_name"] = fwinfo
            fwbt = item.get("fwbt")
            if isinstance(fwbt, str) and fwbt:
                system_info["firmware_build_time"] = fwbt

        return system_info


def _get_nodes(resources: dict[str, Any], endpoint: str) -> list[dict[str, Any]]:
    """Extract the nodes list from a resource endpoint."""
    data = resources.get(endpoint)
    if data is None:
        return []
    nodes: list[dict[str, Any]] = data.get("nodes", [])
    return nodes


def _transpose_nodes(
    resources: dict[str, Any],
    endpoint: str,
) -> list[dict[str, Any]]:
    """Transpose a name/indexN pivot table into per-channel dicts.

    Input rows:  ``{"name": "CH", "index1": "0", "index2": "1"}``
    Output:      ``[{"CH": "0"}, {"CH": "1"}]``

    Dynamically detects ``indexN`` keys so firmware changes that add
    channels are handled without code updates.
    """
    nodes = _get_nodes(resources, endpoint)
    if not nodes:
        return []

    # Detect column keys (index1, index2, ...) from the first row.
    col_keys = sorted(k for k in nodes[0] if k.startswith("index"))
    if not col_keys:
        return []

    result: list[dict[str, str]] = [{} for _ in col_keys]
    for row in nodes:
        name = row.get("name", "")
        for i, col_key in enumerate(col_keys):
            value = row.get(col_key, "")
            result[i][name] = value.strip() if isinstance(value, str) else value

    return result


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
