"""Parser for ARRIS CM820B cable modem."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import NoAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType
from custom_components.cable_modem_monitor.lib.utils import extract_float, extract_number

from ..base_parser import ModemCapability, ModemParser, ParserStatus

_LOGGER = logging.getLogger(__name__)


class ArrisCM820BParser(ModemParser):
    """Parser for ARRIS CM820B cable modem."""

    name = "ARRIS CM820B"
    manufacturer = "ARRIS"
    models = ["CM820B"]

    # Parser status
    status = ParserStatus.VERIFIED  # Verified by @dimkalinux (PR #57, December 2025)
    verification_source = "https://github.com/solentlabs/cable_modem_monitor/pull/57"

    # Device metadata
    release_date = "2011"
    docsis_version = "3.0"
    fixtures_path = "tests/parsers/arris/fixtures/cm820b/"

    priority = 100

    auth_config = NoAuthConfig(strategy=AuthStrategyType.NO_AUTH)

    url_patterns = [
        {"path": "/cgi-bin/vers_cgi", "auth_method": "none", "auth_required": False},
    ]

    capabilities = {
        ModemCapability.DOWNSTREAM_CHANNELS,
        ModemCapability.UPSTREAM_CHANNELS,
        ModemCapability.SYSTEM_UPTIME,
    }

    def login(self, session, base_url, username, password) -> tuple[bool, str | None]:
        """ARRIS CM820B does not require authentication."""
        return (True, None)

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem."""
        # Fetch status page for channel data
        if session and base_url:
            try:
                response = session.get(f"{base_url}/cgi-bin/status_cgi", timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
            except Exception as e:
                _LOGGER.debug("Failed to fetch status_cgi: %s", e)

        downstream_channels = self._parse_downstream(soup)
        upstream_channels = self._parse_upstream(soup)
        system_info = self._parse_system_info(soup)

        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is an ARRIS CM820B modem."""
        return bool(soup.find(string=lambda s: s and "CM820B" in s))

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

    def _parse_system_info(self, status_page_soup: BeautifulSoup) -> dict:
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

        return info
