# =============================================================================
# AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
#
# Source: modems/netgear/cm600/parser.py
# This file is synced from modems/ during build. Edit the source file, then run:
#     make sync
# =============================================================================

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

System info:
- Uptime: Available from DocsisStatus.asp in HH:MM:SS format (e.g., "1308:19:22")
- Last boot time: Calculated from uptime
- Hardware/firmware version: Available from RouterStatus.asp

Known limitations:
- Restart: Connection drops immediately on success (handled as expected behavior)

Related: Issue #3 (Netgear CM600 - Login Doesn't Work)
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


class NetgearCM600Parser(ModemParser):
    """Parser for Netgear CM600 cable modem."""

    # Auth handled by AuthDiscovery (v3.12.0+) - no auth_config needed
    # BasicAuth will be auto-detected via 401 response

    # URL patterns now in modem.yaml pages config

    # login() not needed - uses base class default (AuthDiscovery handles auth)

    def restart(self, session, base_url) -> bool:
        """Restart the modem.

        Args:
            session: Requests session (already authenticated)
            base_url: Base URL of the modem

        Returns:
            True if restart command sent successfully, False otherwise
        """
        from http.client import RemoteDisconnected

        from requests.exceptions import ChunkedEncodingError, ConnectionError

        try:
            restart_url = f"{base_url}/goform/RouterStatus"
            data = {"RsAction": "2"}

            _LOGGER.info("CM600: Sending reboot command to %s", restart_url)
            response = session.post(restart_url, data=data, timeout=10)

            # Log the response for debugging
            _LOGGER.info(
                "CM600: Reboot response - status=%d, length=%d bytes",
                response.status_code,
                len(response.text) if response.text else 0,
            )
            _LOGGER.debug("CM600: Reboot response body: %s", response.text[:500] if response.text else "(empty)")

            if response.status_code == 200:
                _LOGGER.info("CM600: Reboot command accepted by modem")
                return True
            else:
                _LOGGER.warning("CM600: Reboot command failed with status %d", response.status_code)
                return False

        except (RemoteDisconnected, ConnectionError, ChunkedEncodingError) as e:
            # Connection dropped = modem is rebooting (success!)
            _LOGGER.info("CM600: Modem rebooting (connection dropped as expected): %s", type(e).__name__)
            return True
        except Exception as e:
            _LOGGER.error("CM600: Error sending reboot command: %s", e)
            return False

    def parse_resources(self, resources: dict[str, Any]) -> dict:
        """Parse modem data from pre-fetched resources.

        Args:
            resources: Dictionary mapping paths to BeautifulSoup objects

        Returns:
            Dictionary with downstream, upstream, and system_info
        """
        # Get DocsisStatus page soup (channel data)
        docsis_soup = resources.get("/DocsisStatus.asp")
        if docsis_soup is None:
            # Fallback to any available soup
            for value in resources.values():
                if isinstance(value, BeautifulSoup):
                    docsis_soup = value
                    break

        if docsis_soup is None:
            return {"downstream": [], "upstream": [], "system_info": {}}

        # Get RouterStatus page soup (hw/fw version)
        router_soup = resources.get("/RouterStatus.asp")
        if router_soup is None:
            router_soup = docsis_soup

        # Parse channel data from DocsisStatus.asp
        downstream_channels = self.parse_downstream(docsis_soup)
        upstream_channels = self.parse_upstream(docsis_soup)

        # Parse system info from DocsisStatus.asp (uptime) and RouterStatus.asp (hw/fw version)
        system_info = self.parse_system_info(docsis_soup)

        # Merge system info from RouterStatus.asp (hw/fw versions)
        router_system_info = self._parse_router_system_info(router_soup)
        system_info.update(router_system_info)

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
                _LOGGER.debug("CM600: Fetching DocsisStatus.asp for channel data")
                docsis_url = f"{base_url}/DocsisStatus.asp"
                docsis_response = session.get(docsis_url, timeout=10)

                if docsis_response.status_code == 200:
                    resources["/DocsisStatus.asp"] = BeautifulSoup(docsis_response.text, "html.parser")
                    _LOGGER.debug("CM600: Successfully fetched DocsisStatus.asp (%d bytes)", len(docsis_response.text))
                else:
                    _LOGGER.warning(
                        "CM600: Failed to fetch DocsisStatus.asp, status %d - using provided page",
                        docsis_response.status_code,
                    )
            except Exception as e:
                _LOGGER.warning("CM600: Error fetching DocsisStatus.asp: %s - using provided page", e)

            # Also fetch RouterStatus.asp for hardware/firmware version
            try:
                _LOGGER.debug("CM600: Fetching RouterStatus.asp for system info")
                router_url = f"{base_url}/RouterStatus.asp"
                router_response = session.get(router_url, timeout=10)

                if router_response.status_code == 200:
                    resources["/RouterStatus.asp"] = BeautifulSoup(router_response.text, "html.parser")
                    _LOGGER.debug("CM600: Successfully fetched RouterStatus.asp (%d bytes)", len(router_response.text))
                else:
                    _LOGGER.warning(
                        "CM600: Failed to fetch RouterStatus.asp, status %d - using provided page",
                        router_response.status_code,
                    )
            except Exception as e:
                _LOGGER.warning("CM600: Error fetching RouterStatus.asp: %s - using provided page", e)

        return self.parse_resources(resources)

    def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:  # noqa: C901
        """Parse downstream channel data from DocsisStatus.asp.

        The CM600 includes channel data in HTML table with id "dsTable".
        Table structure:
        - Row 1: Headers
        - Rows 2+: Channel data with columns:
          Channel | Lock Status | Modulation | Channel ID | Frequency | Power | SNR | Correctables | Uncorrectables

        Returns:
            List of downstream channel dictionaries
        """
        channels: list[dict] = []

        try:
            # Find the downstream table
            ds_table = soup.find("table", {"id": "dsTable"})

            if not ds_table:
                _LOGGER.warning("CM600 Downstream: Could not find dsTable")
                return channels

            # Get all rows, skip the header row
            rows = ds_table.find_all("tr")[1:]  # Skip header
            _LOGGER.debug("CM600 Downstream: Found %d rows in dsTable", len(rows))

            for row in rows:
                try:
                    cells = row.find_all("td")

                    if len(cells) < 9:
                        _LOGGER.debug("CM600 Downstream: Skipping row with %d cells (expected 9)", len(cells))
                        continue

                    # Extract values from cells
                    # cells[0] = Channel number
                    # cells[1] = Lock Status
                    # cells[2] = Modulation
                    # cells[3] = Channel ID
                    # cells[4] = Frequency
                    # cells[5] = Power
                    # cells[6] = SNR
                    # cells[7] = Correctables
                    # cells[8] = Uncorrectables

                    lock_status = cells[1].get_text(strip=True)

                    # Skip unlocked channels
                    if lock_status != "Locked":
                        _LOGGER.debug("CM600 Downstream: Skipping unlocked channel")
                        continue

                    # Extract and clean numeric values
                    freq_str = cells[4].get_text(strip=True).replace(" Hz", "").replace("Hz", "").strip()
                    power_str = cells[5].get_text(strip=True).replace(" dBmV", "").replace("dBmV", "").strip()
                    snr_str = cells[6].get_text(strip=True).replace(" dB", "").replace("dB", "").strip()

                    freq = int(freq_str)

                    # Skip channels with 0 frequency (placeholder entries)
                    if freq == 0:
                        _LOGGER.debug("CM600 Downstream: Skipping channel with freq=0")
                        continue

                    channel = {
                        "channel_id": cells[3].get_text(strip=True),
                        "frequency": freq,
                        "power": float(power_str),
                        "snr": float(snr_str),
                        "modulation": cells[2].get_text(strip=True),
                        "corrected": int(cells[7].get_text(strip=True)),
                        "uncorrected": int(cells[8].get_text(strip=True)),
                    }

                    channels.append(channel)

                except (ValueError, IndexError) as e:
                    _LOGGER.warning("CM600 Downstream: Error parsing row: %s", e)
                    continue

            _LOGGER.info("Parsed %d downstream channels", len(channels))

        except Exception as e:
            _LOGGER.error("Error parsing CM600 downstream channels: %s", e, exc_info=True)

        return channels

    def parse_upstream(self, soup: BeautifulSoup) -> list[dict]:  # noqa: C901
        """Parse upstream channel data from DocsisStatus.asp.

        The CM600 includes channel data in HTML table with id "usTable".
        Table structure:
        - Row 1: Headers
        - Rows 2+: Channel data with columns:
          Channel | Lock Status | US Channel Type | Channel ID | Symbol Rate | Frequency | Power

        Returns:
            List of upstream channel dictionaries
        """
        channels: list[dict] = []

        try:
            # Find the upstream table
            us_table = soup.find("table", {"id": "usTable"})

            if not us_table:
                _LOGGER.warning("CM600 Upstream: Could not find usTable")
                return channels

            # Get all rows, skip the header row
            rows = us_table.find_all("tr")[1:]  # Skip header
            _LOGGER.debug("CM600 Upstream: Found %d rows in usTable", len(rows))

            for row in rows:
                try:
                    cells = row.find_all("td")

                    if len(cells) < 7:
                        _LOGGER.debug("CM600 Upstream: Skipping row with %d cells (expected 7)", len(cells))
                        continue

                    # Extract values from cells
                    # cells[0] = Channel number
                    # cells[1] = Lock Status
                    # cells[2] = US Channel Type
                    # cells[3] = Channel ID
                    # cells[4] = Symbol Rate
                    # cells[5] = Frequency
                    # cells[6] = Power

                    lock_status = cells[1].get_text(strip=True)

                    # Skip unlocked channels
                    if lock_status != "Locked":
                        _LOGGER.debug("CM600 Upstream: Skipping unlocked channel")
                        continue

                    # Extract and clean numeric values
                    freq_str = cells[5].get_text(strip=True).replace(" Hz", "").replace("Hz", "").strip()
                    power_str = cells[6].get_text(strip=True).replace(" dBmV", "").replace("dBmV", "").strip()

                    freq = int(freq_str)

                    # Skip channels with 0 frequency (placeholder entries)
                    if freq == 0:
                        _LOGGER.debug("CM600 Upstream: Skipping channel with freq=0")
                        continue

                    channel = {
                        "channel_id": cells[3].get_text(strip=True),
                        "frequency": freq,
                        "power": float(power_str),
                        "channel_type": cells[2].get_text(strip=True),
                    }

                    channels.append(channel)

                except (ValueError, IndexError) as e:
                    _LOGGER.warning("CM600 Upstream: Error parsing row: %s", e)
                    continue

            _LOGGER.info("Parsed %d upstream channels", len(channels))

        except Exception as e:
            _LOGGER.error("Error parsing CM600 upstream channels: %s", e, exc_info=True)

        return channels

    def _parse_router_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information from RouterStatus.asp.

        Extracts:
        - Hardware version
        - Firmware version

        Returns:
            Dictionary with hardware/firmware version info
        """
        info = {}

        try:
            # Look for JavaScript variable tagValueList which contains system info
            # Format: tagValueList = 'hw_ver|fw_ver|serial|...'
            script_tags = soup.find_all("script", string=re.compile("tagValueList"))  # type: ignore[call-overload]

            for script in script_tags:
                # Extract the tagValueList value
                match = re.search(r"var tagValueList = [\"']([^\"']+)[\"']", script.string or "")
                if match:
                    # Split by pipe delimiter
                    values = match.group(1).split("|")

                    if len(values) >= 2:
                        # Based on RouterStatus.asp structure:
                        # values[0] = Hardware Version
                        # values[1] = Firmware Version
                        if values[0] and values[0] != "":
                            info["hardware_version"] = values[0]
                        if values[1] and values[1] != "":
                            info["software_version"] = values[1]

                        _LOGGER.debug(
                            "Parsed CM600 system info from RouterStatus.asp: hw=%s, fw=%s", values[0], values[1]
                        )
                        break

        except Exception as e:
            _LOGGER.error("Error parsing CM600 RouterStatus system info: %s", e)

        return info

    def _calculate_boot_time(self, uptime_str: str) -> str | None:
        """
        Calculate boot time from uptime string.

        Args:
            uptime_str: Uptime string like "0d 1h 23m 45s"

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
            _LOGGER.error("Error calculating boot time from '%s': %s", uptime_str, e)
            return None

    def _extract_model(self, soup: BeautifulSoup) -> str | None:
        """Extract actual model name from HTML meta or title.

        The CM600 includes model info in:
        - <META name="description" content='CM600-100NAS'>
        - <title>NETGEAR Gateway CM600</title>

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            Model name (e.g., "CM600-100NAS") or None if not found
        """
        # Try meta description first (most reliable)
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            content = meta.get("content")
            if isinstance(content, str) and content.strip():
                _LOGGER.debug("CM600: Extracted model from meta description: %s", content.strip())
                return content.strip()

        # Fallback to title tag
        title = soup.find("title")
        if title and title.string:
            # Extract model from "NETGEAR Gateway CM600"
            match = re.search(r"Gateway\s+(\S+)", title.string)
            if match:
                model = match.group(1)
                _LOGGER.debug("CM600: Extracted model from title: %s", model)
                return model

        _LOGGER.debug("CM600: Could not extract model name from HTML")
        return None

    def parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information from DocsisStatus.asp.

        Extracts:
        - System uptime
        - Current system time

        Note: Hardware/firmware version should be parsed from RouterStatus.asp
        using _parse_router_system_info()

        Returns:
            Dictionary with available system info
        """
        info = {}

        try:
            # Try to extract System Up Time from DocsisStatus.asp
            # Format: <td id="SystemUpTime">...<b>System Up Time:</b> 0d 1h 23m 45s
            uptime_tag = soup.find("td", {"id": "SystemUpTime"})
            if uptime_tag:
                uptime_text = uptime_tag.get_text(strip=True)
                # Remove "System Up Time:" prefix
                uptime = uptime_text.replace("System Up Time:", "").strip()
                if uptime and uptime != "***IPv6***" and uptime != "Unknown" and uptime != "":
                    info["system_uptime"] = uptime
                    _LOGGER.debug("CM600: Parsed system uptime: %s", uptime)

                    # Calculate and add last boot time
                    boot_time = self._calculate_boot_time(uptime)
                    if boot_time:
                        info["last_boot_time"] = boot_time
                        _LOGGER.debug("CM600: Calculated last boot time: %s", boot_time)

            # Try to extract Current System Time from DocsisStatus.asp
            # Format: <td id="CurrentSystemTime">...<b>Current System Time:</b> Mon Nov 24 ... 2025
            time_tag = soup.find("td", {"id": "CurrentSystemTime"})
            if time_tag:
                time_text = time_tag.get_text(strip=True)
                # Remove "Current System Time:" prefix
                current_time = time_text.replace("Current System Time:", "").strip()
                if current_time and current_time != "***IPv6***" and current_time != "":
                    info["current_time"] = current_time
                    _LOGGER.debug("CM600: Parsed current time: %s", current_time)

        except Exception as e:
            _LOGGER.error("Error parsing CM600 system info: %s", e)

        return info
