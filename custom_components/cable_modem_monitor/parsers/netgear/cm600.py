"""Parser for Netgear CM600 cable modem.

The Netgear CM600 is a DOCSIS 3.0 cable modem with 24x8 channel bonding.

Firmware tested: V1.01.22

Key pages:
- / or /index.html: Main page (frameset)
- /DashBoard.asp: Dashboard with connection overview
- /RouterStatus.asp: Router and wireless status
- /DocsisStatus.asp: DOCSIS channel data (REQUIRED for parsing)
- /EventLog.asp: Event logs

Authentication: HTTP Basic Auth

Related: Issue #3 (Netgear CM600 - Login Doesn't Work)
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import BasicAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType

from ..base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class NetgearCM600Parser(ModemParser):
    """Parser for Netgear CM600 cable modem."""

    name = "Netgear CM600"
    manufacturer = "Netgear"
    models = ["CM600"]
    priority = 50  # Standard priority

    # CM600 uses HTTP Basic Auth
    auth_config = BasicAuthConfig(
        strategy=AuthStrategyType.BASIC_HTTP,
    )

    # URL patterns to try for modem data
    url_patterns = [
        {"path": "/", "auth_method": "basic", "auth_required": False},
        {"path": "/index.html", "auth_method": "basic", "auth_required": False},
        {"path": "/DocsisStatus.asp", "auth_method": "basic", "auth_required": False},
        {"path": "/DashBoard.asp", "auth_method": "basic", "auth_required": False},
        {"path": "/RouterStatus.asp", "auth_method": "basic", "auth_required": False},
    ]

    def login(self, session, base_url, username, password) -> bool:
        """Perform login using HTTP Basic Auth.

        Args:
            session: Requests session
            base_url: Modem base URL
            username: Username for authentication
            password: Password for authentication

        Returns:
            True if login successful or not required
        """
        # CM600 uses HTTP Basic Auth which is handled automatically by the session
        # If credentials are provided, they're set in the session auth
        # No explicit login page to navigate
        return True

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem.

        Args:
            soup: BeautifulSoup object of the page
            session: Requests session (optional, for multi-page parsing)
            base_url: Base URL of the modem (optional)

        Returns:
            Dictionary with downstream, upstream, and system_info
        """
        downstream_channels = self.parse_downstream(soup)
        upstream_channels = self.parse_upstream(soup)
        system_info = self.parse_system_info(soup)

        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Netgear CM600.

        Detection strategy:
        - Check for "NETGEAR Gateway CM600" in title
        - Check for meta description containing "CM600"
        - Check for "CM600" in page content

        Args:
            soup: BeautifulSoup object of the page
            url: URL that was fetched
            html: Raw HTML string

        Returns:
            True if this is a Netgear CM600, False otherwise
        """
        # Check title tag
        title = soup.find("title")
        if title and "NETGEAR Gateway CM600" in title.text:
            _LOGGER.info("Detected Netgear CM600 from page title")
            return True

        # Check meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            content = meta_desc.get("content", "")
            if "CM600" in content:
                _LOGGER.info("Detected Netgear CM600 from meta description")
                return True

        # Check for CM600 in page text
        if "CM600" in html and "NETGEAR" in html.upper():
            _LOGGER.info("Detected Netgear CM600 from page content")
            return True

        return False

    def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream channel data from DocsisStatus.asp.

        The CM600 embeds channel data in JavaScript variables. The data format is:
        - InitDsTableTagValue() function contains tagValueList
        - Format: 'count|ch1_data|ch2_data|...'
        - Each channel: num|lock|modulation|id|frequency|power|snr|corrected|uncorrected

        Returns:
            List of downstream channel dictionaries
        """
        channels = []

        try:
            # Find the InitDsTableTagValue function with downstream data
            script_tags = soup.find_all("script", text=re.compile("InitDsTableTagValue"))

            for script in script_tags:
                # Extract the tagValueList value from the function
                match = re.search(r"var tagValueList = ['\"]([^'\"]+)['\"]", script.string or "")
                if not match:
                    continue

                # Split by pipe delimiter
                values = match.group(1).split("|")

                if len(values) < 10:  # Need at least count + 1 channel (9 fields)
                    _LOGGER.warning("Insufficient downstream data: %d values", len(values))
                    continue

                # First value is channel count
                channel_count = int(values[0])
                _LOGGER.debug("Found %d downstream channels", channel_count)

                # Each channel has 9 fields: num|lock|modulation|id|frequency|power|snr|corrected|uncorrected
                fields_per_channel = 9
                idx = 1  # Start after channel count

                for i in range(channel_count):
                    if idx + fields_per_channel > len(values):
                        _LOGGER.warning("Incomplete data for downstream channel %d", i + 1)
                        break

                    try:
                        # Extract frequency value (remove " Hz" suffix if present)
                        freq_str = values[idx + 4].replace(" Hz", "").strip()
                        freq = int(freq_str)

                        channel = {
                            "channel_id": values[idx + 3],  # Channel ID
                            "frequency": freq,  # Frequency in Hz
                            "power": float(values[idx + 5]),  # Power in dBmV
                            "snr": float(values[idx + 6]),  # SNR in dB
                            "modulation": values[idx + 2],  # Modulation (QAM256, etc.)
                            "corrected": int(values[idx + 7]),  # Corrected errors
                            "uncorrected": int(values[idx + 8]),  # Uncorrected errors
                        }

                        channels.append(channel)
                        idx += fields_per_channel

                    except (ValueError, IndexError) as e:
                        _LOGGER.warning("Error parsing downstream channel %d: %s", i + 1, e)
                        idx += fields_per_channel
                        continue

                _LOGGER.info("Parsed %d downstream channels", len(channels))
                break  # Found the data, stop searching

        except Exception as e:
            _LOGGER.error("Error parsing CM600 downstream channels: %s", e)

        return channels

    def parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream channel data from DocsisStatus.asp.

        The CM600 embeds channel data in JavaScript variables. The data format is:
        - InitUsTableTagValue() function contains tagValueList
        - Format: 'count|ch1_data|ch2_data|...'
        - Each channel: num|lock|channel_type|id|symbol_rate|frequency|power

        Returns:
            List of upstream channel dictionaries
        """
        channels = []

        try:
            # Find the InitUsTableTagValue function with upstream data
            script_tags = soup.find_all("script", text=re.compile("InitUsTableTagValue"))

            for script in script_tags:
                # Extract the tagValueList value from the function
                match = re.search(r"var tagValueList = ['\"]([^'\"]+)['\"]", script.string or "")
                if not match:
                    continue

                # Split by pipe delimiter
                values = match.group(1).split("|")

                if len(values) < 8:  # Need at least count + 1 channel (7 fields)
                    _LOGGER.warning("Insufficient upstream data: %d values", len(values))
                    continue

                # First value is channel count
                channel_count = int(values[0])
                _LOGGER.debug("Found %d upstream channels", channel_count)

                # Each channel has 7 fields: num|lock|channel_type|id|symbol_rate|frequency|power
                fields_per_channel = 7
                idx = 1  # Start after channel count

                for i in range(channel_count):
                    if idx + fields_per_channel > len(values):
                        _LOGGER.warning("Incomplete data for upstream channel %d", i + 1)
                        break

                    try:
                        # Extract frequency value (remove " Hz" suffix if present)
                        freq_str = values[idx + 5].replace(" Hz", "").strip()
                        freq = int(freq_str)

                        channel = {
                            "channel_id": values[idx + 3],  # Channel ID
                            "frequency": freq,  # Frequency in Hz
                            "power": float(values[idx + 6]),  # Power in dBmV
                            "channel_type": values[idx + 2],  # Channel type (ATDMA, etc.)
                        }

                        channels.append(channel)
                        idx += fields_per_channel

                    except (ValueError, IndexError) as e:
                        _LOGGER.warning("Error parsing upstream channel %d: %s", i + 1, e)
                        idx += fields_per_channel
                        continue

                _LOGGER.info("Parsed %d upstream channels", len(channels))
                break  # Found the data, stop searching

        except Exception as e:
            _LOGGER.error("Error parsing CM600 upstream channels: %s", e)

        return channels

    def parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information from RouterStatus.asp or DashBoard.asp.

        Extracts:
        - Hardware version
        - Firmware version
        - Serial number

        Returns:
            Dictionary with available system info
        """
        info = {}

        try:
            # Look for JavaScript variable tagValueList which contains system info
            # Format: tagValueList = 'hw_ver|fw_ver|serial|...'
            script_tags = soup.find_all("script", text=re.compile("tagValueList"))

            for script in script_tags:
                # Extract the tagValueList value
                match = re.search(r"var tagValueList = ['\"]([^'\"]+)['\"]", script.string or "")
                if match:
                    # Split by pipe delimiter
                    values = match.group(1).split("|")

                    if len(values) >= 3:
                        # Based on RouterStatus.asp structure:
                        # values[0] = Hardware Version
                        # values[1] = Firmware Version
                        # values[2] = Serial Number
                        if values[0] and values[0] != "":
                            info["hardware_version"] = values[0]
                        if values[1] and values[1] != "":
                            info["software_version"] = values[1]
                        # Skip serial number (already redacted in fixtures)

                        _LOGGER.debug(f"Parsed CM600 system info: {info}")
                        break

        except Exception as e:
            _LOGGER.error(f"Error parsing CM600 system info: {e}")

        return info
