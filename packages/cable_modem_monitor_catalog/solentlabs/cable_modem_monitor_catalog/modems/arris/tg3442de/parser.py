"""PostProcessor for {manufacturer}/{model} — system_uptime formatting.

The ``javascript_vars`` format extracts all system_info fields from JS
variable assignments.  This PostProcessor only reformats
``system_uptime`` from the Arris duration format
(``D: 39 H: 06 M: 24 S: 26``) to the canonical form
(``39 days 06:24:26``).
"""

from __future__ import annotations

import re
from typing import Any

# Duration format: "D: 39 H: 06 M: 24 S: 26" → "39 days 06:24:26"
_DURATION_RE = re.compile(r"D:\s*(\d+)\s+H:\s*(\d+)\s+M:\s*(\d+)\s+S:\s*(\d+)")


class PostProcessor:
    """Reformat system_uptime from Arris duration string."""

    def parse_system_info(
        self,
        system_info: dict[str, Any],
        resources: dict[str, Any],
    ) -> dict[str, Any]:
        """Reformat system_uptime if present."""
        raw = system_info.get("system_uptime")
        if not isinstance(raw, str):
            return system_info

        m = _DURATION_RE.search(raw)
        if m:
            days, hours, minutes, seconds = m.groups()
            system_info["system_uptime"] = f"{days} days {hours}:{minutes}:{seconds}"

        return system_info
