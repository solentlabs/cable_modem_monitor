"""Parser for Motorola MB8611 cable modem using static HTML scraping."""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from ..base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class MotorolaMB8611StaticParser(ModemParser):
    """Parser for Motorola MB8611 cable modem from static HTML."""

    name = "Motorola MB8611 (Static)"
    manufacturer = "Motorola"
    models = ["MB8611", "MB8612"]
    priority = 100  # Try after HNAP parser, before generic

    url_patterns = [
        {"path": "/MotoStatusConnection.html", "auth_method": "none", "auth_required": False},
    ]

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Motorola MB8611 modem."""
        # Same detection logic as HNAP parser
        return (
            "MB8611" in html
            or "MB 8611" in html
            or "2251-MB8611" in html
            or (("HNAP" in html or "purenetworks.com/HNAP1" in html) and "Motorola" in html)
        )

    def login(self, session, base_url, username, password) -> tuple[bool, str | None]:
        """Static parser does not require login."""
        return True, None

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """
        Parse data from a static HTML page.

        Args:
            soup: BeautifulSoup object of the modem's status page.
            session: Not used for static parsing.
            base_url: Not used for static parsing.

        Returns:
            Dict with downstream, upstream, and system_info.
        """
        _LOGGER.debug("MB8611Static: Parsing data from static HTML")
        downstream = self._parse_downstream_from_html(soup)
        upstream = self._parse_upstream_from_html(soup)
        system_info = self._parse_system_info_from_html(soup)

        return {
            "downstream": downstream,
            "upstream": upstream,
            "system_info": system_info,
        }

    def _parse_downstream_from_html(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream channels from a static HTML table."""
        channels: list[dict] = []
        downstream_table = soup.find("table", id="MotoConnDownstreamChannel")
        if not downstream_table:
            _LOGGER.warning("MB8611Static: Downstream channel table not found.")
            return channels

        rows = downstream_table.find_all("tr")
        if len(rows) <= 1:
            return channels

        for row in rows[1:]:  # Skip header row
            cells = row.find_all("td")
            if len(cells) < 9:
                continue

            try:
                channels.append(
                    {
                        "channel_id": int(cells[0].text.strip()),
                        "lock_status": cells[1].text.strip(),
                        "modulation": cells[2].text.strip(),
                        "ch_id": int(cells[3].text.strip()),
                        "frequency": int(round(float(cells[4].text.strip()) * 1_000_000)),
                        "power": float(cells[5].text.strip()),
                        "snr": float(cells[6].text.strip()),
                        "corrected": int(cells[7].text.strip().replace(",", "")),
                        "uncorrected": int(cells[8].text.strip().replace(",", "")),
                    }
                )
            except (ValueError, IndexError) as e:
                _LOGGER.warning("MB8611Static: Error parsing downstream row: %s - %s", row, e)
                continue
        return channels

    def _parse_upstream_from_html(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream channels from a static HTML table."""
        channels: list[dict] = []
        upstream_table = soup.find("table", id="MotoConnUpstreamChannel")
        if not upstream_table:
            _LOGGER.warning("MB8611Static: Upstream channel table not found.")
            return channels

        rows = upstream_table.find_all("tr")
        if len(rows) <= 1:
            return channels

        for row in rows[1:]:  # Skip header row
            cells = row.find_all("td")
            if len(cells) < 7:
                continue

            try:
                channels.append(
                    {
                        "channel_id": int(cells[0].text.strip()),
                        "lock_status": cells[1].text.strip(),
                        "modulation": cells[2].text.strip(),  # Channel Type in HTML
                        "ch_id": int(cells[3].text.strip()),
                        "symbol_rate": int(cells[4].text.strip().replace(",", "")),
                        "frequency": int(round(float(cells[5].text.strip()) * 1_000_000)),
                        "power": float(cells[6].text.strip()),
                    }
                )
            except (ValueError, IndexError) as e:
                _LOGGER.warning("MB8611Static: Error parsing upstream row: %s - %s", row, e)
                continue
        return channels

    def _parse_system_info_from_html(self, soup: BeautifulSoup) -> dict:
        """Parse system info from various elements in the static HTML."""
        system_info: dict[str, str] = {}

        # Helper to find and store text from an element by its ID
        def _store_text_by_id(element_id: str, key: str):
            element = soup.find(id=element_id)
            if element and element.text.strip():
                system_info[key] = element.text.strip()

        _store_text_by_id("MotoConnSystemUpTime", "system_uptime")
        _store_text_by_id("MotoConnNetworkAccess", "network_access")
        _store_text_by_id("StatusSoftwareSpecVer", "docsis_version")
        _store_text_by_id("StatusSoftwareHdVer", "hardware_version")
        _store_text_by_id("StatusSoftwareSfVer", "software_version")

        # Startup sequence info
        _store_text_by_id("MotoConnDSFreq", "downstream_frequency")
        _store_text_by_id("MotoConnConnectivityStatus", "connectivity_status")
        _store_text_by_id("MotoConnBootStatus", "boot_status")
        _store_text_by_id("MotoConnSecurityStatus", "security_status")
        _store_text_by_id("MotoConnSecurityComment", "security_comment")

        return system_info
