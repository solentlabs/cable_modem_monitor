"""Parser for ARRIS SB8200 cable modem."""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import NoAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType
from custom_components.cable_modem_monitor.lib.utils import extract_float, extract_number

from ..base_parser import ModemCapability, ModemParser, ParserStatus

_LOGGER = logging.getLogger(__name__)


class ArrisSB8200Parser(ModemParser):
    """Parser for ARRIS SB8200 cable modem.

    DOCSIS 3.1 modem with 32x8 channels plus OFDM.
    No authentication required - status page is public.
    """

    name = "ARRIS SB8200"
    manufacturer = "ARRIS"
    models = ["SB8200"]

    # Parser status
    status = ParserStatus.VERIFIED
    verification_source = "https://github.com/solentlabs/cable_modem_monitor/issues/42 (@undotcom)"

    # Device metadata
    release_date = "2016"
    docsis_version = "3.1"
    fixtures_path = "tests/parsers/arris/fixtures/sb8200"

    # Priority - model-specific parser
    priority = 100

    # Authentication configuration (none required)
    auth_config = NoAuthConfig(strategy=AuthStrategyType.NO_AUTH)

    url_patterns = [
        {"path": "/", "auth_method": "none", "auth_required": False},
        {"path": "/cmconnectionstatus.html", "auth_method": "none", "auth_required": False},
        {"path": "/cmswinfo.html", "auth_method": "none", "auth_required": False},
    ]

    # Capabilities - SB8200 has DOCSIS 3.1 OFDM channels
    capabilities = {
        ModemCapability.DOWNSTREAM_CHANNELS,
        ModemCapability.UPSTREAM_CHANNELS,
        ModemCapability.OFDM_DOWNSTREAM,
        ModemCapability.OFDM_UPSTREAM,
        ModemCapability.CURRENT_TIME,
        ModemCapability.SYSTEM_UPTIME,
        ModemCapability.SOFTWARE_VERSION,
        ModemCapability.HARDWARE_VERSION,
    }

    def login(self, session, base_url, username, password) -> tuple[bool, str | None]:
        """ARRIS SB8200 does not require authentication."""
        return (True, None)

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem."""
        downstream_channels = self._parse_downstream(soup)
        upstream_channels = self._parse_upstream(soup)
        system_info = self._parse_system_info(soup)

        # Fetch product info page for uptime and version info
        if session and base_url:
            try:
                response = session.get(f"{base_url}/cmswinfo.html", timeout=10)
                if response.status_code == 200:
                    info_soup = BeautifulSoup(response.text, "html.parser")
                    product_info = self._parse_product_info(info_soup)
                    system_info.update(product_info)
            except Exception as e:
                _LOGGER.debug("Failed to fetch cmswinfo.html: %s", e)

        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is an ARRIS SB8200 modem."""
        # Look for SB8200 model identifier
        model_span = soup.find("span", {"id": "thisModelNumberIs"})
        if model_span and "SB8200" in model_span.text:
            return True
        # Fallback: look for model string anywhere
        return bool(soup.find(string=lambda s: s and "SB8200" in s) and soup.find(string="Downstream Bonded Channels"))

    def _parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream channel data from ARRIS SB8200.

        Table structure:
        Channel ID | Lock Status | Modulation | Frequency | Power | SNR/MER | Corrected | Uncorrectables
        """
        channels: list[dict[str, Any]] = []
        tables = soup.find_all("table")

        for table in tables:
            header = table.find(string=lambda s: s and "Downstream Bonded Channels" in str(s))
            if not header:
                continue

            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # Skip header row(s) - may be 1 or 2 depending on HTML structure
            # Row 0 is always the title row. Row 1 may be column headers or data.
            start_idx = 1
            if len(rows) > 1:
                first_data_row = rows[1]
                cells = first_data_row.find_all("td")
                # If first cell is "Channel ID", this is a header row
                if cells and "Channel ID" in cells[0].text:
                    start_idx = 2

            for row in rows[start_idx:]:
                cells = row.find_all("td")
                if len(cells) < 8:
                    continue

                channel_id = cells[0].text.strip()
                if not channel_id or channel_id == "----":
                    continue

                modulation = cells[2].text.strip()

                # Parse frequency (in Hz format: "435000000 Hz")
                freq_text = cells[3].text.strip()
                freq_hz = extract_number(freq_text)

                channel: dict[str, Any] = {
                    "channel_id": channel_id,
                    "lock_status": cells[1].text.strip(),
                    "modulation": modulation,
                    "frequency": freq_hz,
                    "power": extract_float(cells[4].text),
                    "snr": extract_float(cells[5].text),
                    "corrected": extract_number(cells[6].text),
                    "uncorrected": extract_number(cells[7].text),
                }

                # Mark OFDM channels (modulation is "Other" for OFDM downstream)
                if modulation == "Other":
                    channel["is_ofdm"] = True

                channels.append(channel)
                _LOGGER.debug("Parsed SB8200 downstream channel %s: %s", channel_id, channel)

            break  # Found the downstream table

        return channels

    def _parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream channel data from ARRIS SB8200.

        Table structure:
        Channel | Channel ID | Lock Status | US Channel Type | Frequency | Width | Power
        """
        channels: list[dict[str, Any]] = []
        tables = soup.find_all("table")

        for table in tables:
            header = table.find(string=lambda s: s and "Upstream Bonded Channels" in str(s))
            if not header:
                continue

            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # Skip header row(s) - may be 1 or 2 depending on HTML structure
            start_idx = 1
            if len(rows) > 1:
                first_data_row = rows[1]
                cells = first_data_row.find_all("td")
                # If first cell is "Channel", this is a header row
                if cells and cells[0].text.strip() == "Channel":
                    start_idx = 2

            for row in rows[start_idx:]:
                cells = row.find_all("td")
                if len(cells) < 7:
                    continue

                channel_num = cells[0].text.strip()
                channel_id = cells[1].text.strip()
                if not channel_id or channel_id == "----":
                    continue

                channel_type = cells[3].text.strip()

                # Parse frequency (in Hz format)
                freq_text = cells[4].text.strip()
                freq_hz = extract_number(freq_text)

                # Parse width (in Hz format)
                width_text = cells[5].text.strip()
                width_hz = extract_number(width_text)

                channel: dict[str, Any] = {
                    "channel": channel_num,
                    "channel_id": channel_id,
                    "lock_status": cells[2].text.strip(),
                    "channel_type": channel_type,
                    "frequency": freq_hz,
                    "width": width_hz,
                    "power": extract_float(cells[6].text),
                }

                # Mark OFDM upstream channels
                if "OFDM" in channel_type:
                    channel["is_ofdm"] = True

                channels.append(channel)
                _LOGGER.debug("Parsed SB8200 upstream channel %s: %s", channel_id, channel)

            break  # Found the upstream table

        return channels

    def _parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information from ARRIS SB8200."""
        system_info: dict[str, Any] = {}

        # Parse current system time
        # Format: <p id="systime" align="center"><strong>Current System Time:</strong> Fri Nov 28 ...
        systime = soup.find("p", {"id": "systime"})
        if systime:
            time_text = systime.get_text()
            if "Current System Time:" in time_text:
                time_value = time_text.split("Current System Time:")[-1].strip()
                system_info["current_time"] = time_value

        # Parse startup procedure status
        tables = soup.find_all("table")
        for table in tables:
            header = table.find(string=lambda s: s and "Startup Procedure" in str(s))
            if not header:
                continue

            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    procedure = cells[0].text.strip()
                    status = cells[1].text.strip()

                    if "Connectivity State" in procedure:
                        system_info["connectivity_state"] = status
                    elif "Boot State" in procedure:
                        system_info["boot_state"] = status
                    elif "Security" in procedure:
                        system_info["security"] = status

            break

        return system_info

    def _parse_product_info(self, soup: BeautifulSoup) -> dict:
        """Parse product info from cmswinfo.html page.

        Extracts uptime, hardware version, and software version.
        """
        info: dict[str, Any] = {}

        tables = soup.find_all("table", class_="simpleTable")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)

                    if "Up Time" in label:
                        # Store as string for display (matches other parsers)
                        info["system_uptime"] = value
                        _LOGGER.debug("Parsed SB8200 uptime: %s", value)

                    elif "Hardware Version" in label:
                        info["hardware_version"] = value

                    elif "Software Version" in label:
                        info["software_version"] = value

                    elif "Standard Specification" in label:
                        info["docsis_version"] = value

        return info

    def _parse_uptime(self, uptime_str: str) -> int | None:
        """Parse uptime string to seconds.

        Format: "8 days 01h:16m:13s.00"
        """
        try:
            # Match pattern: X days HHh:MMm:SSs.XX
            match = re.match(
                r"(\d+)\s*days?\s+(\d+)h:(\d+)m:(\d+)s",
                uptime_str,
                re.IGNORECASE,
            )
            if match:
                days = int(match.group(1))
                hours = int(match.group(2))
                minutes = int(match.group(3))
                seconds = int(match.group(4))
                return days * 86400 + hours * 3600 + minutes * 60 + seconds

            # Try simpler format without days: HHh:MMm:SSs
            match = re.match(r"(\d+)h:(\d+)m:(\d+)s", uptime_str, re.IGNORECASE)
            if match:
                hours = int(match.group(1))
                minutes = int(match.group(2))
                seconds = int(match.group(3))
                return hours * 3600 + minutes * 60 + seconds

            _LOGGER.debug("Could not parse uptime format: %s", uptime_str)
            return None
        except (ValueError, AttributeError) as e:
            _LOGGER.debug("Error parsing uptime '%s': %s", uptime_str, e)
            return None
