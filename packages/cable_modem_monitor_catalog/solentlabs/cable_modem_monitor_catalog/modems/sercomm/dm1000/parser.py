"""PostProcessor for {manufacturer}/{model} — system_info extraction.

Extracts firmware version, hardware version, and model from the
/setup.cgi?todo=Version_Info endpoint. Response is a base64-encoded
JSON object with ``nodes`` array containing mixed formats:

    ``{"info": "HW_REV 1.0"}`` — space-separated key-value
    ``{"serial": "2407DC2001702"}`` — direct key-value
    ``{"fwinfo": "DM1000-V1.21.04.025"}`` — firmware info
"""

from __future__ import annotations

from typing import Any

# Maps "info" field prefixes to system_info field names.
_INFO_PREFIX_MAP = {
    "HW_REV ": "hardware_version",
    "SW_REV ": "software_version",
    "MODEL ": "model",
}


class PostProcessor:
    """Extract system_info from Version_Info JSON response."""

    def parse_system_info(
        self,
        system_info: dict[str, Any],
        resources: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract system_info from the Version_Info response."""
        items = _get_version_nodes(resources)

        for item in items:
            _extract_info_fields(item, system_info)
            fwinfo = item.get("fwinfo")
            if isinstance(fwinfo, str) and fwinfo:
                system_info["firmware_name"] = fwinfo

        return system_info


def _get_version_nodes(resources: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the nodes list from the Version_Info resource."""
    data = resources.get("/setup.cgi?todo=Version_Info")
    if not isinstance(data, dict):
        return []
    nodes = data.get("nodes", [])
    return nodes if isinstance(nodes, list) else []


def _extract_info_fields(item: dict[str, Any], system_info: dict[str, Any]) -> None:
    """Extract prefixed info fields from a Version_Info node."""
    if not isinstance(item, dict):
        return
    info = item.get("info", "")
    if not isinstance(info, str):
        return
    for prefix, field_name in _INFO_PREFIX_MAP.items():
        if info.startswith(prefix):
            system_info[field_name] = info[len(prefix) :]
            return
