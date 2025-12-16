"""Parser for Netgear CM1200 cable modem.

The Netgear CM1200 is a DOCSIS 3.1 cable modem with multi-gigabit capability.

Key pages:
- / or /index.htm: Main page (requires auth)
- /DocsisStatus.htm: DOCSIS channel data (REQUIRED for parsing, auth required)

Authentication: HTTP Basic Auth
- Default username: admin
- Password: User-configured

Data format (tagValueList):
Same JavaScript-embedded format as CM2000, but with slightly different upstream
field order (Symbol Rate comes before Frequency).

Channel data:
- Up to 32 downstream (DOCSIS 3.0, QAM256)
- Up to 8 upstream (DOCSIS 3.0, ATDMA)
- OFDM support may vary by ISP configuration

Related: Issue #63 (Netgear CM1200 Support Request)
Contributor: @DeFlanko
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import BasicAuthConfig

from ..base_parser import ModemCapability, ModemParser, ParserStatus

_LOGGER = logging.getLogger(__name__)


class NetgearCM1200Parser(ModemParser):
    """Parser for Netgear CM1200 cable modem."""

    name = "Netgear CM1200"
    manufacturer = "Netgear"
    models = ["CM1200"]
    priority = 50  # Standard priority

    # Parser status - awaiting user confirmation
    status = ParserStatus.AWAITING_VERIFICATION
    verification_source = "https://github.com/solentlabs/cable_modem_monitor/issues/63"

    # Device metadata
    release_date = "2019"
    docsis_version = "3.1"
    fixtures_path = "tests/parsers/netgear/fixtures/cm1200"

    # CM1200 uses HTTP Basic authentication
    auth_config = BasicAuthConfig()

    # Capabilities - CM1200 provides channel data and system info
    capabilities = {
        ModemCapability.DOWNSTREAM_CHANNELS,
        ModemCapability.UPSTREAM_CHANNELS,
        ModemCapability.OFDM_DOWNSTREAM,
        ModemCapability.OFDM_UPSTREAM,
        ModemCapability.SYSTEM_UPTIME,
        ModemCapability.LAST_BOOT_TIME,
        ModemCapability.CURRENT_TIME,
    }

    # URL patterns to try for modem data
    url_patterns = [
        {"path": "/", "auth_method": "basic", "auth_required": True},
        {"path": "/DocsisStatus.htm", "auth_method": "basic", "auth_required": True},
    ]

    def login(self, session, base_url: str, username: str, password: str) -> tuple[bool, str | None]:
        """Perform HTTP Basic authentication.

        HTTP Basic auth is handled by requests via the session.auth attribute.
        This method sets up the credentials and verifies login success.

        Args:
            session: Requests session
            base_url: Modem base URL
            username: Username for authentication
            password: Password for authentication

        Returns:
            tuple[bool, str | None]: (success, authenticated_html)
        """
        if not username or not password:
            _LOGGER.debug("CM1200: No credentials provided, skipping login")
            return (True, None)

        try:
            # Set HTTP Basic auth credentials on the session
            session.auth = (username, password)

            # Verify by fetching DocsisStatus.htm
            _LOGGER.debug("CM1200: Testing HTTP Basic auth via DocsisStatus.htm")
            response = session.get(f"{base_url}/DocsisStatus.htm", timeout=10)

            if response.status_code == 401:
                _LOGGER.warning("CM1200: HTTP Basic auth failed (401 Unauthorized)")
                return (False, None)

            if response.status_code == 200 and (
                "InitDsTableTagValue" in response.text or "InitUsTableTagValue" in response.text
            ):
                _LOGGER.info("CM1200: HTTP Basic auth successful")
                return (True, response.text)

            _LOGGER.warning("CM1200: Unexpected response status %d", response.status_code)
            return (False, None)

        except Exception as e:
            _LOGGER.error("CM1200: Login exception: %s", e, exc_info=True)
            return (False, None)

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem.

        Args:
            soup: BeautifulSoup object of the page
            session: Requests session (optional, for multi-page parsing)
            base_url: Base URL of the modem (optional)

        Returns:
            Dictionary with downstream, upstream, and system_info
        """
        # CM1200 requires fetching DocsisStatus.htm for channel data
        docsis_soup = soup  # Default to provided soup

        if session and base_url:
            try:
                _LOGGER.debug("CM1200: Fetching DocsisStatus.htm for channel data")
                docsis_url = f"{base_url}/DocsisStatus.htm"
                docsis_response = session.get(docsis_url, timeout=10)

                if docsis_response.status_code == 200:
                    docsis_soup = BeautifulSoup(docsis_response.text, "html.parser")
                    _LOGGER.debug("CM1200: Successfully fetched DocsisStatus.htm (%d bytes)", len(docsis_response.text))
                else:
                    _LOGGER.warning(
                        "CM1200: Failed to fetch DocsisStatus.htm, status %d - using provided page",
                        docsis_response.status_code,
                    )
            except Exception as e:
                _LOGGER.warning("CM1200: Error fetching DocsisStatus.htm: %s - using provided page", e)

        # Parse channel data from DocsisStatus.htm
        downstream_channels = self.parse_downstream(docsis_soup)
        upstream_channels = self.parse_upstream(docsis_soup)

        # Parse system info from DocsisStatus.htm (uptime, current time)
        system_info = self.parse_system_info(docsis_soup)

        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Netgear CM1200.

        Detection strategy:
        - Check for "NETGEAR Modem CM1200" in title
        - Check for meta description containing "CM1200"

        Args:
            soup: BeautifulSoup object of the page
            url: URL that was fetched
            html: Raw HTML string

        Returns:
            True if this is a Netgear CM1200, False otherwise
        """
        # Check title tag
        title = soup.find("title")
        if title and "CM1200" in title.text and "NETGEAR" in title.text:
            _LOGGER.info("Detected Netgear CM1200 from page title")
            return True

        # Check meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            content = meta_desc.get("content", "")
            if isinstance(content, str) and "CM1200" in content:
                _LOGGER.info("Detected Netgear CM1200 from meta description")
                return True

        return False

    def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream channel data from DocsisStatus.htm.

        The CM1200 embeds channel data in JavaScript variables.
        Format:
        - InitDsTableTagValue() function contains tagValueList (DOCSIS 3.0 QAM channels)
        - InitDsOfdmTableTagValue() function contains OFDM channels (DOCSIS 3.1)

        Returns:
            List of downstream channel dictionaries
        """
        channels: list[dict] = []

        try:
            # Parse DOCSIS 3.0 QAM channels
            qam_channels = self._parse_downstream_from_js(soup)
            channels.extend(qam_channels)
            _LOGGER.info("CM1200: Parsed %d downstream QAM channels", len(qam_channels))

            # Parse DOCSIS 3.1 OFDM channels
            ofdm_channels = self._parse_ofdm_downstream(soup)
            channels.extend(ofdm_channels)
            _LOGGER.info("CM1200: Parsed %d downstream OFDM channels", len(ofdm_channels))

        except Exception as e:
            _LOGGER.error("Error parsing CM1200 downstream channels: %s", e, exc_info=True)

        return channels

    def _extract_tagvaluelist(self, soup: BeautifulSoup, func_name: str) -> list[str] | None:
        """Extract tagValueList values from a JavaScript function.

        Args:
            soup: BeautifulSoup object
            func_name: Name of the JS function (e.g., "InitDsTableTagValue")

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

    def _parse_downstream_from_js(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream channels from JavaScript variables."""
        channels: list[dict] = []

        try:
            values = self._extract_tagvaluelist(soup, "InitDsTableTagValue")
            if not values or len(values) < 10:
                return channels

            _LOGGER.debug("CM1200 Downstream JS: Found %d values", len(values))

            channel_count = int(values[0])
            fields_per_channel = 9
            idx = 1

            for i in range(channel_count):
                if idx + fields_per_channel > len(values):
                    break

                channel = self._parse_downstream_channel(values, idx, i)
                if channel:
                    channels.append(channel)
                idx += fields_per_channel

        except Exception as e:
            _LOGGER.debug("CM1200: JS downstream parsing failed: %s", e)

        return channels

    def _parse_downstream_channel(self, values: list[str], idx: int, channel_num: int) -> dict | None:
        """Parse a single downstream channel from tagValueList values."""
        try:
            freq_str = values[idx + 4].replace(" Hz", "").strip()
            freq = int(freq_str)
            lock_status = values[idx + 1]

            if freq == 0 or lock_status != "Locked":
                return None

            return {
                "channel_id": values[idx + 3],
                "frequency": freq,
                "power": float(values[idx + 5]),
                "snr": float(values[idx + 6]),
                "modulation": values[idx + 2],
                "corrected": int(values[idx + 7]),
                "uncorrected": int(values[idx + 8]),
            }
        except (ValueError, IndexError) as e:
            _LOGGER.warning("CM1200 Downstream: Error parsing channel %d: %s", channel_num + 1, e)
            return None

    def _parse_ofdm_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse OFDM downstream channels from InitDsOfdmTableTagValue.

        OFDM format: count|num|lock|subcarriers|id|frequency|power|snr|active_range|...|
        """
        channels: list[dict] = []

        try:
            values = self._extract_tagvaluelist(soup, "InitDsOfdmTableTagValue")
            if not values or len(values) < 12:
                return channels

            channel_count = int(values[0])
            fields_per_channel = 12
            idx = 1

            for i in range(channel_count):
                if idx + fields_per_channel > len(values):
                    break

                channel = self._parse_ofdm_downstream_channel(values, idx, i)
                if channel:
                    channels.append(channel)
                idx += fields_per_channel

        except Exception as e:
            _LOGGER.debug("CM1200: OFDM downstream parsing failed: %s", e)

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
            _LOGGER.warning("CM1200 OFDM Downstream: Error parsing channel %d: %s", channel_num + 1, e)
            return None

    def parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream channel data from DocsisStatus.htm.

        Returns:
            List of upstream channel dictionaries
        """
        channels: list[dict] = []

        try:
            # Parse DOCSIS 3.0 ATDMA channels
            atdma_channels = self._parse_upstream_from_js(soup)
            channels.extend(atdma_channels)
            _LOGGER.info("CM1200: Parsed %d upstream ATDMA channels", len(atdma_channels))

            # Parse DOCSIS 3.1 OFDMA channels
            ofdma_channels = self._parse_ofdma_upstream(soup)
            channels.extend(ofdma_channels)
            _LOGGER.info("CM1200: Parsed %d upstream OFDMA channels", len(ofdma_channels))

        except Exception as e:
            _LOGGER.error("Error parsing CM1200 upstream channels: %s", e, exc_info=True)

        return channels

    def _parse_upstream_from_js(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream channels from JavaScript variables.

        CM1200 upstream format:
        count|num|lock|type|channel_id|symbol_rate|frequency|power
        Note: Symbol Rate comes BEFORE Frequency (different from CM2000)
        """
        channels: list[dict] = []

        try:
            values = self._extract_tagvaluelist(soup, "InitUsTableTagValue")
            if not values or len(values) < 8:
                return channels

            _LOGGER.debug("CM1200 Upstream JS: Found %d values", len(values))

            channel_count = int(values[0])
            fields_per_channel = 7
            idx = 1

            for i in range(channel_count):
                if idx + fields_per_channel > len(values):
                    break

                channel = self._parse_upstream_channel(values, idx, i)
                if channel:
                    channels.append(channel)
                idx += fields_per_channel

        except Exception as e:
            _LOGGER.debug("CM1200: JS upstream parsing failed: %s", e)

        return channels

    def _parse_upstream_channel(self, values: list[str], idx: int, channel_num: int) -> dict | None:
        """Parse a single upstream channel from tagValueList values."""
        try:
            # CM1200: Symbol Rate at idx+4, Frequency at idx+5
            freq_str = values[idx + 5].replace(" Hz", "").strip()
            freq = int(freq_str)
            lock_status = values[idx + 1]

            if freq == 0 or lock_status != "Locked":
                return None

            power_str = values[idx + 6].replace(" dBmV", "").strip()
            return {
                "channel_id": values[idx + 3],
                "frequency": freq,
                "power": float(power_str),
                "channel_type": values[idx + 2],
                "symbol_rate": int(values[idx + 4]),
            }
        except (ValueError, IndexError) as e:
            _LOGGER.warning("CM1200 Upstream: Error parsing channel %d: %s", channel_num + 1, e)
            return None

    def _parse_ofdma_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse OFDMA upstream channels from InitUsOfdmaTableTagValue.

        OFDMA format: count|num|lock|channels|id|frequency|power|...
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
            _LOGGER.debug("CM1200: OFDMA upstream parsing failed: %s", e)

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
            _LOGGER.warning("CM1200 OFDMA Upstream: Error parsing channel %d: %s", channel_num + 1, e)
            return None

    def parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information from DocsisStatus.htm.

        Returns:
            Dictionary with available system info
        """
        info: dict = {}

        try:
            # Try to extract from JavaScript InitTagValue function
            script_tags = [
                tag for tag in soup.find_all("script") if tag.string and re.search("InitTagValue", tag.string)
            ]

            for script in script_tags:
                if not script.string:
                    continue

                # Look for InitTagValue function
                func_match = re.search(r"function InitTagValue\(\)[^{]*\{(.*?)\n\s*\}", script.string, re.DOTALL)
                if not func_match:
                    continue

                func_body = func_match.group(1)
                # Remove block comments and line comments
                func_body_clean = re.sub(r"/\*.*?\*/", "", func_body, flags=re.DOTALL)
                func_body_clean = re.sub(r"//.*$", "", func_body_clean, flags=re.MULTILINE)

                match = re.search(r"var tagValueList = [\"']([^\"']+)[\"']", func_body_clean)
                if match:
                    values = match.group(1).split("|")
                    # Extract current system time (index 10)
                    if len(values) > 10 and values[10] and values[10] != "&nbsp;":
                        info["current_time"] = values[10]
                        _LOGGER.debug("CM1200: Parsed current time: %s", values[10])

                    # Extract system uptime (index 14)
                    if len(values) > 14 and values[14] and values[14] != "&nbsp;":
                        info["system_uptime"] = values[14]
                        _LOGGER.debug("CM1200: Parsed system uptime: %s", values[14])

                        # Calculate last boot time from uptime
                        boot_time = self._calculate_boot_time(values[14])
                        if boot_time:
                            info["last_boot_time"] = boot_time
                            _LOGGER.debug("CM1200: Calculated last boot time: %s", boot_time)

                    _LOGGER.debug("CM1200: Parsed system info from InitTagValue")
                    break

        except Exception as e:
            _LOGGER.error("Error parsing CM1200 system info: %s", e)

        return info

    def _calculate_boot_time(self, uptime_str: str) -> str | None:
        """Calculate boot time from uptime string.

        Args:
            uptime_str: Uptime string like "39 days 15:47:33" (days HH:MM:SS format)

        Returns:
            ISO format datetime string of boot time or None if parsing fails
        """
        from datetime import datetime, timedelta

        try:
            total_seconds = 0

            # Parse days (e.g., "39 days")
            days_match = re.search(r"(\d+)\s*days?", uptime_str, re.IGNORECASE)
            if days_match:
                total_seconds += int(days_match.group(1)) * 86400

            # Parse HH:MM:SS format (e.g., "15:47:33")
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
