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

Related: Issue ***REMOVED***3 (Netgear CM600 - Login Doesn't Work)
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
    priority = 50  ***REMOVED*** Standard priority

    ***REMOVED*** CM600 uses HTTP Basic Auth
    auth_config = BasicAuthConfig(
        strategy=AuthStrategyType.BASIC_HTTP,
    )

    ***REMOVED*** URL patterns to try for modem data
    url_patterns = [
        {"path": "/", "auth_method": "basic", "auth_required": False},
        {"path": "/index.html", "auth_method": "basic", "auth_required": False},
        {"path": "/DocsisStatus.asp", "auth_method": "basic", "auth_required": True},
        {"path": "/DashBoard.asp", "auth_method": "basic", "auth_required": True},
        {"path": "/RouterStatus.asp", "auth_method": "basic", "auth_required": True},
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
        ***REMOVED*** CM600 uses HTTP Basic Auth - use AuthFactory to set it up
        from custom_components.cable_modem_monitor.core.authentication import AuthFactory

        auth_strategy = AuthFactory.get_strategy(self.auth_config.strategy)
        success, _ = auth_strategy.login(session, base_url, username, password, self.auth_config)
        return success

    def restart(self, session, base_url) -> bool:
        """Restart the modem.

        Args:
            session: Requests session (already authenticated)
            base_url: Base URL of the modem

        Returns:
            True if restart command sent successfully, False otherwise
        """
        try:
            restart_url = f"{base_url}/goform/RouterStatus"
            data = {"RsAction": "2"}

            _LOGGER.info("CM600: Sending reboot command to %s", restart_url)
            response = session.post(restart_url, data=data, timeout=10)

            if response.status_code == 200:
                _LOGGER.info("CM600: Reboot command sent successfully")
                return True
            else:
                _LOGGER.warning("CM600: Reboot command failed with status %d", response.status_code)
                return False

        except Exception as e:
            _LOGGER.error("CM600: Error sending reboot command: %s", e)
            return False

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem.

        Args:
            soup: BeautifulSoup object of the page
            session: Requests session (optional, for multi-page parsing)
            base_url: Base URL of the modem (optional)

        Returns:
            Dictionary with downstream, upstream, and system_info
        """
        ***REMOVED*** CM600 requires fetching DocsisStatus.asp for channel data
        docsis_soup = soup  ***REMOVED*** Default to provided soup
        router_soup = soup  ***REMOVED*** Default to provided soup for system info

        if session and base_url:
            try:
                _LOGGER.debug("CM600: Fetching DocsisStatus.asp for channel data")
                docsis_url = f"{base_url}/DocsisStatus.asp"
                docsis_response = session.get(docsis_url, timeout=10)

                if docsis_response.status_code == 200:
                    docsis_soup = BeautifulSoup(docsis_response.text, "html.parser")
                    _LOGGER.debug("CM600: Successfully fetched DocsisStatus.asp (%d bytes)", len(docsis_response.text))
                else:
                    _LOGGER.warning(
                        "CM600: Failed to fetch DocsisStatus.asp, status %d - using provided page",
                        docsis_response.status_code,
                    )
            except Exception as e:
                _LOGGER.warning("CM600: Error fetching DocsisStatus.asp: %s - using provided page", e)

            ***REMOVED*** Also fetch RouterStatus.asp for hardware/firmware version
            try:
                _LOGGER.debug("CM600: Fetching RouterStatus.asp for system info")
                router_url = f"{base_url}/RouterStatus.asp"
                router_response = session.get(router_url, timeout=10)

                if router_response.status_code == 200:
                    router_soup = BeautifulSoup(router_response.text, "html.parser")
                    _LOGGER.debug("CM600: Successfully fetched RouterStatus.asp (%d bytes)", len(router_response.text))
                else:
                    _LOGGER.warning(
                        "CM600: Failed to fetch RouterStatus.asp, status %d - using provided page",
                        router_response.status_code,
                    )
            except Exception as e:
                _LOGGER.warning("CM600: Error fetching RouterStatus.asp: %s - using provided page", e)

        ***REMOVED*** Parse channel data from DocsisStatus.asp
        downstream_channels = self.parse_downstream(docsis_soup)
        upstream_channels = self.parse_upstream(docsis_soup)

        ***REMOVED*** Parse system info from DocsisStatus.asp (uptime) and RouterStatus.asp (hw/fw version)
        system_info = self.parse_system_info(docsis_soup)

        ***REMOVED*** Merge system info from RouterStatus.asp (hw/fw versions)
        router_system_info = self._parse_router_system_info(router_soup)
        system_info.update(router_system_info)

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
        ***REMOVED*** Check title tag
        title = soup.find("title")
        if title and "NETGEAR Gateway CM600" in title.text:
            _LOGGER.info("Detected Netgear CM600 from page title")
            return True

        ***REMOVED*** Check meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            content = meta_desc.get("content", "")
            ***REMOVED*** Ensure content is a string before checking
            if isinstance(content, str) and "CM600" in content:
                _LOGGER.info("Detected Netgear CM600 from meta description")
                return True

        ***REMOVED*** Check for CM600 in page text
        if "CM600" in html and "NETGEAR" in html.upper():
            _LOGGER.info("Detected Netgear CM600 from page content")
            return True

        return False

    def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:  ***REMOVED*** noqa: C901
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
            ***REMOVED*** Find the downstream table
            ds_table = soup.find("table", {"id": "dsTable"})

            if not ds_table:
                _LOGGER.warning("CM600 Downstream: Could not find dsTable")
                return channels

            ***REMOVED*** Get all rows, skip the header row
            rows = ds_table.find_all("tr")[1:]  ***REMOVED*** Skip header
            _LOGGER.debug("CM600 Downstream: Found %d rows in dsTable", len(rows))

            for row in rows:
                try:
                    cells = row.find_all("td")

                    if len(cells) < 9:
                        _LOGGER.debug("CM600 Downstream: Skipping row with %d cells (expected 9)", len(cells))
                        continue

                    ***REMOVED*** Extract values from cells
                    ***REMOVED*** cells[0] = Channel number
                    ***REMOVED*** cells[1] = Lock Status
                    ***REMOVED*** cells[2] = Modulation
                    ***REMOVED*** cells[3] = Channel ID
                    ***REMOVED*** cells[4] = Frequency
                    ***REMOVED*** cells[5] = Power
                    ***REMOVED*** cells[6] = SNR
                    ***REMOVED*** cells[7] = Correctables
                    ***REMOVED*** cells[8] = Uncorrectables

                    lock_status = cells[1].get_text(strip=True)

                    ***REMOVED*** Skip unlocked channels
                    if lock_status != "Locked":
                        _LOGGER.debug("CM600 Downstream: Skipping unlocked channel")
                        continue

                    ***REMOVED*** Extract and clean numeric values
                    freq_str = cells[4].get_text(strip=True).replace(" Hz", "").replace("Hz", "").strip()
                    power_str = cells[5].get_text(strip=True).replace(" dBmV", "").replace("dBmV", "").strip()
                    snr_str = cells[6].get_text(strip=True).replace(" dB", "").replace("dB", "").strip()

                    freq = int(freq_str)

                    ***REMOVED*** Skip channels with 0 frequency (placeholder entries)
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

    def parse_upstream(self, soup: BeautifulSoup) -> list[dict]:  ***REMOVED*** noqa: C901
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
            ***REMOVED*** Find the upstream table
            us_table = soup.find("table", {"id": "usTable"})

            if not us_table:
                _LOGGER.warning("CM600 Upstream: Could not find usTable")
                return channels

            ***REMOVED*** Get all rows, skip the header row
            rows = us_table.find_all("tr")[1:]  ***REMOVED*** Skip header
            _LOGGER.debug("CM600 Upstream: Found %d rows in usTable", len(rows))

            for row in rows:
                try:
                    cells = row.find_all("td")

                    if len(cells) < 7:
                        _LOGGER.debug("CM600 Upstream: Skipping row with %d cells (expected 7)", len(cells))
                        continue

                    ***REMOVED*** Extract values from cells
                    ***REMOVED*** cells[0] = Channel number
                    ***REMOVED*** cells[1] = Lock Status
                    ***REMOVED*** cells[2] = US Channel Type
                    ***REMOVED*** cells[3] = Channel ID
                    ***REMOVED*** cells[4] = Symbol Rate
                    ***REMOVED*** cells[5] = Frequency
                    ***REMOVED*** cells[6] = Power

                    lock_status = cells[1].get_text(strip=True)

                    ***REMOVED*** Skip unlocked channels
                    if lock_status != "Locked":
                        _LOGGER.debug("CM600 Upstream: Skipping unlocked channel")
                        continue

                    ***REMOVED*** Extract and clean numeric values
                    freq_str = cells[5].get_text(strip=True).replace(" Hz", "").replace("Hz", "").strip()
                    power_str = cells[6].get_text(strip=True).replace(" dBmV", "").replace("dBmV", "").strip()

                    freq = int(freq_str)

                    ***REMOVED*** Skip channels with 0 frequency (placeholder entries)
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
            ***REMOVED*** Look for JavaScript variable tagValueList which contains system info
            ***REMOVED*** Format: tagValueList = 'hw_ver|fw_ver|serial|...'
            script_tags = soup.find_all("script", string=re.compile("tagValueList"))  ***REMOVED*** type: ignore[call-overload]

            for script in script_tags:
                ***REMOVED*** Extract the tagValueList value
                match = re.search(r"var tagValueList = [\"']([^\"']+)[\"']", script.string or "")
                if match:
                    ***REMOVED*** Split by pipe delimiter
                    values = match.group(1).split("|")

                    if len(values) >= 2:
                        ***REMOVED*** Based on RouterStatus.asp structure:
                        ***REMOVED*** values[0] = Hardware Version
                        ***REMOVED*** values[1] = Firmware Version
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
            ***REMOVED*** Try to extract System Up Time from DocsisStatus.asp
            ***REMOVED*** Format: <td id="SystemUpTime">...<b>System Up Time:</b> 0d 1h 23m 45s
            uptime_tag = soup.find("td", {"id": "SystemUpTime"})
            if uptime_tag:
                uptime_text = uptime_tag.get_text(strip=True)
                ***REMOVED*** Remove "System Up Time:" prefix
                uptime = uptime_text.replace("System Up Time:", "").strip()
                if uptime and uptime != "***IPv6***" and uptime != "Unknown" and uptime != "":
                    info["system_uptime"] = uptime
                    _LOGGER.debug("CM600: Parsed system uptime: %s", uptime)

            ***REMOVED*** Try to extract Current System Time from DocsisStatus.asp
            ***REMOVED*** Format: <td id="CurrentSystemTime">...<b>Current System Time:</b> Mon Nov 24 ... 2025
            time_tag = soup.find("td", {"id": "CurrentSystemTime"})
            if time_tag:
                time_text = time_tag.get_text(strip=True)
                ***REMOVED*** Remove "Current System Time:" prefix
                current_time = time_text.replace("Current System Time:", "").strip()
                if current_time and current_time != "***IPv6***" and current_time != "":
                    info["current_time"] = current_time
                    _LOGGER.debug("CM600: Parsed current time: %s", current_time)

        except Exception as e:
            _LOGGER.error("Error parsing CM600 system info: %s", e)

        return info
