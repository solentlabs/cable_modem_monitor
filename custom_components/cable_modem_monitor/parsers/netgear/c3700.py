"""Parser for Netgear C3700 cable modem/router.

The Netgear C3700 is a DOCSIS 3.0 cable modem with integrated WiFi router
and 24x8 channel bonding.

Firmware tested: V1.0.0.42_1.0.11
Hardware version: V2.02.18

Key pages:
- / or /index.htm: Main page (frameset)
- /DashBoard.htm: Dashboard with connection overview
- /RouterStatus.htm: Router and wireless status
- /DocsisStatus.htm: DOCSIS channel data (REQUIRED for parsing)
- /DocsisOffline.htm: Displayed when modem is offline
- /Logs.htm: Event logs

Authentication: HTTP Basic Auth

Note: The C3700 is a combo modem/router device, unlike the modem-only CM600.
Page extensions are .htm instead of .asp.
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import BasicAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType

from ..base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class NetgearC3700Parser(ModemParser):
    """Parser for Netgear C3700 cable modem/router."""

    name = "Netgear C3700"
    manufacturer = "Netgear"
    models = ["C3700", "C3700-100NAS"]
    priority = 50  # Standard priority

    # C3700 uses HTTP Basic Auth
    auth_config = BasicAuthConfig(
        strategy=AuthStrategyType.BASIC_HTTP,
    )

    # URL patterns to try for modem data
    url_patterns = [
        {"path": "/", "auth_method": "basic", "auth_required": False},
        {"path": "/index.htm", "auth_method": "basic", "auth_required": False},
        {"path": "/DocsisStatus.htm", "auth_method": "basic", "auth_required": True},
        {"path": "/DashBoard.htm", "auth_method": "basic", "auth_required": True},
        {"path": "/RouterStatus.htm", "auth_method": "basic", "auth_required": True},
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
        # C3700 uses HTTP Basic Auth - use AuthFactory to set it up
        from custom_components.cable_modem_monitor.core.authentication import AuthFactory

        auth_strategy = AuthFactory.get_strategy(self.auth_config.strategy)
        success, _ = auth_strategy.login(session, base_url, username, password, self.auth_config)
        return success

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem.

        Args:
            soup: BeautifulSoup object of the page
            session: Requests session (optional, for multi-page parsing)
            base_url: Base URL of the modem (optional)

        Returns:
            Dictionary with downstream, upstream, and system_info
        """
        # C3700 requires fetching DocsisStatus.htm for channel data
        docsis_soup = soup  # Default to provided soup

        if session and base_url:
            try:
                _LOGGER.debug("C3700: Fetching DocsisStatus.htm for channel data")
                docsis_url = f"{base_url}/DocsisStatus.htm"
                docsis_response = session.get(docsis_url, timeout=10)

                if docsis_response.status_code == 200:
                    docsis_soup = BeautifulSoup(docsis_response.text, "html.parser")
                    _LOGGER.debug("C3700: Successfully fetched DocsisStatus.htm (%d bytes)", len(docsis_response.text))
                else:
                    _LOGGER.warning(
                        "C3700: Failed to fetch DocsisStatus.htm, status %d - using provided page",
                        docsis_response.status_code,
                    )
            except Exception as e:
                _LOGGER.warning("C3700: Error fetching DocsisStatus.htm: %s - using provided page", e)

        # Parse channel data from DocsisStatus.htm
        downstream_channels = self.parse_downstream(docsis_soup)
        upstream_channels = self.parse_upstream(docsis_soup)

        # Parse system info from the main page (could be RouterStatus.htm or index.htm)
        system_info = self.parse_system_info(soup)

        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Netgear C3700.

        Detection strategy:
        - Check for "NETGEAR Gateway C3700" in title
        - Check for meta description containing "C3700"
        - Check for "C3700" in page content

        Args:
            soup: BeautifulSoup object of the page
            url: URL that was fetched
            html: Raw HTML string

        Returns:
            True if this is a Netgear C3700, False otherwise
        """
        # Check title tag
        title = soup.find("title")
        if title and "NETGEAR Gateway C3700" in title.text:
            _LOGGER.info("Detected Netgear C3700 from page title")
            return True

        # Check meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            content = meta_desc.get("content", "")
            if "C3700" in content:
                _LOGGER.info("Detected Netgear C3700 from meta description")
                return True

        # Check for C3700 in page text
        if "C3700" in html and "NETGEAR" in html.upper():
            _LOGGER.info("Detected Netgear C3700 from page content")
            return True

        return False

    def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:  # noqa: C901
        """Parse downstream channel data from DocsisStatus.htm.

        The C3700 embeds channel data in JavaScript variables. The data format is:
        - InitDsTableTagValue() function contains tagValueList
        - Format: 'count|ch1_data|ch2_data|...'
        - Each channel: num|lock|modulation|id|frequency|power|snr|corrected|uncorrected

        Returns:
            List of downstream channel dictionaries
        """
        channels: list[dict] = []

        try:
            regex_pattern = re.compile("InitDsTableTagValue")
            _LOGGER.debug("C3700 Downstream: Compiled regex pattern: %s", regex_pattern)
            all_scripts = soup.find_all("script")
            _LOGGER.debug("C3700 Downstream: Found %d total script tags.", len(all_scripts))

            match = None  # Initialize match to None
            for script in all_scripts:
                if script.string and regex_pattern.search(script.string):
                    _LOGGER.debug(
                        "C3700 Downstream: Found script tag with InitDsTableTagValue. Script string length: %d",
                        len(script.string),
                    )
                    # Extract the function body first, then get tagValueList from within it
                    func_match = re.search(
                        r"function InitDsTableTagValue\(\)[^{]*\{(.*?)\n\}", script.string, re.DOTALL
                    )
                    if func_match:
                        func_body = func_match.group(1)
                        # Remove block comments /* ... */ to avoid matching commented-out code
                        func_body_clean = re.sub(r"/\*.*?\*/", "", func_body, flags=re.DOTALL)
                        # Now find tagValueList within this function (skip // commented lines)
                        match = re.search(r"^\s+var tagValueList = [\"']([^\"']+)[\"']", func_body_clean, re.MULTILINE)
                        if match:
                            _LOGGER.debug(
                                "C3700 Downstream: tagValueList match found. Extracted value length: %d",
                                len(match.group(1)),
                            )

                            # Split by pipe delimiter
                            values = match.group(1).split("|")
                            break  # Found the data, stop searching
                        else:
                            _LOGGER.debug("C3700 Downstream: No tagValueList match found in function body.")
                            continue
                    else:
                        _LOGGER.debug("C3700 Downstream: Could not extract function body.")
                        continue

            if match is None:  # If no match was found after iterating all scripts
                _LOGGER.debug(
                    "C3700 Downstream: No script tag with InitDsTableTagValue found or no tagValueList extracted."
                )
                return channels  # Return empty list if no data found

            if len(values) < 10:  # Need at least count + 1 channel (9 fields)
                _LOGGER.warning("Insufficient downstream data: %d values", len(values))
                return channels  # Return empty list if insufficient data

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

                    # Extract lock status
                    lock_status = values[idx + 1]  # "Locked" or "Not Locked"

                    # Skip unlocked channels with 0 frequency (placeholder entries)
                    # These are configured but not in use by the ISP
                    if freq == 0 or lock_status != "Locked":
                        _LOGGER.debug(
                            "Skipping downstream channel %d: %s, freq=%d Hz",
                            i + 1,
                            lock_status,
                            freq,
                        )
                        idx += fields_per_channel
                        continue

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
            # No break here, as we want to parse all channels

        except Exception as e:
            _LOGGER.error("Error parsing C3700 downstream channels: %s", e, exc_info=True)

        return channels

    def parse_upstream(self, soup: BeautifulSoup) -> list[dict]:  # noqa: C901
        """Parse upstream channel data from DocsisStatus.htm.

        The C3700 embeds channel data in JavaScript variables. The data format is:
        - InitUsTableTagValue() function contains tagValueList
        - Format: 'count|ch1_data|ch2_data|...'
        - Each channel: num|lock|channel_type|id|symbol_rate|frequency|power

        Returns:
            List of upstream channel dictionaries
        """
        channels: list[dict] = []

        try:
            # Find the InitUsTableTagValue function with upstream data
            regex_pattern = re.compile("InitUsTableTagValue")
            _LOGGER.debug("C3700 Upstream: Compiled regex pattern: %s", regex_pattern)
            all_scripts = soup.find_all("script")
            _LOGGER.debug("C3700 Upstream: Found %d total script tags.", len(all_scripts))

            match = None  # Initialize match to None
            for script in all_scripts:
                if script.string and regex_pattern.search(script.string):
                    _LOGGER.debug(
                        "C3700 Upstream: Found script tag with InitUsTableTagValue. Script string length: %d",
                        len(script.string),
                    )
                    # Extract the function body first, then get tagValueList from within it
                    func_match = re.search(
                        r"function InitUsTableTagValue\(\)[^{]*\{(.*?)\n\}", script.string, re.DOTALL
                    )
                    if func_match:
                        func_body = func_match.group(1)
                        # Remove block comments /* ... */ to avoid matching commented-out code
                        func_body_clean = re.sub(r"/\*.*?\*/", "", func_body, flags=re.DOTALL)
                        # Now find tagValueList within this function (skip // commented lines)
                        match = re.search(r"^\s+var tagValueList = [\"']([^\"']+)[\"']", func_body_clean, re.MULTILINE)
                        if match:
                            _LOGGER.debug(
                                "C3700 Upstream: tagValueList match found. Extracted value length: %d",
                                len(match.group(1)),
                            )

                            # Split by pipe delimiter
                            values = match.group(1).split("|")
                            break  # Found the data, stop searching
                        else:
                            _LOGGER.debug("C3700 Upstream: No tagValueList match found in function body.")
                            continue
                    else:
                        _LOGGER.debug("C3700 Upstream: Could not extract function body.")
                        continue

            if match is None:  # If no match was found after iterating all scripts
                _LOGGER.debug(
                    "C3700 Upstream: No script tag with InitUsTableTagValue found or no tagValueList extracted."
                )
                return channels  # Return empty list if no data found

            if len(values) < 8:  # Need at least count + 1 channel (7 fields)
                _LOGGER.warning("Insufficient upstream data: %d values", len(values))
                return channels  # Return empty list if insufficient data

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

                    # Extract lock status
                    lock_status = values[idx + 1]  # "Locked" or "Not Locked"

                    # Skip unlocked channels with 0 frequency (placeholder entries)
                    # These are configured but not in use by the ISP
                    if freq == 0 or lock_status != "Locked":
                        _LOGGER.debug(
                            "Skipping upstream channel %d: %s, freq=%d Hz",
                            i + 1,
                            lock_status,
                            freq,
                        )
                        idx += fields_per_channel
                        continue

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
            # No break here, as we want to parse all channels

        except Exception as e:
            _LOGGER.error("Error parsing C3700 upstream channels: %s", e, exc_info=True)

        return channels

    def parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information from RouterStatus.htm or DashBoard.htm.

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
                match = re.search(r"var tagValueList = [\"']([^\"']+)[\"']", script.string or "")
                if match:
                    # Split by pipe delimiter
                    values = match.group(1).split("|")

                    if len(values) >= 3:
                        # Based on RouterStatus.htm structure:
                        # values[0] = Hardware Version
                        # values[1] = Firmware Version
                        # values[2] = Serial Number
                        if values[0] and values[0] != "":
                            info["hardware_version"] = values[0]
                        if values[1] and values[1] != "":
                            info["software_version"] = values[1]
                        # Skip serial number (already redacted in fixtures)

                        _LOGGER.debug(f"Parsed C3700 system info: {info}")
                        break

        except Exception as e:
            _LOGGER.error(f"Error parsing C3700 system info: {e}")

        return info
