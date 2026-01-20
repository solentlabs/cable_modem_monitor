# =============================================================================
# AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
#
# Source: modems/arris/cm820b/parser.py
# This file is synced from modems/ during build. Edit the source file, then run:
#     make sync
# =============================================================================

"""Parser for ARRIS CM820B cable modem."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.lib.utils import extract_float, extract_number

_LOGGER = logging.getLogger(__name__)


class ArrisCM820BParser(ModemParser):
    """Parser for ARRIS CM820B cable modem."""

    # Auth handled by AuthDiscovery (v3.12.0+) - no auth_config needed
    # URL patterns now in modem.yaml pages config

    # login() not needed - uses base class default (AuthDiscovery handles auth)

    def parse_resources(self, resources: dict[str, Any]) -> dict:
        """Parse all data from pre-fetched resources."""
        # Get status page soup (primary page with channel data)
        status_soup = resources.get("/cgi-bin/status_cgi")
        if status_soup is None:
            # Fallback: try root or any BeautifulSoup in resources
            status_soup = resources.get("/")
            if status_soup is None:
                for value in resources.values():
                    if isinstance(value, BeautifulSoup):
                        status_soup = value
                        break

        if status_soup is None:
            return {"downstream": [], "upstream": [], "system_info": {}}

        downstream_channels = self._parse_downstream(status_soup)
        upstream_channels = self._parse_upstream(status_soup)

        # Parse system info from status page and vers_cgi page
        system_info = self._parse_system_info_from_resources(status_soup, resources)

        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem (legacy interface)."""
        # Build resources dict for parse_resources
        resources: dict[str, Any] = {"/": soup}

        # Fetch status page for channel data
        if session and base_url:
            try:
                response = session.get(f"{base_url}/cgi-bin/status_cgi", timeout=10)
                if response.status_code == 200:
                    resources["/cgi-bin/status_cgi"] = BeautifulSoup(response.text, "html.parser")
            except Exception as e:
                _LOGGER.debug("Failed to fetch status_cgi: %s", e)

            # Fetch vers_cgi for version info
            try:
                response = session.get(f"{base_url}/cgi-bin/vers_cgi", timeout=10)
                if response.status_code == 200:
                    resources["/cgi-bin/vers_cgi"] = BeautifulSoup(response.text, "html.parser")
            except Exception as e:
                _LOGGER.debug("Failed to fetch vers_cgi: %s", e)

        return self.parse_resources(resources)

    def _parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream channel data from ARRIS CM820B."""
        try:
            tables = soup.find_all("table")
            for table in tables:
                if table.find(string="Downstream 1"):
                    return self._parse_downstream_table(table)
        except Exception as e:
            _LOGGER.error("Error parsing downstream channels: %s", e)
        return []

    def _parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream channel data from ARRIS CM820B."""
        try:
            tables = soup.find_all("table")
            for table in tables:
                if table.find(string="Upstream 1"):
                    return self._parse_upstream_table(table)
        except Exception as e:
            _LOGGER.error("Error parsing upstream channels: %s", e)
        return []

    def _parse_downstream_table(self, table) -> list[dict]:
        """Parse ARRIS CM820B modem downstream table."""
        channels: list[dict[str, Any]] = []
        rows = table.find_all("tr")
        if not rows or len(rows) < 8:
            return channels

        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 9:
                continue

            freq_text = cells[2].text.strip()
            freq_hz = None
            if "MHz" in freq_text:
                try:
                    freq_hz = int(float(freq_text.replace("MHz", "").strip()) * 1_000_000)
                except Exception:
                    freq_hz = None

            channel = {
                "channel_id": cells[1].text.strip(),
                "frequency": freq_hz,
                "power": extract_float(cells[3].text),
                "snr": extract_float(cells[4].text),
                "modulation": cells[5].text.strip(),
                "corrected": extract_number(cells[7].text),
                "uncorrected": extract_number(cells[8].text),
            }

            if not channel["channel_id"] or channel["channel_id"] == "----":
                continue
            channels.append(channel)

        _LOGGER.debug(f"Parsed {len(channels)} downstream channels")

        return channels

    def _parse_upstream_table(self, table) -> list[dict]:
        """Parse ARRIS CM820B modem upstream table."""
        channels: list[dict[str, Any]] = []
        rows = table.find_all("tr")
        if not rows or len(rows) < 4:
            return channels

        for row in rows[2:]:
            cells = row.find_all("td")
            if len(cells) < 7:
                continue

            freq_text = cells[2].text.strip()
            freq_hz = None
            if "MHz" in freq_text:
                try:
                    freq_hz = int(float(freq_text.replace("MHz", "").strip()) * 1_000_000)
                except Exception:
                    freq_hz = None

            channel = {
                "channel_id": cells[1].text.strip(),
                "frequency": freq_hz,
                "power": extract_float(cells[3].text),
                "modulation": cells[6].text.strip(),
            }

            symbol_rate_text = cells[5].text.strip()
            symbol_rate = extract_number(symbol_rate_text)
            if symbol_rate is not None:
                channel["symbol_rate"] = symbol_rate

            if not channel["channel_id"] or channel["channel_id"] == "----":
                continue
            channels.append(channel)

        _LOGGER.debug(f"Parsed {len(channels)} upstream channels")

        return channels

    def _parse_system_info_from_resources(self, status_page_soup: BeautifulSoup, resources: dict[str, Any]) -> dict:
        """Parse system information from pre-fetched resources."""
        info: dict[str, Any] = {}

        try:
            uptime_tag = status_page_soup.find("td", text=lambda t: bool(t and "System Uptime:" in t))
            if uptime_tag:
                uptime_value = uptime_tag.find_next_sibling("td")
                if uptime_value:
                    info["system_uptime"] = uptime_value.text.strip()
                    _LOGGER.debug("Found uptime: %s", info["system_uptime"])
            else:
                _LOGGER.debug("System Up Time tag not found in HTML")

        except Exception as e:
            _LOGGER.error("Error parsing system info: %s", e)

        # Get vers_cgi soup from resources for hardware/software version
        vers_soup = resources.get("/cgi-bin/vers_cgi")
        if vers_soup is not None:
            self._parse_version_info(vers_soup, info)

        return info

    def _parse_system_info(self, status_page_soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse system information from ARRIS CM820B modem."""
        info = {}

        try:
            uptime_tag = status_page_soup.find("td", text=lambda t: bool(t and "System Uptime:" in t))
            if uptime_tag:
                uptime_value = uptime_tag.find_next_sibling("td")
                if uptime_value:
                    info["system_uptime"] = uptime_value.text.strip()
                    _LOGGER.debug("Found uptime: %s", info["system_uptime"])
            else:
                _LOGGER.debug("System Up Time tag not found in HTML")

        except Exception as e:
            _LOGGER.error("Error parsing system info: %s", e)

        # Fetch vers_cgi for hardware/software version
        if session and base_url:
            try:
                response = session.get(f"{base_url}/cgi-bin/vers_cgi", timeout=10)
                if response.status_code == 200:
                    vers_soup = BeautifulSoup(response.text, "html.parser")
                    self._parse_version_info(vers_soup, info)
            except Exception as e:
                _LOGGER.debug("Failed to fetch vers_cgi: %s", e)

        return info

    def _parse_version_info(self, vers_soup: BeautifulSoup, info: dict) -> None:
        """Parse hardware/software version from vers_cgi page.

        The vers_cgi page contains a cell with "System:" label followed by
        a cell containing multi-line text with HW_REV and SW_REV values.
        """
        try:
            system_label = vers_soup.find("td", string=lambda t: t and "System:" in t.strip())
            if system_label:
                system_value = system_label.find_next_sibling("td")
                if system_value:
                    text = system_value.get_text(separator="\n")
                    for raw_line in text.split("\n"):
                        stripped = raw_line.strip()
                        if stripped.startswith("HW_REV:"):
                            info["hardware_version"] = stripped.replace("HW_REV:", "").strip()
                            _LOGGER.debug("Found hardware version: %s", info["hardware_version"])
                        elif stripped.startswith("SW_REV:"):
                            info["software_version"] = stripped.replace("SW_REV:", "").strip()
                            _LOGGER.debug("Found software version: %s", info["software_version"])
        except Exception as e:
            _LOGGER.debug("Error parsing version info: %s", e)
