"""Parser for Technicolor TC4400 cable modem."""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup, Tag

from custom_components.cable_modem_monitor.core.auth_config import BasicAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthFactory, AuthStrategyType
from custom_components.cable_modem_monitor.lib.utils import extract_float, extract_number, parse_uptime_to_seconds

from ..base_parser import ModemCapability, ModemParser

_LOGGER = logging.getLogger(__name__)

***REMOVED*** During modem restart, power readings may be temporarily zero.
***REMOVED*** Ignore zero power readings during the first 5 minutes after boot.
RESTART_WINDOW_SECONDS = 300


class TechnicolorTC4400Parser(ModemParser):
    """Parser for Technicolor TC4400 cable modem."""

    name = "Technicolor TC4400"
    manufacturer = "Technicolor"
    models = ["TC4400"]

    ***REMOVED*** Verification status
    verified = False  ***REMOVED*** No confirmed user reports
    verification_source = None  ***REMOVED*** Check Issue ***REMOVED***1 for status

    ***REMOVED*** Device metadata
    release_date = "2017"
    docsis_version = "3.1"
    fixtures_path = "tests/parsers/technicolor/fixtures/tc4400"

    ***REMOVED*** New authentication configuration (declarative)
    auth_config = BasicAuthConfig(strategy=AuthStrategyType.BASIC_HTTP)

    url_patterns = [
        {"path": "/cmconnectionstatus.html", "auth_method": "basic", "auth_required": True},
    ]

    ***REMOVED*** Capabilities - Technicolor TC4400
    capabilities = {
        ModemCapability.DOWNSTREAM_CHANNELS,
        ModemCapability.UPSTREAM_CHANNELS,
        ModemCapability.SYSTEM_UPTIME,
        ModemCapability.HARDWARE_VERSION,
        ModemCapability.SOFTWARE_VERSION,
    }

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Technicolor TC4400 modem."""
        url_match = "cmconnectionstatus.html" in url.lower() or "cmswinfo.html" in url.lower()
        html_match = "Board ID:" in html and "Build Timestamp:" in html

        result = url_match or html_match

        _LOGGER.debug(
            "TC4400 detection: url_match=%s, html_match=%s, url=%s, result=%s",
            url_match,
            html_match,
            url,
            result,
        )

        return result

    def login(self, session, base_url, username, password) -> tuple[bool, str | None]:
        """
        Log in to the modem using Basic HTTP Authentication.

        Returns:
            tuple[bool, str | None]: (success, authenticated_html)
        """
        auth_strategy = AuthFactory.get_strategy(self.auth_config.strategy)
        return auth_strategy.login(session, base_url, username, password, self.auth_config)

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem."""
        ***REMOVED*** Parse system info first to get uptime for restart detection
        system_info = self._parse_system_info(soup)
        downstream_channels = self._parse_downstream(soup, system_info)
        upstream_channels = self._parse_upstream(soup, system_info)

        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    def _parse_downstream(self, soup: BeautifulSoup, system_info: dict) -> list[dict]:
        """
        Parse downstream channel data from Technicolor TC4400.
        """
        uptime_seconds = parse_uptime_to_seconds(system_info.get("system_uptime", ""))
        is_restarting = uptime_seconds is not None and uptime_seconds < RESTART_WINDOW_SECONDS
        _LOGGER.debug(
            "TC4400 Uptime: %s, Seconds: %s, Restarting: %s",
            system_info.get("system_uptime"),
            uptime_seconds,
            is_restarting,
        )

        channels: list[dict] = []
        try:
            downstream_header = soup.find("th", text="Downstream Channel Status")
            if not downstream_header:
                _LOGGER.warning("TC4400: Downstream Channel Status table not found")
                return channels

            downstream_table = downstream_header.find_parent("table")
            if not downstream_table or not isinstance(downstream_table, Tag):
                _LOGGER.warning("TC4400: Downstream table parent not found")
                return channels

            for row in downstream_table.find_all("tr")[2:]:
                cols = row.find_all("td")
                if len(cols) == 13:
                    snr = extract_float(cols[7].text)
                    power = extract_float(cols[8].text)

                    ***REMOVED*** During restart window, filter out zero values which are typically invalid
                    if is_restarting:
                        if power == 0:
                            power = None
                        if snr == 0:
                            snr = None

                    channel_data = {
                        "channel_id": extract_number(cols[1].text),
                        "lock_status": cols[2].text.strip(),
                        "channel_type": cols[3].text.strip(),
                        "bonding_status": cols[4].text.strip(),
                        "frequency": self._parse_frequency(cols[5].text),
                        "width": self._parse_frequency(cols[6].text),
                        "snr": snr,
                        "power": power,
                        "modulation": cols[9].text.strip(),
                        "unerrored_codewords": extract_number(cols[10].text),
                        "corrected": extract_number(cols[11].text),
                        "uncorrected": extract_number(cols[12].text),
                    }
                    channels.append(channel_data)
        except Exception as e:
            _LOGGER.error("Error parsing TC4400 downstream channels: %s", e)

        return channels

    def _parse_upstream(self, soup: BeautifulSoup, system_info: dict) -> list[dict]:
        """
        Parse upstream channel data from Technicolor TC4400.
        """
        uptime_seconds = parse_uptime_to_seconds(system_info.get("system_uptime", ""))
        is_restarting = uptime_seconds is not None and uptime_seconds < RESTART_WINDOW_SECONDS
        _LOGGER.debug(
            "TC4400 Uptime: %s, Seconds: %s, Restarting: %s",
            system_info.get("system_uptime"),
            uptime_seconds,
            is_restarting,
        )

        channels: list[dict] = []
        try:
            upstream_header = soup.find("th", text="Upstream Channel Status")
            if not upstream_header:
                _LOGGER.warning("TC4400: Upstream Channel Status table not found")
                return channels

            upstream_table = upstream_header.find_parent("table")
            if not upstream_table or not isinstance(upstream_table, Tag):
                _LOGGER.warning("TC4400: Upstream table parent not found")
                return channels

            for row in upstream_table.find_all("tr")[2:]:
                cols = row.find_all("td")
                if len(cols) == 9:
                    power = extract_float(cols[7].text)

                    ***REMOVED*** During restart window, filter out zero power which is typically invalid
                    if is_restarting and power == 0:
                        power = None

                    channel_data = {
                        "channel_id": extract_number(cols[1].text),
                        "lock_status": cols[2].text.strip(),
                        "channel_type": cols[3].text.strip(),
                        "bonding_status": cols[4].text.strip(),
                        "frequency": self._parse_frequency(cols[5].text),
                        "width": self._parse_frequency(cols[6].text),
                        "power": power,
                        "modulation": cols[8].text.strip(),
                    }
                    channels.append(channel_data)
        except Exception as e:
            _LOGGER.error("Error parsing TC4400 upstream channels: %s", e)

        return channels

    def _parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information from Technicolor TC4400."""
        ***REMOVED*** Mapping of HTML header text to info dict keys
        header_mapping = {
            "Standard Specification Compliant": "standard_specification_compliant",
            "Hardware Version": "hardware_version",
            "Software Version": "software_version",
            "Cable Modem MAC Address": "mac_address",
            "System Up Time": "system_uptime",
            "Network Access": "network_access",
            "Cable Modem IPv4 Address": "ipv4_address",
            "Cable Modem IPv6 Address": "ipv6_address",
            "Board Temperature": "board_temperature",
        }

        info = {}
        try:
            rows = soup.find_all("tr")
            for row in rows:
                header_cell = row.find("td", class_="hd")
                if header_cell:
                    header = header_cell.text.strip()
                    value_cell = header_cell.find_next_sibling("td")
                    if value_cell and header in header_mapping:
                        info[header_mapping[header]] = value_cell.text.strip()
                else:
                    ***REMOVED*** Special case: Serial number uses different format
                    header_cell = row.find("td", text="Cable Modem Serial Number")
                    if header_cell:
                        value_cell = header_cell.find_next_sibling("td")
                        if value_cell:
                            info["serial_number"] = value_cell.text.strip()
        except Exception as e:
            _LOGGER.error("Error parsing TC4400 system info: %s", e)

        return info

    def _parse_frequency(self, text: str) -> int | None:
        """Parse frequency, handling both Hz and MHz formats."""
        try:
            freq = extract_float(text)
            if freq is None:
                return None
            if "mhz" in text.lower() or (freq > 0 and freq < 2000):
                return int(freq * 1_000_000)
            else:
                return int(freq)
        except Exception:
            return None
