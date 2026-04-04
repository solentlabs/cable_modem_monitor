"""PostProcessor for {manufacturer}/{model} — system_info formatting.

The ``javascript_vars`` format extracts all system_info fields from JS
variable assignments.  This PostProcessor reformats
``system_uptime`` from the Arris duration format
(``D: 39 H: 06 M: 24 S: 26``) to the canonical form
(``39 days 06:24:26``) and maps ``cm_status`` from ``"1"``/``"0"``
to ``"online"``/``"offline"``.
"""

from __future__ import annotations

import re
from typing import Any

# TODO: system_info fields don't support `map` in parser.yaml yet
# (only channel FieldMapping does). When core adds map support to
# SystemInfoFieldConfig, move these transforms into parser.yaml.

# Duration format: "D: 39 H: 06 M: 24 S: 26" → "39 days 06:24:26"
_DURATION_RE = re.compile(r"D:\s*(\d+)\s+H:\s*(\d+)\s+M:\s*(\d+)\s+S:\s*(\d+)")

# Firmware labels: PAGE_OVERVIEW_DOCSIS = "DOCSIS Online" / "DOCSIS Offline"
_CM_STATUS_MAP = {"1": "online", "0": "offline"}


class PostProcessor:
    """Reformat system_uptime and map cm_status."""

    def parse_system_info(
        self,
        system_info: dict[str, Any],
        resources: dict[str, Any],
    ) -> dict[str, Any]:
        """Reformat system_uptime and map cm_status if present."""
        raw = system_info.get("system_uptime")
        if isinstance(raw, str):
            m = _DURATION_RE.search(raw)
            if m:
                days, hours, minutes, seconds = m.groups()
                system_info["system_uptime"] = f"{days} days {hours}:{minutes}:{seconds}"

        cm = system_info.get("cm_status")
        if isinstance(cm, str) and cm in _CM_STATUS_MAP:
            system_info["cm_status"] = _CM_STATUS_MAP[cm]

        return system_info
