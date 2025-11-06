"""Parser for Technicolor TC4400 cable modem."""
import logging
from bs4 import BeautifulSoup
from ..base_parser import ModemParser
from custom_components.cable_modem_monitor.lib.utils import extract_number, extract_float

_LOGGER = logging.getLogger(__name__)

# During modem restart, power readings may be temporarily zero.
# Ignore zero power readings during the first 5 minutes after boot.
RESTART_WINDOW_SECONDS = 300


class TechnicolorTC4400Parser(ModemParser):
    """Parser for Technicolor TC4400 cable modem."""

    name = "Technicolor TC4400"
    manufacturer = "Technicolor"
    models = ["TC4400"]

    url_patterns = [
        {"path": "/cmconnectionstatus.html", "auth_method": "basic"},
    ]

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Technicolor TC4400 modem."""
        return "cmconnectionstatus.html" in url.lower() or "cmswinfo.html" in url.lower() or ("Board ID:" in html and "Build Timestamp:" in html)

    def login(self, session, base_url, username, password) -> bool:
        """Log in to the modem using Basic HTTP Authentication."""
        if not username or not password:
            _LOGGER.debug("No credentials provided, skipping login")
            return True

        session.auth = (username, password)
        return True

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem."""
        # Parse system info first to get uptime for restart detection
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
        from custom_components.cable_modem_monitor.lib.utils import parse_uptime_to_seconds

        uptime_seconds = parse_uptime_to_seconds(system_info.get("system_uptime", ""))
        is_restarting = uptime_seconds is not None and uptime_seconds < RESTART_WINDOW_SECONDS
        _LOGGER.debug("TC4400 Uptime: %s, Seconds: {uptime_seconds}, Restarting: {is_restarting}", system_info.get('system_uptime'))

        channels = []
        try:
            downstream_table = soup.find("th", string="Downstream Channel Status").find_parent("table")
            for row in downstream_table.find_all("tr")[2:]:
                cols = row.find_all("td")
                if len(cols) == 13:
                    snr = extract_float(cols[7].text)
                    power = extract_float(cols[8].text)

                    # During restart window, filter out zero values which are typically invalid
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
        from custom_components.cable_modem_monitor.lib.utils import parse_uptime_to_seconds

        uptime_seconds = parse_uptime_to_seconds(system_info.get("system_uptime", ""))
        is_restarting = uptime_seconds is not None and uptime_seconds < RESTART_WINDOW_SECONDS
        _LOGGER.debug("TC4400 Uptime: %s, Seconds: {uptime_seconds}, Restarting: {is_restarting}", system_info.get('system_uptime'))

        channels = []
        try:
            upstream_table = soup.find("th", string="Upstream Channel Status").find_parent("table")
            for row in upstream_table.find_all("tr")[2:]:
                cols = row.find_all("td")
                if len(cols) == 9:
                    power = extract_float(cols[7].text)

                    # During restart window, filter out zero power which is typically invalid
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
        info = {}
        try:
            rows = soup.find_all("tr")
            for row in rows:
                header_cell = row.find("td", class_="hd")
                if header_cell:
                    header = header_cell.text.strip()
                    value_cell = header_cell.find_next_sibling("td")
                    if value_cell:
                        value = value_cell.text.strip()
                        if header == "Standard Specification Compliant":
                            info["standard_specification_compliant"] = value
                        elif header == "Hardware Version":
                            info["hardware_version"] = value
                        elif header == "Software Version":
                            info["software_version"] = value
                        elif header == "Cable Modem MAC Address":
                            info["mac_address"] = value
                        elif header == "System Up Time":
                            info["system_uptime"] = value
                        elif header == "Network Access":
                            info["network_access"] = value
                        elif header == "Cable Modem IPv4 Address":
                            info["ipv4_address"] = value
                        elif header == "Cable Modem IPv6 Address":
                            info["ipv6_address"] = value
                        elif header == "Board Temperature":
                            info["board_temperature"] = value
                else:
                    header_cell = row.find("td", string="Cable Modem Serial Number")
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