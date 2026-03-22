"""PostProcessor for {manufacturer}/{model} — system_info extraction.

Extracts hardware_version, software_version, and system_uptime from
CGI pages. Same structure as CM820B: the "System:" blob in vers_cgi
contains HW_REV/SW_REV/MODEL on separate lines inside a single td cell.
The html_fields parser's label matching hits wrapper divs before the
correct td cells, so extraction is handled here.

Layout in /cgi-bin/vers_cgi::

    <td>System:</td>
    <td>ARRIS DOCSIS 3.0 ...
        HW_REV: 3
        SW_REV: 9.1.303U11.SIP.PC20.TW
        MODEL: TM1602A
    </td>

Layout in /cgi-bin/status_cgi::

    <td>System Uptime:</td>
    <td>27 d: 13 h: 39 m</td>
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag


class PostProcessor:
    """Extract system_info from CGI pages."""

    def parse_system_info(
        self,
        system_info: dict[str, Any],
        resources: dict[str, Any],
    ) -> dict[str, Any]:
        """Enrich system_info from status_cgi and vers_cgi pages."""
        status_soup = resources.get("/cgi-bin/status_cgi")
        if isinstance(status_soup, BeautifulSoup):
            uptime = _extract_td_label(status_soup, "System Uptime")
            if uptime:
                system_info["system_uptime"] = uptime

        vers_soup = resources.get("/cgi-bin/vers_cgi")
        if isinstance(vers_soup, BeautifulSoup):
            _extract_version_info(vers_soup, system_info)
            fw_name = _extract_td_label(vers_soup, "Firmware Name")
            if fw_name:
                system_info["firmware_name"] = fw_name
            fw_time = _extract_td_label(vers_soup, "Firmware Build Time")
            if fw_time:
                system_info["firmware_build_time"] = fw_time

        return system_info


def _extract_td_label(soup: BeautifulSoup, label: str) -> str:
    """Find a ``<td>`` with exact label text and return the next sibling td's text.

    Only matches ``<td>`` elements directly (not wrapper divs) to avoid
    the html_fields wrapper-element matching issue.
    """
    label_lower = label.lower()
    for td in soup.find_all("td"):
        if not isinstance(td, Tag):
            continue
        if td.find(["table", "div"]) is not None:
            continue
        text = td.get_text(strip=True).rstrip(":").lower()
        if text == label_lower:
            sibling = td.find_next_sibling("td")
            if sibling and isinstance(sibling, Tag):
                return str(sibling.get_text(strip=True))
    return ""


def _extract_version_info(soup: BeautifulSoup, system_info: dict[str, Any]) -> None:
    """Extract HW_REV, SW_REV, and MODEL from the 'System:' blob."""
    system_text = ""
    for td in soup.find_all("td"):
        if not isinstance(td, Tag):
            continue
        if td.get_text(strip=True).startswith("System:"):
            next_td = td.find_next_sibling("td")
            if next_td and isinstance(next_td, Tag):
                system_text = next_td.get_text(separator="\n", strip=True)
                break

    if not system_text:
        return

    hw_rev = _extract_field(system_text, r"HW_REV:\s*(.+)")
    sw_rev = _extract_field(system_text, r"SW_REV:\s*(.+)")
    model = _extract_field(system_text, r"MODEL:\s*(.+)")

    if hw_rev:
        system_info["hardware_version"] = hw_rev
    if sw_rev:
        system_info["software_version"] = sw_rev
    if model:
        system_info["model"] = model


def _extract_field(text: str, pattern: str) -> str:
    """Extract a named field from multi-line text using regex."""
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""
