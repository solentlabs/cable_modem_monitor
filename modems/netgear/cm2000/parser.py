"""Parser for Netgear CM2000 (Nighthawk) cable modem.

The Netgear CM2000 is a DOCSIS 3.1 cable modem with multi-gigabit capability.

Firmware tested: V8.01.02
Hardware version: 1.01

Key pages:
- / or /index.htm: Login page (unauthenticated)
- /DocsisStatus.htm: DOCSIS channel data (REQUIRED for parsing, auth required)
- /Login.htm: Redirect target when unauthenticated

Authentication: Form-based POST to /goform/Login
- Username field: loginName
- Password field: loginPassword

Data format (InitTagValue):
- [10] Current System Time (e.g., "Tue Nov 25 12:48:02 2025")
- [14] System Up Time (e.g., "7 days 00:00:01")

Channel data:
- 32 downstream (DOCSIS 3.0, QAM256)
- 8 upstream (DOCSIS 3.0, ATDMA)
- OFDM downstream (DOCSIS 3.1)
- OFDM upstream (DOCSIS 3.1)

Related: Issue #38 (Netgear CM2000 Support Request)
Contributor: @m4dh4tt3r-88
"""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class NetgearCM2000Parser(ModemParser):
    """Parser for Netgear CM2000 (Nighthawk) cable modem."""

    # Auth handled by AuthDiscovery (v3.12.0+) - form hints now in modem.yaml auth.form

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

        # Parse channel data from DocsisStatus.htm
        downstream_channels = self.parse_downstream(docsis_soup)
        upstream_channels = self.parse_upstream(docsis_soup)

        # Parse system info from DocsisStatus.htm (uptime, current time)
        system_info = self.parse_system_info(docsis_soup)

        # Parse version info from additional pages if available
        index_soup = resources.get("/index.htm")
        if index_soup is not None:
            sw_version = self._parse_software_version_from_index(index_soup)
            if sw_version:
                system_info["software_version"] = sw_version

        router_soup = resources.get("/RouterStatus.htm")
        if router_soup is not None:
            hw_version = self._parse_hardware_version_from_router_status(router_soup)
            if hw_version:
                system_info["hardware_version"] = hw_version

        # Extract actual model from HTML
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
            try:
                _LOGGER.debug("CM2000: Fetching DocsisStatus.htm for channel data")
                docsis_url = f"{base_url}/DocsisStatus.htm"
                docsis_response = session.get(docsis_url, timeout=10)

                if docsis_response.status_code == 200:
                    # Check if we got redirected to login page
                    if "redirect()" in docsis_response.text and "Login.htm" in docsis_response.text:
                        _LOGGER.warning("CM2000: Session expired, got login redirect")
                    else:
                        resources["/DocsisStatus.htm"] = BeautifulSoup(docsis_response.text, "html.parser")
                        _LOGGER.debug(
                            "CM2000: Successfully fetched DocsisStatus.htm (%d bytes)", len(docsis_response.text)
                        )
                else:
                    _LOGGER.warning(
                        "CM2000: Failed to fetch DocsisStatus.htm, status %d - using provided page",
                        docsis_response.status_code,
                    )
            except Exception as e:
                _LOGGER.warning("CM2000: Error fetching DocsisStatus.htm: %s - using provided page", e)

            # Fetch version info from additional pages
            self._fetch_version_info_to_resources(session, base_url, resources)

        return self.parse_resources(resources)

    def _fetch_version_info_to_resources(self, session, base_url: str, resources: dict[str, Any]) -> None:
        """Fetch version info pages and add to resources dict.

        Args:
            session: Authenticated requests session
            base_url: Modem base URL
            resources: Dictionary to add fetched soups to
        """
        # Fetch index.htm for software version
        try:
            _LOGGER.debug("CM2000: Fetching index.htm for software version")
            index_response = session.get(f"{base_url}/index.htm", timeout=10)
            if index_response.status_code == 200:
                resources["/index.htm"] = BeautifulSoup(index_response.text, "html.parser")
        except Exception as e:
            _LOGGER.debug("CM2000: Error fetching index.htm for version: %s", e)

        # Fetch RouterStatus.htm for hardware version
        try:
            _LOGGER.debug("CM2000: Fetching RouterStatus.htm for hardware version")
            router_response = session.get(f"{base_url}/RouterStatus.htm", timeout=10)
            if router_response.status_code == 200:
                resources["/RouterStatus.htm"] = BeautifulSoup(router_response.text, "html.parser")
        except Exception as e:
            _LOGGER.debug("CM2000: Error fetching RouterStatus.htm for version: %s", e)

    def _fetch_version_info(self, session, base_url: str, system_info: dict) -> None:
        """Fetch software and hardware version from additional pages.

        Args:
            session: Authenticated requests session
            base_url: Modem base URL
            system_info: Dictionary to update with version info
        """
        # Fetch index.htm for software version (it's not in DocsisStatus.htm)
        try:
            _LOGGER.debug("CM2000: Fetching index.htm for software version")
            index_response = session.get(f"{base_url}/index.htm", timeout=10)
            if index_response.status_code == 200:
                index_soup = BeautifulSoup(index_response.text, "html.parser")
                sw_version = self._parse_software_version_from_index(index_soup)
                if sw_version:
                    system_info["software_version"] = sw_version
                    _LOGGER.debug("CM2000: Parsed software version: %s", sw_version)
        except Exception as e:
            _LOGGER.debug("CM2000: Error fetching index.htm for version: %s", e)

        # Fetch RouterStatus.htm for hardware version
        try:
            _LOGGER.debug("CM2000: Fetching RouterStatus.htm for hardware version")
            router_response = session.get(f"{base_url}/RouterStatus.htm", timeout=10)
            if router_response.status_code == 200:
                router_soup = BeautifulSoup(router_response.text, "html.parser")
                hw_version = self._parse_hardware_version_from_router_status(router_soup)
                if hw_version:
                    system_info["hardware_version"] = hw_version
                    _LOGGER.debug("CM2000: Parsed hardware version: %s", hw_version)
        except Exception as e:
            _LOGGER.debug("CM2000: Error fetching RouterStatus.htm for version: %s", e)

    def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:  # noqa: C901
        """Parse downstream channel data from DocsisStatus.htm.

        The CM2000 embeds channel data in JavaScript variables:
        - InitDsTableTagValue() function contains DOCSIS 3.0 QAM channels
        - InitDsOfdmTableTagValue() function contains DOCSIS 3.1 OFDM channels

        Returns:
            List of downstream channel dictionaries
        """
        channels: list[dict] = []

        try:
            # Parse DOCSIS 3.0 QAM channels
            qam_channels = self._parse_downstream_from_js(soup)
            channels.extend(qam_channels)

            # Fallback to HTML table if JS method fails
            if not qam_channels:
                qam_channels = self._parse_downstream_from_table(soup)
                channels.extend(qam_channels)

            _LOGGER.info("CM2000: Parsed %d downstream QAM channels", len(qam_channels))

            # Parse DOCSIS 3.1 OFDM channels
            ofdm_channels = self._parse_ofdm_downstream(soup)
            channels.extend(ofdm_channels)
            _LOGGER.info("CM2000: Parsed %d downstream OFDM channels", len(ofdm_channels))

        except Exception as e:
            _LOGGER.error("Error parsing CM2000 downstream channels: %s", e, exc_info=True)

        return channels

    def _parse_downstream_from_js(self, soup: BeautifulSoup) -> list[dict]:  # noqa: C901
        """Parse downstream channels from JavaScript variables."""
        channels: list[dict] = []

        try:
            regex_pattern = re.compile("InitDsTableTagValue")
            all_scripts = soup.find_all("script")

            for script in all_scripts:
                if script.string and regex_pattern.search(script.string):
                    # Extract the function body
                    func_match = re.search(
                        r"function InitDsTableTagValue\(\)[^{]*\{(.*?)\n\}", script.string, re.DOTALL
                    )
                    if not func_match:
                        continue

                    func_body = func_match.group(1)
                    # Remove block comments
                    func_body_clean = re.sub(r"/\*.*?\*/", "", func_body, flags=re.DOTALL)

                    # Find tagValueList
                    match = re.search(r"^\s+var tagValueList = [\"']([^\"']+)[\"']", func_body_clean, re.MULTILINE)
                    if not match:
                        continue

                    values = match.group(1).split("|")
                    _LOGGER.debug("CM2000 Downstream JS: Found %d values", len(values))

                    if len(values) < 10:  # Need at least count + 1 channel
                        continue

                    # First value is channel count
                    channel_count = int(values[0])
                    fields_per_channel = 9
                    idx = 1

                    for i in range(channel_count):
                        if idx + fields_per_channel > len(values):
                            break

                        try:
                            freq_str = values[idx + 4].replace(" Hz", "").strip()
                            freq = int(freq_str)
                            lock_status = values[idx + 1]

                            if freq == 0 or lock_status != "Locked":
                                idx += fields_per_channel
                                continue

                            channel = {
                                "channel_id": values[idx + 3],
                                "frequency": freq,
                                "power": float(values[idx + 5]),
                                "snr": float(values[idx + 6]),
                                "modulation": values[idx + 2],
                                "corrected": int(values[idx + 7]),
                                "uncorrected": int(values[idx + 8]),
                            }
                            channels.append(channel)

                        except (ValueError, IndexError) as e:
                            _LOGGER.warning("CM2000 Downstream: Error parsing channel %d: %s", i + 1, e)

                        idx += fields_per_channel

                    break  # Found data, stop searching

        except Exception as e:
            _LOGGER.debug("CM2000: JS downstream parsing failed: %s", e)

        return channels

    def _parse_downstream_from_table(self, soup: BeautifulSoup) -> list[dict]:  # noqa: C901
        """Parse downstream channels from HTML table (fallback method)."""
        channels: list[dict] = []

        try:
            # Look for downstream table by id or class
            ds_table = soup.find("table", {"id": "dsTable"})
            if not ds_table:
                # Try finding by header text
                tables = soup.find_all("table")
                for table in tables:
                    header = table.find("tr")
                    if header and "downstream" in header.get_text().lower():
                        ds_table = table
                        break

            if not ds_table:
                return channels

            rows = ds_table.find_all("tr")[1:]  # Skip header

            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 9:
                    continue

                try:
                    lock_status = cells[1].get_text(strip=True)
                    if lock_status != "Locked":
                        continue

                    freq_str = cells[4].get_text(strip=True).replace(" Hz", "").replace("Hz", "").strip()
                    freq = int(freq_str)
                    if freq == 0:
                        continue

                    channel = {
                        "channel_id": cells[3].get_text(strip=True),
                        "frequency": freq,
                        "power": float(cells[5].get_text(strip=True).replace(" dBmV", "").replace("dBmV", "")),
                        "snr": float(cells[6].get_text(strip=True).replace(" dB", "").replace("dB", "")),
                        "modulation": cells[2].get_text(strip=True),
                        "corrected": int(cells[7].get_text(strip=True)),
                        "uncorrected": int(cells[8].get_text(strip=True)),
                    }
                    channels.append(channel)

                except (ValueError, IndexError) as e:
                    _LOGGER.warning("CM2000 Downstream table: Error parsing row: %s", e)
                    continue

        except Exception as e:
            _LOGGER.debug("CM2000: Table downstream parsing failed: %s", e)

        return channels

    def parse_upstream(self, soup: BeautifulSoup) -> list[dict]:  # noqa: C901
        """Parse upstream channel data from DocsisStatus.htm.

        The CM2000 embeds channel data in JavaScript variables:
        - InitUsTableTagValue() function contains DOCSIS 3.0 ATDMA channels
        - InitUsOfdmaTableTagValue() function contains DOCSIS 3.1 OFDMA channels

        Returns:
            List of upstream channel dictionaries
        """
        channels: list[dict] = []

        try:
            # Parse DOCSIS 3.0 ATDMA channels
            atdma_channels = self._parse_upstream_from_js(soup)
            channels.extend(atdma_channels)

            # Fallback to HTML table if JS method fails
            if not atdma_channels:
                atdma_channels = self._parse_upstream_from_table(soup)
                channels.extend(atdma_channels)

            _LOGGER.info("CM2000: Parsed %d upstream ATDMA channels", len(atdma_channels))

            # Parse DOCSIS 3.1 OFDMA channels
            ofdma_channels = self._parse_ofdma_upstream(soup)
            channels.extend(ofdma_channels)
            _LOGGER.info("CM2000: Parsed %d upstream OFDMA channels", len(ofdma_channels))

        except Exception as e:
            _LOGGER.error("Error parsing CM2000 upstream channels: %s", e, exc_info=True)

        return channels

    def _parse_upstream_from_js(self, soup: BeautifulSoup) -> list[dict]:  # noqa: C901
        """Parse upstream channels from JavaScript variables."""
        channels: list[dict] = []

        try:
            regex_pattern = re.compile("InitUsTableTagValue")
            all_scripts = soup.find_all("script")

            for script in all_scripts:
                if script.string and regex_pattern.search(script.string):
                    func_match = re.search(
                        r"function InitUsTableTagValue\(\)[^{]*\{(.*?)\n\}", script.string, re.DOTALL
                    )
                    if not func_match:
                        continue

                    func_body = func_match.group(1)
                    func_body_clean = re.sub(r"/\*.*?\*/", "", func_body, flags=re.DOTALL)

                    match = re.search(r"^\s+var tagValueList = [\"']([^\"']+)[\"']", func_body_clean, re.MULTILINE)
                    if not match:
                        continue

                    values = match.group(1).split("|")
                    _LOGGER.debug("CM2000 Upstream JS: Found %d values", len(values))

                    if len(values) < 8:  # Need at least count + 1 channel
                        continue

                    channel_count = int(values[0])
                    fields_per_channel = 7
                    idx = 1

                    for i in range(channel_count):
                        if idx + fields_per_channel > len(values):
                            break

                        try:
                            freq_str = values[idx + 5].replace(" Hz", "").strip()
                            freq = int(freq_str)
                            lock_status = values[idx + 1]

                            if freq == 0 or lock_status != "Locked":
                                idx += fields_per_channel
                                continue

                            power_str = values[idx + 6].replace(" dBmV", "").strip()
                            channel = {
                                "channel_id": values[idx + 3],
                                "frequency": freq,
                                "power": float(power_str),
                                "channel_type": values[idx + 2],
                            }
                            channels.append(channel)

                        except (ValueError, IndexError) as e:
                            _LOGGER.warning("CM2000 Upstream: Error parsing channel %d: %s", i + 1, e)

                        idx += fields_per_channel

                    break

        except Exception as e:
            _LOGGER.debug("CM2000: JS upstream parsing failed: %s", e)

        return channels

    def _parse_upstream_from_table(self, soup: BeautifulSoup) -> list[dict]:  # noqa: C901
        """Parse upstream channels from HTML table (fallback method)."""
        channels: list[dict] = []

        try:
            us_table = soup.find("table", {"id": "usTable"})
            if not us_table:
                tables = soup.find_all("table")
                for table in tables:
                    header = table.find("tr")
                    if header and "upstream" in header.get_text().lower():
                        us_table = table
                        break

            if not us_table:
                return channels

            rows = us_table.find_all("tr")[1:]

            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 7:
                    continue

                try:
                    lock_status = cells[1].get_text(strip=True)
                    if lock_status != "Locked":
                        continue

                    freq_str = cells[5].get_text(strip=True).replace(" Hz", "").replace("Hz", "").strip()
                    freq = int(freq_str)
                    if freq == 0:
                        continue

                    channel = {
                        "channel_id": cells[3].get_text(strip=True),
                        "frequency": freq,
                        "power": float(cells[6].get_text(strip=True).replace(" dBmV", "").replace("dBmV", "")),
                        "channel_type": cells[2].get_text(strip=True),
                    }
                    channels.append(channel)

                except (ValueError, IndexError) as e:
                    _LOGGER.warning("CM2000 Upstream table: Error parsing row: %s", e)
                    continue

        except Exception as e:
            _LOGGER.debug("CM2000: Table upstream parsing failed: %s", e)

        return channels

    def _extract_tagvaluelist(self, soup: BeautifulSoup, func_name: str) -> list[str] | None:
        """Extract tagValueList values from a JavaScript function.

        Args:
            soup: BeautifulSoup object
            func_name: Name of the JS function (e.g., "InitDsOfdmTableTagValue")

        Returns:
            List of pipe-separated values or None if not found
        """
        regex_pattern = re.compile(func_name)
        for script in soup.find_all("script"):
            if not script.string or not regex_pattern.search(script.string):
                continue

            func_match = re.search(rf"function {func_name}\(\)[^{{]*\{{(.*?)\n\s*\}}", script.string, re.DOTALL)
            if not func_match:
                continue

            func_body = func_match.group(1)
            func_body_clean = re.sub(r"/\*.*?\*/", "", func_body, flags=re.DOTALL)

            match = re.search(r"var tagValueList = [\"']([^\"']+)[\"']", func_body_clean)
            if match:
                return match.group(1).split("|")

        return None

    def _parse_ofdm_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse OFDM downstream channels from InitDsOfdmTableTagValue.

        CM2000 OFDM format (12 fields per channel):
        count|num|lock|profile_ids|channel_id|frequency|power|snr|active_range|
              unerrored_cw|correctable_cw|uncorrectable_cw|...
        """
        channels: list[dict] = []

        try:
            values = self._extract_tagvaluelist(soup, "InitDsOfdmTableTagValue")
            if not values or len(values) < 12:
                return channels

            channel_count = int(values[0])
            fields_per_channel = 11
            idx = 1

            for i in range(channel_count):
                if idx + fields_per_channel > len(values):
                    break

                channel = self._parse_ofdm_downstream_channel(values, idx, i)
                if channel:
                    channels.append(channel)
                idx += fields_per_channel

        except Exception as e:
            _LOGGER.debug("CM2000: OFDM downstream parsing failed: %s", e)

        return channels

    def _parse_ofdm_downstream_channel(self, values: list[str], idx: int, channel_num: int) -> dict | None:
        """Parse a single OFDM downstream channel."""
        try:
            freq_str = values[idx + 4].replace(" Hz", "").strip()
            freq = int(freq_str)
            lock_status = values[idx + 1]

            if freq == 0 or lock_status != "Locked":
                return None

            power_str = values[idx + 5].replace(" dBmV", "").strip()
            snr_str = values[idx + 6].replace(" dB", "").strip()

            return {
                "channel_id": values[idx + 3],
                "frequency": freq,
                "power": float(power_str),
                "snr": float(snr_str),
                "modulation": "OFDM",
                "is_ofdm": True,
            }
        except (ValueError, IndexError) as e:
            _LOGGER.warning("CM2000 OFDM Downstream: Error parsing channel %d: %s", channel_num + 1, e)
            return None

    def _parse_ofdma_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse OFDMA upstream channels from InitUsOfdmaTableTagValue.

        CM2000 OFDMA format (6 fields per channel):
        count|num|lock|profile_id|channel_id|frequency|power|...
        """
        channels: list[dict] = []

        try:
            values = self._extract_tagvaluelist(soup, "InitUsOfdmaTableTagValue")
            if not values or len(values) < 7:
                return channels

            channel_count = int(values[0])
            fields_per_channel = 6
            idx = 1

            for i in range(channel_count):
                if idx + fields_per_channel > len(values):
                    break

                channel = self._parse_ofdma_upstream_channel(values, idx, i)
                if channel:
                    channels.append(channel)
                idx += fields_per_channel

        except Exception as e:
            _LOGGER.debug("CM2000: OFDMA upstream parsing failed: %s", e)

        return channels

    def _parse_ofdma_upstream_channel(self, values: list[str], idx: int, channel_num: int) -> dict | None:
        """Parse a single OFDMA upstream channel."""
        try:
            freq_str = values[idx + 4].replace(" Hz", "").strip()
            freq = int(freq_str)
            lock_status = values[idx + 1]

            if freq == 0 or lock_status != "Locked":
                return None

            power_str = values[idx + 5].replace(" dBmV", "").strip()

            return {
                "channel_id": values[idx + 3],
                "frequency": freq,
                "power": float(power_str),
                "channel_type": "OFDMA",
                "is_ofdm": True,
            }
        except (ValueError, IndexError) as e:
            _LOGGER.warning("CM2000 OFDMA Upstream: Error parsing channel %d: %s", channel_num + 1, e)
            return None

    def parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information from DocsisStatus.htm.

        Returns:
            Dictionary with available system info
        """
        info = {}

        try:
            # Try to extract from JavaScript InitTagValue function
            # Filter script tags manually to satisfy mypy (find_all with both name and string has typing issues)
            script_tags = [
                tag for tag in soup.find_all("script") if tag.string and re.search("InitTagValue", tag.string)
            ]

            for script in script_tags:
                if not script.string:
                    continue

                # Look for InitTagValue function
                func_match = re.search(r"function InitTagValue\(\)[^{]*\{(.*?)\n\}", script.string, re.DOTALL)
                if not func_match:
                    continue

                func_body = func_match.group(1)
                func_body_clean = re.sub(r"/\*.*?\*/", "", func_body, flags=re.DOTALL)

                match = re.search(r"var tagValueList = [\"']([^\"']+)[\"']", func_body_clean)
                if match:
                    values = match.group(1).split("|")
                    # Extract current system time (index 10)
                    if len(values) > 10 and values[10] and values[10] != "&nbsp;":
                        info["current_time"] = values[10]
                        _LOGGER.debug("CM2000: Parsed current time: %s", values[10])

                    # Extract system uptime (index 14) - CM2000 provides this!
                    if len(values) > 14 and values[14] and values[14] != "&nbsp;":
                        info["system_uptime"] = values[14]
                        _LOGGER.debug("CM2000: Parsed system uptime: %s", values[14])

                        # Calculate last boot time from uptime
                        boot_time = self._calculate_boot_time(values[14])
                        if boot_time:
                            info["last_boot_time"] = boot_time
                            _LOGGER.debug("CM2000: Calculated last boot time: %s", boot_time)

                    _LOGGER.debug("CM2000: Parsed system info from InitTagValue")
                    break

            # Also try to find firmware version from page content
            fw_match = re.search(r"Cable Firmware Version[:\s]*([^\s<]+)", str(soup))
            if fw_match:
                info["software_version"] = fw_match.group(1)

        except Exception as e:
            _LOGGER.error("Error parsing CM2000 system info: %s", e)

        return info

    def _calculate_boot_time(self, uptime_str: str) -> str | None:
        """Calculate boot time from uptime string.

        Args:
            uptime_str: Uptime string like "7 days 00:00:01" (days HH:MM:SS format)

        Returns:
            ISO format datetime string of boot time or None if parsing fails
        """
        from datetime import datetime, timedelta

        try:
            total_seconds = 0

            # Parse days (e.g., "7 days")
            days_match = re.search(r"(\d+)\s*days?", uptime_str, re.IGNORECASE)
            if days_match:
                total_seconds += int(days_match.group(1)) * 86400

            # Parse HH:MM:SS format (e.g., "00:00:01")
            time_match = re.search(r"(\d{1,2}):(\d{2}):(\d{2})", uptime_str)
            if time_match:
                hours = int(time_match.group(1))
                minutes = int(time_match.group(2))
                seconds = int(time_match.group(3))
                total_seconds += hours * 3600 + minutes * 60 + seconds

            if total_seconds == 0:
                return None

            # Calculate boot time: current time - uptime
            uptime_delta = timedelta(seconds=total_seconds)
            boot_time = datetime.now() - uptime_delta

            return boot_time.isoformat()

        except Exception as e:
            _LOGGER.error("Error calculating boot time from '%s': %s", uptime_str, e)
            return None

    def _extract_model(self, soup: BeautifulSoup) -> str | None:
        """Extract actual model name from HTML meta or title.

        The CM2000 includes model info in:
        - <META name="description" content='CM2000'>
        - <title>NETGEAR Modem CM2000</title>

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            Model name (e.g., "CM2000") or None if not found
        """
        # Try meta description first
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            content = meta.get("content")
            if isinstance(content, str) and content.strip():
                _LOGGER.debug("CM2000: Extracted model from meta description: %s", content.strip())
                return content.strip()

        # Fallback to title tag
        title = soup.find("title")
        if title and title.string:
            # Extract model from "NETGEAR Modem CM2000"
            match = re.search(r"(?:Modem|Gateway)\s+(\S+)", title.string)
            if match:
                model = match.group(1)
                _LOGGER.debug("CM2000: Extracted model from title: %s", model)
                return model

        _LOGGER.debug("CM2000: Could not extract model name from HTML")
        return None

    def _parse_hardware_version_from_router_status(self, soup: BeautifulSoup) -> str | None:
        """Parse hardware version from RouterStatus.htm.

        The CM2000 stores hardware version in RouterStatus.htm's tagValueList:
            var tagValueList = '1.01|V8.01.02|SERIAL|...'

        Index 0 contains the hardware version (e.g., "1.01").

        Args:
            soup: BeautifulSoup object of RouterStatus.htm

        Returns:
            Hardware version string or None if not found
        """
        try:
            for script in soup.find_all("script"):
                if not script.string or "tagValueList" not in script.string:
                    continue

                # Look for InitDashBoardTagValue or standalone tagValueList
                match = re.search(
                    r"var tagValueList = ['\"]([^'\"]+)['\"]",
                    script.string,
                )
                if match:
                    values = match.group(1).split("|")
                    if values and values[0]:
                        hw_version = values[0].strip()
                        if hw_version and hw_version != "&nbsp;":
                            _LOGGER.debug(
                                "CM2000: Found hardware version in RouterStatus.htm: %s",
                                hw_version,
                            )
                            return hw_version

        except Exception as e:
            _LOGGER.debug("CM2000: Error parsing hardware version from RouterStatus.htm: %s", e)

        return None

    def _parse_software_version_from_index(self, soup: BeautifulSoup) -> str | None:
        """Parse software version from index.htm.

        The CM2000 stores firmware version in index.htm's InitTagValue() function:
            function InitTagValue() {
                var tagValueList = 'V8.01.02|0|0|0|0|retail|...';
                return tagValueList.split("|");
            }

        Index 0 contains the firmware version (e.g., "V8.01.02").

        Args:
            soup: BeautifulSoup object of index.htm

        Returns:
            Firmware version string or None if not found
        """
        try:
            # Find script containing InitTagValue
            for script in soup.find_all("script"):
                if not script.string or "InitTagValue" not in script.string:
                    continue

                # Extract tagValueList from the function (first non-commented assignment)
                # Look for lines that start with whitespace then "var tagValueList"
                # Skip lines that start with "//" (comments)
                match = re.search(
                    r"function InitTagValue\(\)[^{]*\{[^}]*?^\s+var tagValueList = ['\"]([^'\"]+)['\"]",
                    script.string,
                    re.DOTALL | re.MULTILINE,
                )
                if match:
                    values = match.group(1).split("|")
                    if values and values[0]:
                        version = values[0].strip()
                        if version and version != "&nbsp;":
                            _LOGGER.debug("CM2000: Found firmware version in index.htm: %s", version)
                            return version

        except Exception as e:
            _LOGGER.debug("CM2000: Error parsing software version from index.htm: %s", e)

        return None

    def restart(self, session, base_url: str) -> bool:
        """Restart the modem.

        The CM2000 restart is done via RouterStatus.htm:
        1. Fetch RouterStatus.htm to get the dynamic form action URL
        2. POST to /goform/RouterStatus?id=XXXXX with buttonSelect=2

        Args:
            session: Authenticated requests session
            base_url: Modem base URL

        Returns:
            True if restart command was sent successfully
        """
        try:
            # Step 1: Fetch RouterStatus.htm to get the form action with dynamic ID
            _LOGGER.debug("CM2000: Fetching RouterStatus.htm for restart")
            status_response = session.get(f"{base_url}/RouterStatus.htm", timeout=10)

            if status_response.status_code != 200:
                _LOGGER.error("CM2000: Failed to fetch RouterStatus.htm, status %d", status_response.status_code)
                return False

            # Step 2: Extract form action URL with dynamic ID
            soup = BeautifulSoup(status_response.text, "html.parser")
            form = soup.find("form", {"action": re.compile(r"/goform/RouterStatus")})

            if not form:
                _LOGGER.error("CM2000: Could not find RouterStatus form")
                return False

            form_action = str(form.get("action", ""))
            if form_action.startswith("/"):
                restart_url = f"{base_url}{form_action}"
            else:
                restart_url = f"{base_url}/goform/RouterStatus"

            _LOGGER.debug("CM2000: Restart URL: %s", restart_url)

            # Step 3: POST with buttonSelect=2 to trigger reboot
            restart_data = {"buttonSelect": "2"}
            restart_response = session.post(restart_url, data=restart_data, timeout=10)

            if restart_response.status_code == 200:
                _LOGGER.info("CM2000: Restart command sent successfully")
                return True
            else:
                _LOGGER.error("CM2000: Restart failed with status %d", restart_response.status_code)
                return False

        except Exception as e:
            _LOGGER.error("CM2000: Error during restart: %s", e)
            return False
