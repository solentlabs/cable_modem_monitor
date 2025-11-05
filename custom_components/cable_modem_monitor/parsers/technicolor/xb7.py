"""Parser for Technicolor XB7 cable modem."""
import logging
from bs4 import BeautifulSoup
from ..base_parser import ModemParser
from custom_components.cable_modem_monitor.lib.utils import extract_number, extract_float

_LOGGER = logging.getLogger(__name__)


class TechnicolorXB7Parser(ModemParser):
    """Parser for Technicolor XB7 cable modem (Rogers, Comcast)."""

    name = "Technicolor XB7"
    manufacturer = "Technicolor"
    models = ["XB7", "CGM4331COM"]

    url_patterns = [
        {"path": "/network_setup.jst", "auth_method": "form"},
    ]

    def login(self, session, base_url, username, password) -> tuple[bool, str]:
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
            # Step 1: POST credentials to check.jst
            login_url = f"{base_url}/check.jst"
            login_data = {
                "username": username,
                "password": password,
            }

            _LOGGER.debug(f"XB7: Posting credentials to {login_url}")
            response = session.post(login_url, data=login_data, timeout=10, allow_redirects=True)

            if response.status_code != 200:
                _LOGGER.error(f"XB7 login failed with status {response.status_code}")
                return False, None

            # Step 2: Check if we got redirected to at_a_glance.jst (successful login)
            if "at_a_glance.jst" in response.url:
                _LOGGER.debug("XB7: Login successful, redirected to at_a_glance.jst")
            else:
                _LOGGER.warning(f"XB7: Unexpected redirect to {response.url}")

            # Step 3: Now fetch the network_setup.jst page with authenticated session
            status_url = f"{base_url}/network_setup.jst"
            _LOGGER.debug(f"XB7: Fetching {status_url} with authenticated session")
            status_response = session.get(status_url, timeout=10)

            if status_response.status_code != 200:
                _LOGGER.error(f"XB7: Failed to fetch status page, status {status_response.status_code}")
                return False, None

            _LOGGER.info(f"XB7: Successfully authenticated and fetched status page ({len(status_response.text)} bytes)")
            return True, status_response.text

        except Exception as e:
            _LOGGER.error(f"XB7 login exception: {e}", exc_info=True)
            return False, None

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """
        Detect if this is a Technicolor XB7 modem.

        Detection criteria:
        1. URL contains "network_setup.jst"
        2. HTML contains "Channel Bonding Value" with netWidth divs (XB7-specific)
        """
        # Primary detection: URL pattern
        if "network_setup.jst" in url.lower():
            _LOGGER.debug("XB7 detected by URL pattern: network_setup.jst")
            return True

        # Secondary detection: Content-based
        if "Channel Bonding Value" in html:
            # Look for XB7-specific class pattern
            if soup.find_all('div', class_='netWidth'):
                _LOGGER.debug("XB7 detected by content: Channel Bonding Value + netWidth divs")
                return True

        return False

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the XB7 modem."""
        downstream_channels = self._parse_downstream(soup)
        upstream_channels = self._parse_upstream(soup)
        system_info = self._parse_system_info(soup)

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
            _LOGGER.debug(f"Found {len(tables)} tables in XB7 HTML")

            for table in tables:
                # Find thead with "Downstream" text
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

                # Look for error codewords table
                error_channels = self._parse_error_codewords(soup)
                if error_channels:
                    self._merge_error_stats(downstream_channels, error_channels)

                break

            _LOGGER.debug(f"XB7 parsing found {len(downstream_channels)} downstream channels")

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
                # Find thead with "Upstream" text
                thead = table.find("thead")
                if not thead:
                    continue

                header_text = thead.get_text()
                if "Upstream" not in header_text or "Channel Bonding Value" not in header_text:
                    continue

                # Make sure it's not downstream table
                if "Downstream" in header_text:
                    continue

                _LOGGER.debug("Found XB7 upstream table")
                tbody = table.find("tbody")
                if not tbody:
                    continue

                rows = tbody.find_all("tr", recursive=False)
                upstream_channels = self._parse_xb7_transposed_table(rows, is_upstream=True)
                break

            _LOGGER.debug(f"XB7 parsing found {len(upstream_channels)} upstream channels")

        except Exception as e:
            _LOGGER.error(f"Error parsing XB7 upstream: {e}", exc_info=True)

        return upstream_channels

    def _parse_xb7_transposed_table(
        self, rows: list, is_upstream: bool = False
    ) -> list[dict]:
        """
        Parse XB7 transposed table where columns are channels.

        Each cell contains: <div class="netWidth">value</div>
        """
        channels = []

        try:
            # Build a map of row_label -> [values for each channel]
            data_map = {}
            channel_count = 0

            for row in rows:
                # First cell is the row label (th)
                label_cell = row.find("th", class_="row-label")
                if not label_cell:
                    continue

                # Get only direct text, not from nested divs
                label = "".join(label_cell.find_all(string=True, recursive=False)).strip()
                if not label:
                    # Fallback if no direct text
                    label = label_cell.get_text(strip=True)

                # Extract all netWidth div values from this row
                value_cells = row.find_all("td")
                values = []
                for cell in value_cells:
                    div = cell.find("div", class_="netWidth")
                    if div:
                        values.append(div.get_text(strip=True))
                    else:
                        values.append(cell.get_text(strip=True))

                # Update channel count from longest row
                if len(values) > channel_count:
                    channel_count = len(values)

                data_map[label] = values
                _LOGGER.debug(f"XB7 row '{label}': {len(values)} values")

            _LOGGER.debug(
                f"XB7 transposed table has {channel_count} channels with labels: {list(data_map.keys())}"
            )

            # Now transpose: create one channel dict per column
            for i in range(channel_count):
                channel_data = {}

                # Extract channel ID
                if "Channel ID" in data_map and i < len(data_map["Channel ID"]):
                    channel_id = extract_number(data_map["Channel ID"][i])
                    if channel_id is None:
                        continue
                    channel_data["channel_id"] = str(channel_id)

                # Extract lock status
                if "Lock Status" in data_map and i < len(data_map["Lock Status"]):
                    channel_data["lock_status"] = data_map["Lock Status"][i]

                # Extract frequency (handles both "609 MHz" and "350000000" formats)
                if "Frequency" in data_map and i < len(data_map["Frequency"]):
                    freq_text = data_map["Frequency"][i]
                    freq_hz = self._parse_xb7_frequency(freq_text)
                    channel_data["frequency"] = freq_hz

                # Extract power level
                if "Power Level" in data_map and i < len(data_map["Power Level"]):
                    power_text = data_map["Power Level"][i]
                    channel_data["power"] = extract_float(power_text)

                # Extract modulation
                if "Modulation" in data_map and i < len(data_map["Modulation"]):
                    channel_data["modulation"] = data_map["Modulation"][i]

                if is_upstream:
                    # Upstream-specific fields

                    # Symbol Rate (XB7-specific)
                    if "Symbol Rate" in data_map and i < len(data_map["Symbol Rate"]):
                        symbol_rate_text = data_map["Symbol Rate"][i]
                        symbol_rate = extract_number(symbol_rate_text)
                        if symbol_rate is not None:
                            channel_data["symbol_rate"] = symbol_rate

                    # Channel Type (XB7-specific)
                    if "Channel Type" in data_map and i < len(data_map["Channel Type"]):
                        channel_data["channel_type"] = data_map["Channel Type"][i]

                else:
                    # Downstream-specific fields
                    if "SNR" in data_map and i < len(data_map["SNR"]):
                        snr_text = data_map["SNR"][i]
                        channel_data["snr"] = extract_float(snr_text)

                    # Initialize error counters (will be filled from error table)
                    channel_data["corrected"] = None
                    channel_data["uncorrected"] = None

                # Skip if missing required data
                if channel_data.get("channel_id") is not None:
                    channels.append(channel_data)
                    _LOGGER.debug(
                        f"Parsed XB7 channel {channel_data.get('channel_id')}: {channel_data}"
                    )

        except Exception as e:
            _LOGGER.error(f"Error parsing XB7 transposed table: {e}", exc_info=True)

        return channels

    def _parse_error_codewords(self, soup: BeautifulSoup) -> list[dict]:
        """
        Parse CM Error Codewords table.

        Returns list of dicts with channel_id, corrected, uncorrected.
        """
        error_channels = []

        try:
            tables = soup.find_all("table", class_="data")

            for table in tables:
                # Look for "CM Error Codewords" header
                thead = table.find("thead")
                if not thead:
                    continue

                header_text = thead.get_text()
                if "CM Error Codewords" not in header_text:
                    continue

                _LOGGER.debug("Found XB7 error codewords table")
                tbody = table.find("tbody")
                if not tbody:
                    continue

                rows = tbody.find_all("tr", recursive=False)

                # Build data map
                data_map = {}
                for row in rows:
                    label_cell = row.find("th", class_="row-label")
                    if not label_cell:
                        continue

                    # Get only direct text, not from nested divs
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

                # Transpose to channel dicts
                if "Channel ID" in data_map:
                    channel_count = len(data_map["Channel ID"])
                    for i in range(channel_count):
                        channel = {}

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

                break

        except Exception as e:
            _LOGGER.error(f"Error parsing XB7 error codewords: {e}", exc_info=True)

        return error_channels

    def _merge_error_stats(self, downstream_channels: list[dict], error_channels: list[dict]) -> None:
        """Merge error statistics into downstream channels by matching channel_id."""
        try:
            # Create lookup dict by channel_id
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

    def _parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information from XB7."""
        system_info = {}

        try:
            # Look for readonlyLabel spans
            labels = soup.find_all("span", class_="readonlyLabel")

            for label in labels:
                label_text = label.get_text(strip=True).rstrip(":")

                # Find the value (usually in next sibling or nearby span)
                value_span = label.find_next_sibling("span")
                if value_span and "readonlyLabel" not in value_span.get("class", []):
                    value = value_span.get_text(strip=True)

                    # Map common fields
                    if "Serial Number" in label_text:
                        system_info["serial_number"] = value
                    elif "CM MAC" in label_text or "Hardware Address" in label_text:
                        system_info["mac_address"] = value
                    elif "Acquire Downstream" in label_text:
                        system_info["downstream_status"] = value
                    elif "Upstream Ranging" in label_text:
                        system_info["upstream_status"] = value

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

        # Check if it's raw Hz (all digits)
        if text.replace(" ", "").isdigit():
            return int(text.replace(" ", ""))

        # Check if it contains "MHz"
        if "mhz" in text.lower():
            freq_mhz = extract_float(text)
            if freq_mhz is not None:
                return int(freq_mhz * 1_000_000)

        return None