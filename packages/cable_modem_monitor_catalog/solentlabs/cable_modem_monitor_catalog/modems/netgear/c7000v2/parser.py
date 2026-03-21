"""Post-processor for Netgear C7000v2.

Extracts hardware_version and software_version from RouterStatus.htm.
These values are embedded in a JavaScript ``tagValueList`` variable
that the html_fields parser cannot reach -- the values are in JS, not
in HTML label/value cells.

Layout in RouterStatus.htm::

    var tagValueList = 'hw_ver|fw_ver|serial|...'
                        [0]     [1]    [2]
"""

from __future__ import annotations

import re
from typing import Any


class PostProcessor:
    """RouterStatus.htm system_info extractor for C7000v2."""

    def parse_system_info(
        self,
        system_info: dict[str, Any],
        resources: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract hardware/software version from JS tagValueList.

        Args:
            system_info: Existing system_info dict (from parser.yaml).
            resources: Resource dict (path -> BeautifulSoup).

        Returns:
            Updated system_info dict with hw/sw version added.
        """
        soup = resources.get("/RouterStatus.htm")
        if soup is None:
            return system_info

        for script in soup.find_all("script"):
            text = script.string
            if not text:
                continue

            match = re.search(r"var tagValueList = [\"']([^\"']+)[\"']", text)
            if not match:
                continue

            values = match.group(1).split("|")
            if len(values) >= 2:
                if values[0]:
                    system_info["hardware_version"] = values[0]
                if values[1]:
                    system_info["software_version"] = values[1]
            break

        return system_info
