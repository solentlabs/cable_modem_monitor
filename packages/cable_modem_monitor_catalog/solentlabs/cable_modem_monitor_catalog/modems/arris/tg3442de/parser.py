"""PostProcessor for {manufacturer}/{model} — system_info extraction.

Extracts ``software_version`` from a simple JS variable assignment
(``js_FWVersion = 'value'``) in ``/php/status_about_data.php``.

Channel data extraction is handled entirely by parser.yaml (js_json
format). This PostProcessor only handles system_info because the
variable is a simple assignment, not a tagValueList that the
``javascript`` system_info format can parse.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

# Regex to match simple JS variable assignments: var x = 'value'
_JS_VAR_RE = re.compile(r"(?:var\s+)?(\w+)\s*=\s*'([^']*)'")


class PostProcessor:
    """Extract software_version from JS variable assignment."""

    def parse_system_info(
        self,
        system_info: dict[str, Any],
        resources: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract software_version from status_about_data.php."""
        for resource in resources.values():
            if not isinstance(resource, BeautifulSoup):
                continue
            for script in resource.find_all("script"):
                text = script.string
                if not text or "js_FWVersion" not in text:
                    continue
                for match in _JS_VAR_RE.finditer(text):
                    if match.group(1) == "js_FWVersion":
                        system_info["software_version"] = match.group(2)
                        return system_info
        return system_info
