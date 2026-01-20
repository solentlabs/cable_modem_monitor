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

IP Addressing: Combo modem/routers have two interfaces:
- 192.168.100.1 (cable modem interface)
- 192.168.0.1 (router LAN gateway) - separate auth session
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.lib.utils import parse_uptime_to_seconds

_LOGGER = logging.getLogger(__name__)


class NetgearC3700Parser(ModemParser):
    """Parser for Netgear C3700 cable modem/router."""

    # Auth handled by AuthDiscovery (v3.12.0+) - no auth_config needed
    # BasicAuth will be auto-detected via 401 response

    # URL patterns now in modem.yaml pages config

    # login() not needed - uses base class default (AuthDiscovery handles auth)

    def parse_resources(self, resources: dict[str, Any]) -> dict:
        """Parse modem data from pre-fetched resources.

        Args:
            resources: Dictionary mapping paths to BeautifulSoup objects

        Returns:
            Dictionary with downstream, upstream, and system_info
        """
        # Get DocsisStatus page soup (channel data)
        docsis_soup = resources.get("/DocsisStatus.htm")
        if docsis_soup is None:
            # Fallback to any available soup
            for value in resources.values():
                if isinstance(value, BeautifulSoup):
                    docsis_soup = value
                    break

        if docsis_soup is None:
            return {"downstream": [], "upstream": [], "system_info": {}}

        # Get RouterStatus page soup (system info)
        router_soup = resources.get("/RouterStatus.htm")
        if router_soup is None:
            router_soup = docsis_soup

        # Parse channel data from DocsisStatus.htm
        downstream_channels = self.parse_downstream(docsis_soup)
        upstream_channels = self.parse_upstream(docsis_soup)

        # Parse system info from RouterStatus.htm
        system_info = self.parse_system_info(router_soup)

        # Extract actual model from DocsisStatus.htm
        model_name = self._extract_model(docsis_soup)
        if model_name:
            system_info["model_name"] = model_name

        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem (legacy interface).

        Args:
            soup: BeautifulSoup object of the page
            session: Requests session (optional, for multi-page parsing)
            base_url: Base URL of the modem (optional)

        Returns:
            Dictionary with downstream, upstream, and system_info
        """
        # Build resources dict
        resources: dict[str, Any] = {"/": soup}

        if session and base_url:
            # Fetch DocsisStatus.htm for channel data
            try:
                _LOGGER.debug("C3700: Fetching DocsisStatus.htm for channel data")
                docsis_url = f"{base_url}/DocsisStatus.htm"
                docsis_response = session.get(docsis_url, timeout=10)

                if docsis_response.status_code == 200:
                    resources["/DocsisStatus.htm"] = BeautifulSoup(docsis_response.text, "html.parser")
                    _LOGGER.debug("C3700: Successfully fetched DocsisStatus.htm (%d bytes)", len(docsis_response.text))
                else:
                    _LOGGER.warning(
                        "C3700: Failed to fetch DocsisStatus.htm, status %d - using provided page",
                        docsis_response.status_code,
                    )
            except Exception as e:
                _LOGGER.warning("C3700: Error fetching DocsisStatus.htm: %s - using provided page", e)

            # Fetch RouterStatus.htm for system info (hardware/firmware versions)
            try:
                _LOGGER.debug("C3700: Fetching RouterStatus.htm for system info")
                router_url = f"{base_url}/RouterStatus.htm"
                router_response = session.get(router_url, timeout=10)

                if router_response.status_code == 200:
                    resources["/RouterStatus.htm"] = BeautifulSoup(router_response.text, "html.parser")
                    _LOGGER.debug("C3700: Successfully fetched RouterStatus.htm (%d bytes)", len(router_response.text))
                else:
                    _LOGGER.warning(
                        "C3700: Failed to fetch RouterStatus.htm, status %d - using provided page",
                        router_response.status_code,
                    )
            except Exception as e:
                _LOGGER.warning("C3700: Error fetching RouterStatus.htm: %s - using provided page", e)

        return self.parse_resources(resources)

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

    def parse_system_info(self, soup: BeautifulSoup) -> dict:  # noqa: C901
        """Parse system information from RouterStatus.htm or DashBoard.htm.

        Extracts:
        - Hardware version
        - Firmware version
        - System uptime
        - Last boot time (calculated from uptime)

        Returns:
            Dictionary with available system info
        """
        info = {}

        try:
            # Look for JavaScript variable tagValueList which contains system info
            # Format: tagValueList = 'hw_ver|fw_ver|serial|...|uptime|current_time|...'
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
                        # Skip serial number (PII)

                    # Extract uptime from values[33] if available
                    # Format: "26 days 12:34:56" or similar
                    if len(values) > 33 and values[33]:
                        uptime = values[33].strip()
                        if uptime and uptime != "---" and "***" not in uptime:
                            info["system_uptime"] = uptime
                            _LOGGER.debug("C3700: Parsed system uptime: %s", uptime)

                            # Calculate and add last boot time
                            boot_time = self._calculate_boot_time(uptime)
                            if boot_time:
                                info["last_boot_time"] = boot_time
                                _LOGGER.debug("C3700: Calculated last boot time: %s", boot_time)
                        elif uptime and "***" not in uptime:
                            # Still store even if it's just days without time
                            info["system_uptime"] = uptime
                            _LOGGER.debug("C3700: Parsed system uptime (partial): %s", uptime)

                    _LOGGER.debug(f"Parsed C3700 system info: {info}")
                    break

        except Exception as e:
            _LOGGER.error(f"Error parsing C3700 system info: {e}")

        return info

    def _calculate_boot_time(self, uptime_str: str) -> str | None:
        """Calculate boot time from uptime string.

        Args:
            uptime_str: Uptime string like "26 days 12:34:56" or "0 days 1h 23m 45s"

        Returns:
            ISO format datetime string of boot time or None if parsing fails
        """
        try:
            # Parse uptime string to seconds
            uptime_seconds = parse_uptime_to_seconds(uptime_str)
            if uptime_seconds is None:
                return None

            # Calculate boot time: current time - uptime
            uptime_delta = timedelta(seconds=uptime_seconds)
            boot_time = datetime.now() - uptime_delta

            return boot_time.isoformat()
        except Exception as e:
            _LOGGER.debug("C3700: Could not calculate boot time from '%s': %s", uptime_str, e)
            return None

    def _extract_model(self, soup: BeautifulSoup) -> str | None:
        """Extract actual model name from HTML meta or title.

        The C3700 includes model info in:
        - <META name="description" content='C3700-100NAS'>
        - <title>NETGEAR Gateway C3700-100NAS</title>

        Args:
            soup: BeautifulSoup object of the DocsisStatus.htm page

        Returns:
            Model name (e.g., "C3700-100NAS") or None if not found
        """
        # Try meta description first (most reliable)
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            content = meta.get("content")
            if isinstance(content, str) and content.strip():
                _LOGGER.debug("C3700: Extracted model from meta description: %s", content.strip())
                return content.strip()

        # Fallback to title tag
        title = soup.find("title")
        if title and title.string:
            # Extract model from "NETGEAR Gateway C3700-100NAS"
            match = re.search(r"Gateway\s+(\S+)", title.string)
            if match:
                model = match.group(1)
                _LOGGER.debug("C3700: Extracted model from title: %s", model)
                return model

        _LOGGER.debug("C3700: Could not extract model name from HTML")
        return None
