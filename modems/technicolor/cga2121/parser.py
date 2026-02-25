"""Parser for Technicolor CGA2121 cable modem."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup, Tag

from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.lib.utils import extract_float, extract_number
from custom_components.cable_modem_monitor.modem_config.adapter import (
    get_auth_adapter_for_parser,
)

_LOGGER = logging.getLogger(__name__)


class TechnicolorCGA2121Parser(ModemParser):
    """Parser for Technicolor CGA2121 cable modem (Telia Finland)."""

    def _get_primary_data_page(self) -> str | None:
        """Get primary data page path from modem.yaml."""
        adapter = get_auth_adapter_for_parser(self.__class__.__name__)
        if adapter:
            return adapter.get_primary_data_page()
        return None

    def parse_resources(self, resources: dict[str, Any]) -> dict:
        """Parse modem data from pre-fetched resources.

        Tries to find the data page in this order:
        1. Primary data page from modem.yaml (pages.data.downstream_channels)
        2. Root path (/) - legacy compatibility
        3. First BeautifulSoup in resources - fallback

        This handles the case where auth redirects to a different page
        than the data page (Issue #75).
        """
        soup = None

        # Try primary data page from modem.yaml first
        primary_page = self._get_primary_data_page()
        if primary_page:
            soup = resources.get(primary_page)
            if soup:
                _LOGGER.debug("CGA2121: Using primary data page %s", primary_page)

        # Fall back to root path (legacy compatibility)
        if soup is None:
            soup = resources.get("/")

        # Final fallback: iterate through all resources
        if soup is None:
            for value in resources.values():
                if isinstance(value, BeautifulSoup):
                    soup = value
                    break

        if soup is None:
            return {"downstream": [], "upstream": [], "system_info": {}}

        downstream = self._parse_downstream(soup)
        upstream = self._parse_upstream(soup)
        system_info = self._parse_system_info(soup)

        return {
            "downstream": downstream,
            "upstream": upstream,
            "system_info": system_info,
        }

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse modem data (legacy interface)."""
        return self.parse_resources({"/": soup})

    def _find_channel_tbody(self, soup: BeautifulSoup, section_name: str, i18n_key: str) -> Tag | None:
        """Find the tbody element for a channel section by header text or i18n key."""
        # Look for header containing section name
        header = None
        for h2 in soup.find_all("h2"):
            if section_name in h2.get_text():
                header = h2
                break

        # Try finding by data-i18n attribute as fallback
        if not header:
            header = soup.find("span", {"data-i18n": i18n_key})

        if not header:
            _LOGGER.warning("CGA2121: %s section not found", section_name)
            return None

        # Find the parent panel and then the table
        panel = header.find_parent("div", class_="panel")
        if not panel:
            _LOGGER.warning("CGA2121: %s panel not found", section_name)
            return None

        tables = panel.find_all("table", class_="rsp-table")
        if not tables:
            _LOGGER.warning("CGA2121: %s table not found", section_name)
            return None

        # Use the last table (the active one, not commented)
        tbody = tables[-1].find("tbody")
        if not tbody:
            _LOGGER.warning("CGA2121: %s tbody not found", section_name)
            return None

        return tbody

    def _parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream channel data from CGA2121."""
        channels: list[dict] = []

        try:
            tbody = self._find_channel_tbody(soup, "Downstream Channels", "ds_link_downstream_channels")
            if not tbody:
                return channels

            for row in tbody.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) >= 4:
                    channels.append(
                        {
                            "channel_id": extract_number(cols[0].get_text()),
                            "modulation": cols[1].get_text().strip(),
                            "snr": extract_float(cols[2].get_text()),
                            "power": extract_float(cols[3].get_text()),
                        }
                    )

            _LOGGER.debug("CGA2121: Parsed %d downstream channels", len(channels))

        except Exception as e:
            _LOGGER.error("Error parsing CGA2121 downstream channels: %s", e)

        return channels

    def _parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream channel data from CGA2121."""
        channels: list[dict] = []

        try:
            tbody = self._find_channel_tbody(soup, "Upstream Channels", "ds_link_upstream_channels")
            if not tbody:
                return channels

            for row in tbody.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) >= 3:
                    channels.append(
                        {
                            "channel_id": extract_number(cols[0].get_text()),
                            "modulation": cols[1].get_text().strip(),
                            "power": extract_float(cols[2].get_text()),
                        }
                    )

            _LOGGER.debug("CGA2121: Parsed %d upstream channels", len(channels))

        except Exception as e:
            _LOGGER.error("Error parsing CGA2121 upstream channels: %s", e)

        return channels

    def _parse_system_info(self, soup: BeautifulSoup) -> dict[str, Any]:
        """
        Parse system information from CGA2121.

        The status page has limited system info - mainly operational status.
        """
        info: dict[str, Any] = {}

        try:
            # Try to find operational status
            for row in soup.find_all("tr"):
                header = row.find("th")
                value = row.find("td")
                if header and value:
                    header_text = header.get_text().strip()
                    value_text = value.get_text().strip()

                    if "Operational Status" in header_text:
                        info["operational_status"] = value_text
                    elif "Downstream Channels" in header_text:
                        info["downstream_channel_count"] = extract_number(value_text)
                    elif "Upstream Channels" in header_text:
                        info["upstream_channel_count"] = extract_number(value_text)
                    elif "Baseline Privacy" in header_text:
                        info["baseline_privacy"] = value_text

        except Exception as e:
            _LOGGER.error("Error parsing CGA2121 system info: %s", e)

        return info
