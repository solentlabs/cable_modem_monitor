"""PostProcessor for {manufacturer}/{model} — system_info extraction.

The XB6's system info is in ``readonlyLabel``/``value`` span pairs
within nested div structures. The ``html_fields`` label cascade
matches wrapper divs before the correct spans, returning wrong values.
This PostProcessor extracts system info directly from the span pairs.
"""

from __future__ import annotations

from typing import Any


class PostProcessor:
    """Extract system_info from readonlyLabel/value span pairs."""

    def parse_system_info(
        self,
        system_info: dict[str, str],
        resources: dict[str, Any],
    ) -> dict[str, str]:
        """Extract system_info from readonlyLabel/value span pairs."""
        soup = resources["/network_setup.jst"]

        result: dict[str, str] = {}
        label_map = {
            "System Uptime": "system_uptime",
            "Download Version": "software_version",
            "Serial Number": "serial_number",
            "CM MAC": "mac_address",
            "Acquire Downstream Channel": "downstream_status",
            "Upstream Ranging": "upstream_status",
            "HW Version": "hardware_version",
            "Model": "model_name",
        }

        for span in soup.find_all("span", class_="readonlyLabel"):
            label = span.get_text(strip=True).rstrip(":")
            field = label_map.get(label)
            if field is None:
                continue
            value_span = span.find_next_sibling("span")
            if value_span:
                result[field] = value_span.get_text(strip=True)

        return result
