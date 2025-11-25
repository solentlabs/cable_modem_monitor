"""Parser for Technicolor XB7 cable modem."""

from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import RedirectFormAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType
from custom_components.cable_modem_monitor.lib.utils import extract_float, extract_number

from ..base_parser import ModemCapability, ModemParser

_LOGGER = logging.getLogger(__name__)


class TechnicolorXB7Parser(ModemParser):
    """Parser for Technicolor XB7 cable modem (Rogers, Comcast)."""

    name = "Technicolor XB7"
    manufacturer = "Technicolor"
    models = ["XB7", "CGM4331COM"]

    ***REMOVED*** Verification status
    verified = False  ***REMOVED*** No confirmed user reports
    verification_source = None  ***REMOVED*** Needs user verification

    ***REMOVED*** New authentication configuration (declarative)
    auth_config = RedirectFormAuthConfig(
        strategy=AuthStrategyType.REDIRECT_FORM,
        login_url="/check.jst",
        username_field="username",
        password_field="password",
        success_redirect_pattern="/at_a_glance.jst",
        authenticated_page_url="/network_setup.jst",
    )

    url_patterns = [
        {"path": "/network_setup.jst", "auth_method": "form", "auth_required": True},
    ]

    ***REMOVED*** Capabilities - Technicolor XB7 provides full system info
    capabilities = {
        ModemCapability.DOWNSTREAM_CHANNELS,
        ModemCapability.UPSTREAM_CHANNELS,
        ModemCapability.SYSTEM_UPTIME,
        ModemCapability.LAST_BOOT_TIME,
        ModemCapability.SOFTWARE_VERSION,
    }

    def login(self, session, base_url, username, password) -> tuple[bool, str | None]:
        """
        XB7 uses form-based authentication.

        Login flow:
        1. POST credentials to /check.jst
        2. Receives redirect to /at_a_glance.jst
        3. Can then access /network_setup.jst

        Args:
            session: requests session object
            base_url: modem base URL (e.g., http://10.0.0.1)
            username: admin username
            password: admin password

        Returns:
            tuple: (success: bool, html: str) - authenticated HTML from network_setup.jst
        """
        if not username or not password:
            _LOGGER.debug("No credentials provided for XB7, attempting without auth")
            return False, None

        try:
            ***REMOVED*** Step 1: POST credentials to check.jst
            login_url = f"{base_url}/check.jst"
            login_data = {
                "username": username,
                "password": password,
            }

            _LOGGER.debug("XB7: Posting credentials to %s", login_url)
            response = session.post(login_url, data=login_data, timeout=10, allow_redirects=True)

            if response.status_code != 200:
                _LOGGER.error("XB7 login failed with status %s", response.status_code)
                return False, None

            ***REMOVED*** Step 2: Check if we got redirected to at_a_glance.jst (successful login)
            ***REMOVED*** Validate redirect URL is on the same host for security
            from urllib.parse import urlparse

            redirect_parsed = urlparse(response.url)
            base_parsed = urlparse(base_url)

            ***REMOVED*** Security check: Ensure redirect is to same host
            if redirect_parsed.hostname != base_parsed.hostname:
                _LOGGER.error("XB7: Security violation - redirect to different host: %s", response.url)
                return False, None

            if "at_a_glance.jst" in response.url:
                _LOGGER.debug("XB7: Login successful, redirected to at_a_glance.jst")
            else:
                _LOGGER.warning("XB7: Unexpected redirect to %s", response.url)

            ***REMOVED*** Step 3: Now fetch the network_setup.jst page with authenticated session
            status_url = f"{base_url}/network_setup.jst"
            _LOGGER.debug("XB7: Fetching %s with authenticated session", status_url)
            status_response = session.get(status_url, timeout=10)

            if status_response.status_code != 200:
                _LOGGER.error("XB7: Failed to fetch status page, status %s", status_response.status_code)
                return False, None

            _LOGGER.info(
                "XB7: Successfully authenticated and fetched status page (%s bytes)", len(status_response.text)
            )
            return True, status_response.text

        except (requests.exceptions.Timeout, requests.exceptions.ReadTimeout) as e:
            ***REMOVED*** Timeout is common when modem is busy/rebooting - log at debug level
            _LOGGER.debug("XB7 login timeout (modem may be busy or rebooting): %s", str(e))
            return False, None

        except requests.exceptions.ConnectionError as e:
            ***REMOVED*** Connection errors should be logged but not with full stack trace
            _LOGGER.warning("XB7 login connection error: %s", str(e))
            return False, None

        except requests.exceptions.RequestException as e:
            ***REMOVED*** Other request errors
            _LOGGER.warning("XB7 login request failed: %s", str(e))
            _LOGGER.debug("XB7 login exception details:", exc_info=True)  ***REMOVED*** Full trace only at debug
            return False, None

        except Exception as e:
            ***REMOVED*** Unexpected errors should still log details
            _LOGGER.error("XB7 login unexpected exception: %s", str(e), exc_info=True)
            return False, None

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """
        Detect if this is a Technicolor XB7 modem.

        Detection criteria:
        1. URL contains "network_setup.jst"
        2. HTML contains "Channel Bonding Value" with netWidth divs (XB7-specific)
        """
        ***REMOVED*** Primary detection: URL pattern
        if "network_setup.jst" in url.lower():
            _LOGGER.debug("XB7 detected by URL pattern: network_setup.jst")
            return True

        ***REMOVED*** Secondary detection: Content-based
        if "Channel Bonding Value" in html and soup.find_all("div", class_="netWidth"):
            _LOGGER.debug("XB7 detected by content: Channel Bonding Value + netWidth divs")
            return True

        return False

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the XB7 modem."""
        downstream_channels = self._parse_downstream(soup)
        upstream_channels = self._parse_upstream(soup)
        system_info = self._parse_system_info(soup)

        ***REMOVED*** Parse primary channel
        primary_channel_id = self._parse_primary_channel(soup)
        if primary_channel_id:
            system_info["primary_downstream_channel"] = primary_channel_id

        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    def _parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """
        Parse downstream channel data from XB7.

        XB7 uses transposed table format:
        - Rows = Metrics (Channel ID, Lock Status, Frequency, SNR, Power, Modulation)
        - Columns = Channels (34 downstream channels)
        - Each cell contains a <div class="netWidth">value</div>
        """
        downstream_channels = []

        try:
            tables = soup.find_all("table", class_="data")
            _LOGGER.debug("Found %s tables in XB7 HTML", len(tables))

            for table in tables:
                ***REMOVED*** Find thead with "Downstream" text
                thead = table.find("thead")
                if not thead:
                    continue

                header_text = thead.get_text()
                if "Downstream" not in header_text or "Channel Bonding Value" not in header_text:
                    continue

                _LOGGER.debug("Found XB7 downstream table")
                tbody = table.find("tbody")
                if not tbody:
                    continue

                rows = tbody.find_all("tr", recursive=False)
                downstream_channels = self._parse_xb7_transposed_table(rows, is_upstream=False)

                ***REMOVED*** Look for error codewords table
                error_channels = self._parse_error_codewords(soup)
                if error_channels:
                    self._merge_error_stats(downstream_channels, error_channels)

                break

            _LOGGER.debug("XB7 parsing found %s downstream channels", len(downstream_channels))

        except Exception as e:
            _LOGGER.error(f"Error parsing XB7 downstream: {e}", exc_info=True)

        return downstream_channels

    def _parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """
        Parse upstream channel data from XB7.

        XB7 upstream includes additional fields:
        - Symbol Rate (XB7-specific)
        - Channel Type (XB7-specific: TDMA, ATDMA, TDMA_AND_ATDMA, OFDMA)
        """
        upstream_channels = []

        try:
            tables = soup.find_all("table", class_="data")

            for table in tables:
                ***REMOVED*** Find thead with "Upstream" text
                thead = table.find("thead")
                if not thead:
                    continue

                header_text = thead.get_text()
                if "Upstream" not in header_text or "Channel Bonding Value" not in header_text:
                    continue

                ***REMOVED*** Make sure it's not downstream table
                if "Downstream" in header_text:
                    continue

                _LOGGER.debug("Found XB7 upstream table")
                tbody = table.find("tbody")
                if not tbody:
                    continue

                rows = tbody.find_all("tr", recursive=False)
                upstream_channels = self._parse_xb7_transposed_table(rows, is_upstream=True)
                break

            _LOGGER.debug("XB7 parsing found %s upstream channels", len(upstream_channels))

        except Exception as e:
            _LOGGER.error(f"Error parsing XB7 upstream: {e}", exc_info=True)

        return upstream_channels

    def _build_xb7_data_map(self, rows: list) -> tuple[dict, int]:
        """Build data map from XB7 transposed table rows.

        Returns:
            Tuple of (data_map, channel_count)
        """
        data_map = {}
        channel_count = 0

        for row in rows:
            ***REMOVED*** First cell is the row label (th)
            label_cell = row.find("th", class_="row-label")
            if not label_cell:
                continue

            ***REMOVED*** Get only direct text, not from nested divs
            label = "".join(label_cell.find_all(string=True, recursive=False)).strip()
            if not label:
                ***REMOVED*** Fallback if no direct text
                label = label_cell.get_text(strip=True)

            ***REMOVED*** Extract all netWidth div values from this row
            value_cells = row.find_all("td")
            values = []
            for cell in value_cells:
                div = cell.find("div", class_="netWidth")
                if div:
                    values.append(div.get_text(strip=True))
                else:
                    values.append(cell.get_text(strip=True))

            ***REMOVED*** Update channel count from longest row
            if len(values) > channel_count:
                channel_count = len(values)

            data_map[label] = values
            _LOGGER.debug("XB7 row '%s': %d values", label, len(values))

        return data_map, channel_count

    def _extract_channel_id(self, data_map: dict, index: int) -> str | None:
        """Extract channel ID from data_map at given index.

        Returns:
            Channel ID as string or None if missing/invalid
        """
        if "Channel ID" not in data_map or index >= len(data_map["Channel ID"]):
            return None

        channel_id = extract_number(data_map["Channel ID"][index])
        return str(channel_id) if channel_id is not None else None

    def _extract_common_fields(self, data_map: dict, index: int, channel_data: dict) -> None:
        """Extract common fields for both upstream and downstream channels."""
        if "Lock Status" in data_map and index < len(data_map["Lock Status"]):
            channel_data["lock_status"] = data_map["Lock Status"][index]

        if "Frequency" in data_map and index < len(data_map["Frequency"]):
            freq_text = data_map["Frequency"][index]
            channel_data["frequency"] = self._parse_xb7_frequency(freq_text)

        if "Power Level" in data_map and index < len(data_map["Power Level"]):
            power_text = data_map["Power Level"][index]
            channel_data["power"] = extract_float(power_text)

        if "Modulation" in data_map and index < len(data_map["Modulation"]):
            channel_data["modulation"] = data_map["Modulation"][index]

    def _extract_upstream_fields(self, data_map: dict, index: int, channel_data: dict) -> None:
        """Extract upstream-specific fields."""
        if "Symbol Rate" in data_map and index < len(data_map["Symbol Rate"]):
            symbol_rate_text = data_map["Symbol Rate"][index]
            symbol_rate = extract_number(symbol_rate_text)
            if symbol_rate is not None:
                channel_data["symbol_rate"] = symbol_rate

        if "Channel Type" in data_map and index < len(data_map["Channel Type"]):
            channel_data["channel_type"] = data_map["Channel Type"][index]

    def _extract_downstream_fields(self, data_map: dict, index: int, channel_data: dict) -> None:
        """Extract downstream-specific fields."""
        if "SNR" in data_map and index < len(data_map["SNR"]):
            snr_text = data_map["SNR"][index]
            channel_data["snr"] = extract_float(snr_text)

        ***REMOVED*** Initialize error counters (will be filled from error table)
        channel_data["corrected"] = None
        channel_data["uncorrected"] = None

    def _extract_xb7_channel_data_at_index(self, data_map: dict, index: int, is_upstream: bool) -> dict | None:
        """Extract channel data from data_map at given column index.

        Returns:
            Channel data dict or None if channel_id is missing
        """
        channel_id = self._extract_channel_id(data_map, index)
        if channel_id is None:
            return None

        channel_data = {"channel_id": channel_id}
        self._extract_common_fields(data_map, index, channel_data)

        if is_upstream:
            self._extract_upstream_fields(data_map, index, channel_data)
        else:
            self._extract_downstream_fields(data_map, index, channel_data)

        return channel_data

    def _parse_xb7_transposed_table(self, rows: list, is_upstream: bool = False) -> list[dict]:
        """
        Parse XB7 transposed table where columns are channels.

        Each cell contains: <div class="netWidth">value</div>
        """
        channels = []

        try:
            ***REMOVED*** Build a map of row_label -> [values for each channel]
            data_map, channel_count = self._build_xb7_data_map(rows)

            _LOGGER.debug(f"XB7 transposed table has {channel_count} channels with labels: {list(data_map.keys())}")

            ***REMOVED*** Now transpose: create one channel dict per column
            for i in range(channel_count):
                channel_data = self._extract_xb7_channel_data_at_index(data_map, i, is_upstream)

                if channel_data is not None:
                    channels.append(channel_data)
                    _LOGGER.debug(f"Parsed XB7 channel {channel_data.get('channel_id')}: {channel_data}")

        except Exception as e:
            _LOGGER.error(f"Error parsing XB7 transposed table: {e}", exc_info=True)

        return channels

    def _find_error_codewords_table(self, soup: BeautifulSoup):
        """Find the CM Error Codewords table.

        Returns:
            Table element or None if not found
        """
        tables = soup.find_all("table", class_="data")

        for table in tables:
            thead = table.find("thead")
            if not thead:
                continue

            header_text = thead.get_text()
            if "CM Error Codewords" in header_text:
                _LOGGER.debug("Found XB7 error codewords table")
                return table

        return None

    def _build_error_data_map(self, rows: list) -> dict:
        """Build data map from error codewords table rows."""
        data_map = {}
        for row in rows:
            label_cell = row.find("th", class_="row-label")
            if not label_cell:
                continue

            ***REMOVED*** Get only direct text, not from nested divs
            label = "".join(label_cell.find_all(string=True, recursive=False)).strip()
            if not label:
                label = label_cell.get_text(strip=True)

            value_cells = row.find_all("td")
            values = []
            for cell in value_cells:
                div = cell.find("div", class_="netWidth")
                if div:
                    values.append(div.get_text(strip=True))
                else:
                    values.append(cell.get_text(strip=True))

            data_map[label] = values

        return data_map

    def _transpose_error_data(self, data_map: dict) -> list[dict]:
        """Transpose error data map into list of channel dicts."""
        error_channels: list[dict] = []

        if "Channel ID" not in data_map:
            return error_channels

        channel_count = len(data_map["Channel ID"])
        for i in range(channel_count):
            channel: dict[str, int | str | None] = {}

            if i < len(data_map["Channel ID"]):
                channel_id = extract_number(data_map["Channel ID"][i])
                if channel_id is None:
                    continue
                channel["channel_id"] = str(channel_id)

            if "Correctable Codewords" in data_map and i < len(data_map["Correctable Codewords"]):
                channel["corrected"] = extract_number(data_map["Correctable Codewords"][i])

            if "Uncorrectable Codewords" in data_map and i < len(data_map["Uncorrectable Codewords"]):
                channel["uncorrected"] = extract_number(data_map["Uncorrectable Codewords"][i])

            error_channels.append(channel)

        return error_channels

    def _parse_error_codewords(self, soup: BeautifulSoup) -> list[dict]:
        """
        Parse CM Error Codewords table.

        Returns list of dicts with channel_id, corrected, uncorrected.
        """
        try:
            table = self._find_error_codewords_table(soup)
            if not table:
                return []

            tbody = table.find("tbody")
            if not tbody:
                return []

            rows = tbody.find_all("tr", recursive=False)
            data_map = self._build_error_data_map(rows)
            return self._transpose_error_data(data_map)

        except Exception as e:
            _LOGGER.error(f"Error parsing XB7 error codewords: {e}", exc_info=True)
            return []

    def _merge_error_stats(self, downstream_channels: list[dict], error_channels: list[dict]) -> None:
        """Merge error statistics into downstream channels by matching channel_id."""
        try:
            ***REMOVED*** Create lookup dict by channel_id
            error_lookup = {ch["channel_id"]: ch for ch in error_channels if "channel_id" in ch}

            for channel in downstream_channels:
                channel_id = channel.get("channel_id")
                if channel_id and channel_id in error_lookup:
                    error_data = error_lookup[channel_id]
                    channel["corrected"] = error_data.get("corrected")
                    channel["uncorrected"] = error_data.get("uncorrected")
                    _LOGGER.debug(
                        f"Merged error stats for channel {channel_id}: "
                        f"corrected={channel['corrected']}, uncorrected={channel['uncorrected']}"
                    )

        except Exception as e:
            _LOGGER.error(f"Error merging XB7 error stats: {e}", exc_info=True)

    def _extract_label_value(self, label) -> str | None:
        """Extract value from label's next sibling span.

        Returns:
            Extracted value text or None if not found
        """
        value_span = label.find_next_sibling("span")
        if value_span and "readonlyLabel" not in value_span.get("class", []):
            return str(value_span.get_text(strip=True))
        return None

    def _process_system_uptime(self, value: str, system_info: dict) -> None:
        """Process system uptime value and calculate boot time."""
        system_info["system_uptime"] = value
        boot_time = self._calculate_boot_time(value)
        if boot_time:
            system_info["last_boot_time"] = boot_time

    def _map_system_info_field(self, label_text: str, value: str, system_info: dict) -> None:
        """Map label text to system info field and set value."""
        if "Serial Number" in label_text:
            system_info["serial_number"] = value
        elif "CM MAC" in label_text or "Hardware Address" in label_text:
            system_info["mac_address"] = value
        elif "Acquire Downstream" in label_text:
            system_info["downstream_status"] = value
        elif "Upstream Ranging" in label_text:
            system_info["upstream_status"] = value
        elif "System Uptime" in label_text:
            self._process_system_uptime(value, system_info)
        elif "Download Version" in label_text:
            system_info["software_version"] = value

    def _parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information from XB7."""
        system_info: dict[str, str] = {}

        try:
            ***REMOVED*** Look for readonlyLabel spans
            labels = soup.find_all("span", class_="readonlyLabel")

            for label in labels:
                label_text = label.get_text(strip=True).rstrip(":")
                value = self._extract_label_value(label)

                if value:
                    self._map_system_info_field(label_text, value, system_info)

        except Exception as e:
            _LOGGER.error(f"Error parsing XB7 system info: {e}", exc_info=True)

        return system_info

    def _parse_xb7_frequency(self, text: str) -> int | None:
        """
        Parse XB7 frequency which can be in two formats:
        1. "609 MHz" - text with unit
        2. "350000000" - raw Hz value

        Returns frequency in Hz.
        """
        text = text.strip()

        ***REMOVED*** Check if it's raw Hz (all digits)
        if text.replace(" ", "").isdigit():
            return int(text.replace(" ", ""))

        ***REMOVED*** Check if it contains "MHz"
        if "mhz" in text.lower():
            freq_mhz = extract_float(text)
            if freq_mhz is not None:
                return int(freq_mhz * 1_000_000)

        return None

    def _calculate_boot_time(self, uptime_str: str) -> str | None:
        """
        Calculate boot time from uptime string.
        Format: "21 days 15h: 20m: 33s"
        Returns ISO format datetime string.
        """
        import re
        from datetime import datetime, timedelta

        try:
            ***REMOVED*** Parse uptime string
            days = 0
            hours = 0
            minutes = 0
            seconds = 0

            day_match = re.search(r"(\d+)\s*days?", uptime_str)
            if day_match:
                days = int(day_match.group(1))

            hour_match = re.search(r"(\d+)h", uptime_str)
            if hour_match:
                hours = int(hour_match.group(1))

            min_match = re.search(r"(\d+)m", uptime_str)
            if min_match:
                minutes = int(min_match.group(1))

            sec_match = re.search(r"(\d+)s", uptime_str)
            if sec_match:
                seconds = int(sec_match.group(1))

            ***REMOVED*** Calculate boot time
            uptime_delta = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
            boot_time = datetime.now() - uptime_delta

            return boot_time.isoformat()

        except Exception as e:
            _LOGGER.error("Error calculating boot time from '%s': %s", uptime_str, e)
            return None

    def _parse_primary_channel(self, soup: BeautifulSoup) -> str | None:
        """
        Parse primary channel from note: "*Channel ID 10 is the Primary channel"
        Returns the primary channel ID as a string.
        """
        import re

        try:
            ***REMOVED*** Look for the note text
            for span in soup.find_all("span", class_="readonlyLabel"):
                text = span.get_text(strip=True)
                if "Primary channel" in text or "primary channel" in text:
                    ***REMOVED*** Extract channel ID: "*Channel ID 10 is the Primary channel"
                    match = re.search(r"Channel ID (\d+) is the Primary", text, re.IGNORECASE)
                    if match:
                        return match.group(1)
        except Exception as e:
            _LOGGER.error("Error parsing primary channel: %s", e)

        return None
