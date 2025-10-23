"""Web scraper for cable modem data."""
import logging
import requests
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


class ModemScraper:
    """Scrape data from cable modem web interface."""

    def __init__(self, host: str, username: str = None, password: str = None):
        """Initialize the modem scraper."""
        self.host = host
        self.base_url = f"http://{host}"
        self.username = username
        self.password = password
        self.session = requests.Session()

    def _login(self) -> bool:
        """Log in to the modem web interface."""
        if not self.username or not self.password:
            _LOGGER.debug("No credentials provided, skipping login")
            return True

        try:
            login_url = f"{self.base_url}/goform/login"
            login_data = {
                "loginUsername": self.username,
                "loginPassword": self.password,
            }
            _LOGGER.info(f"Attempting login to {login_url} as user '{self.username}'")

            # Don't follow redirects automatically so we can check the response
            response = self.session.post(login_url, data=login_data, timeout=10, allow_redirects=True)

            _LOGGER.info(f"Login response: status={response.status_code}, url={response.url}")

            # Motorola modems have unusual behavior - they redirect to login.asp
            # even on successful login, but the session cookie is set correctly.
            # Test if we can access a protected page to verify login success.
            test_response = self.session.get(f"{self.base_url}/MotoConnection.asp", timeout=10)
            _LOGGER.info(f"Login verification: test page status={test_response.status_code}")

            if test_response.status_code == 200 and len(test_response.text) > 1000:
                _LOGGER.info("Login successful - verified by accessing protected page")
                return True
            else:
                _LOGGER.error(
                    f"Login failed - could not access protected page "
                    f"(status={test_response.status_code}, length={len(test_response.text)})"
                )
                return False

        except requests.RequestException as e:
            _LOGGER.error(f"Login failed: {type(e).__name__}: {e}")
            return False

    def get_modem_data(self) -> dict:
        """Fetch and parse modem data."""
        try:
            # Login first if credentials are provided
            if not self._login():
                _LOGGER.error("Failed to log in to modem")
                return {"connection_status": "unreachable", "downstream": [], "upstream": []}

            # Try common modem signal data URLs
            # Based on research: Motorola MB series, Technicolor TC4400, Arris
            # See ATTRIBUTION.md for research sources
            urls_to_try = [
                f"{self.base_url}/MotoConnection.asp",      # Motorola MB series
                f"{self.base_url}/cmconnectionstatus.html", # Technicolor TC4400
                f"{self.base_url}/cmSignalData.htm",        # Generic/Arris
                f"{self.base_url}/cmSignal.html",           # Generic/Arris
                f"{self.base_url}/",                        # Root fallback
            ]

            html = None
            successful_url = None
            for url in urls_to_try:
                try:
                    _LOGGER.debug(f"Attempting to fetch {url}")
                    response = self.session.get(url, timeout=10)
                    if response.status_code == 200:
                        html = response.text
                        successful_url = url
                        _LOGGER.info(f"Successfully connected to modem at {url} (HTML length: {len(html)} bytes)")
                        break
                    else:
                        _LOGGER.debug(f"Got status {response.status_code} from {url}")
                except requests.RequestException as e:
                    _LOGGER.debug(f"Failed to fetch from {url}: {type(e).__name__}: {e}")
                    continue

            if not html:
                _LOGGER.error("Could not fetch data from any known modem URL")
                return {"connection_status": "unreachable", "downstream": [], "upstream": []}

            soup = BeautifulSoup(html, "html.parser")

            # Log HTML structure for debugging
            tables = soup.find_all("table")
            _LOGGER.debug(f"Found {len(tables)} tables in HTML from {successful_url}")
            if tables:
                for i, table in enumerate(tables[:3]):  # Log first 3 tables only
                    headers = table.find_all("td", class_="moto-param-header-s")
                    if headers:
                        header_text = [h.text.strip() for h in headers[:5]]  # First 5 headers
                        _LOGGER.debug(f"Table {i+1} headers (Motorola style): {header_text}")

            # Try Motorola-style parsing first
            downstream_channels = self._parse_downstream_channels(soup)
            upstream_channels = self._parse_upstream_channels(soup)

            # If Motorola parsing failed, try ARRIS SB6141 format
            if not downstream_channels and not upstream_channels:
                _LOGGER.debug("Motorola parsing found no channels, trying ARRIS SB6141 format")
                downstream_channels, upstream_channels = self._parse_arris_sb6141(soup)

            # Validate that we got some valid data
            if not downstream_channels and not upstream_channels:
                _LOGGER.error(
                    f"No valid channel data parsed from modem. Connection to {successful_url} succeeded "
                    f"but HTML format not recognized (found {len(soup.find_all('table'))} tables). "
                    "Your modem model may not be supported yet. To add support, please: "
                    "1) Open this URL in your browser: %s "
                    "2) Right-click -> View Page Source "
                    "3) Save and share the HTML at https://github.com/kwschulz/cable_modem_monitor/issues",
                    successful_url
                )
                raise ValueError("No valid channel data available")

            # Calculate totals (only include non-None values)
            total_corrected = sum(
                ch.get("corrected") or 0 for ch in downstream_channels if ch.get("corrected") is not None
            )
            total_uncorrected = sum(
                ch.get("uncorrected") or 0 for ch in downstream_channels if ch.get("uncorrected") is not None
            )

            # Fetch additional data from MotoHome.asp (version, channel counts)
            software_version = "Unknown"
            system_uptime = "Unknown"
            upstream_channel_count = len(upstream_channels)  # Default to parsed count
            downstream_channel_count = len(downstream_channels)  # Default to parsed count

            # Get uptime from main connection page (soup already has MotoConnection.asp)
            system_uptime = self._parse_system_uptime(soup)

            try:
                _LOGGER.info("Fetching additional data from MotoHome.asp")
                home_response = self.session.get(f"{self.base_url}/MotoHome.asp", timeout=10)
                if home_response.status_code == 200:
                    home_soup = BeautifulSoup(home_response.text, "html.parser")
                    software_version = self._parse_software_version(home_soup)
                    # Parse channel counts from MotoHome page
                    reported_counts = self._parse_channel_counts(home_soup)
                    if reported_counts.get("downstream") is not None:
                        downstream_channel_count = reported_counts["downstream"]
                    if reported_counts.get("upstream") is not None:
                        upstream_channel_count = reported_counts["upstream"]
            except Exception as e:
                _LOGGER.warning(f"Could not fetch MotoHome.asp data: {e}")

            return {
                "connection_status": "online" if downstream_channels else "offline",
                "downstream": downstream_channels,
                "upstream": upstream_channels,
                "total_corrected": total_corrected,
                "total_uncorrected": total_uncorrected,
                "downstream_channel_count": downstream_channel_count,
                "upstream_channel_count": upstream_channel_count,
                "software_version": software_version,
                "system_uptime": system_uptime,
            }

        except Exception as e:
            _LOGGER.error(f"Error fetching modem data: {e}")
            return {"connection_status": "unreachable", "downstream": [], "upstream": []}

    def _parse_downstream_channels(self, soup: BeautifulSoup) -> list:
        """Parse downstream channel data from HTML."""
        channels = []

        try:
            # Motorola MB series modems use specific table structure
            # Look for table with "Downstream Bonded Channels" title
            tables = soup.find_all("table")
            _LOGGER.debug(f"Found {len(tables)} tables to parse")

            for table in tables:
                # Check if this table contains downstream channel data
                # Look for headers: Channel, Lock Status, Modulation, etc.
                # Use direct children only (recursive=False) to avoid nested table issues
                all_rows = table.find_all("tr", recursive=False)

                # If no direct children, try one level deeper (for tables wrapped in tbody)
                if not all_rows:
                    tbody = table.find("tbody")
                    if tbody:
                        all_rows = tbody.find_all("tr", recursive=False)

                if not all_rows:
                    continue

                # Find the header row by looking for moto-param-header-s class
                header_row = None
                headers = []
                for row in all_rows:
                    potential_headers = [td.text.strip() for td in row.find_all("td", class_="moto-param-header-s")]
                    if potential_headers and "Channel" in potential_headers:
                        header_row = row
                        headers = potential_headers
                        break

                # If we found the header row with channel data headers
                if header_row and headers:
                    _LOGGER.debug(f"Found downstream channel table with headers: {headers}")
                    # Get all rows after the header row
                    header_index = all_rows.index(header_row)
                    data_rows = all_rows[header_index + 1:]  # Skip header row

                    for row in data_rows:
                        cols = row.find_all("td")
                        if len(cols) >= 9:  # Channel, Lock, Modulation, ID, Freq, Pwr, SNR, Corrected, Uncorrected
                            try:
                                # Skip the "Total" row at the bottom of the table
                                channel_text = cols[0].text.strip()
                                if channel_text.lower() == "total":
                                    _LOGGER.debug("Skipping Total row to avoid double-counting errors")
                                    continue

                                freq_mhz = self._extract_float(cols[4].text)  # Freq column in MHz
                                # Convert MHz to Hz
                                freq_hz = freq_mhz * 1_000_000 if freq_mhz is not None else None
                                channel_data = {
                                    "channel": self._extract_number(cols[0].text),
                                    "frequency": freq_hz,
                                    "power": self._extract_float(cols[5].text),      # Pwr column
                                    "snr": self._extract_float(cols[6].text),        # SNR column
                                    "corrected": self._extract_number(cols[7].text),
                                    "uncorrected": self._extract_number(cols[8].text),
                                }

                                # Skip channel if all critical values are None (invalid data)
                                if all(v is None for k, v in channel_data.items() if k != "channel"):
                                    _LOGGER.warning(f"Skipping downstream channel with all null values: {cols[0].text}")
                                    continue

                                # Skip if channel number itself is None
                                if channel_data["channel"] is None:
                                    _LOGGER.warning("Skipping downstream channel with invalid channel number")
                                    continue

                                channels.append(channel_data)
                                _LOGGER.debug(f"Parsed downstream channel {channel_data['channel']}: {channel_data}")
                            except Exception as e:
                                _LOGGER.error(f"Error parsing downstream channel row: {e}")
                                continue

            _LOGGER.debug(f"Total downstream channels parsed: {len(channels)}")

        except Exception as e:
            _LOGGER.error(f"Error parsing downstream channels: {e}")

        return channels

    def _parse_upstream_channels(self, soup: BeautifulSoup) -> list:
        """Parse upstream channel data from HTML."""
        channels = []

        try:
            # Look for upstream channel table (similar structure to downstream)
            tables = soup.find_all("table")

            for table in tables:
                # Use direct children only (recursive=False) to avoid nested table issues
                all_rows = table.find_all("tr", recursive=False)

                # If no direct children, try one level deeper (for tables wrapped in tbody)
                if not all_rows:
                    tbody = table.find("tbody")
                    if tbody:
                        all_rows = tbody.find_all("tr", recursive=False)

                if not all_rows:
                    continue

                # Find the header row by looking for moto-param-header-s class
                header_row = None
                headers = []
                for row in all_rows:
                    potential_headers = [td.text.strip() for td in row.find_all("td", class_="moto-param-header-s")]
                    if potential_headers:
                        # Look for upstream-specific headers (must have symb rate, not SNR which is downstream)
                        headers_text = " ".join(potential_headers).lower()
                        is_upstream = ("symb" in headers_text or "symbol rate" in headers_text) and "snr" not in headers_text
                        if is_upstream:
                            header_row = row
                            headers = potential_headers
                            break

                if header_row and headers:
                    _LOGGER.debug(f"Found upstream channel table with headers: {headers}")
                    # Get all rows after the header row
                    header_index = all_rows.index(header_row)
                    data_rows = all_rows[header_index + 1:]  # Skip header row

                    for row in data_rows:
                        cols = row.find_all("td")
                        if len(cols) >= 7:  # Typical upstream: Channel, Lock, Type, ID, Symb Rate, Freq, Power
                            try:
                                # Skip "Not Locked" channels
                                lock_status = cols[1].text.strip() if len(cols) > 1 else ""
                                if "not locked" in lock_status.lower():
                                    _LOGGER.debug(f"Skipping not locked upstream channel: {cols[0].text}")
                                    continue

                                freq_mhz = self._extract_float(cols[5].text)  # Freq column in MHz
                                # Convert MHz to Hz
                                freq_hz = freq_mhz * 1_000_000 if freq_mhz is not None else None
                                channel_data = {
                                    "channel": self._extract_number(cols[0].text),
                                    "frequency": freq_hz,
                                    "power": self._extract_float(cols[6].text),      # Power column
                                }

                                # Skip channel if all critical values are None or zero (invalid data)
                                if all(v is None or v == 0 for k, v in channel_data.items() if k != "channel"):
                                    _LOGGER.warning(
                                        f"Skipping upstream channel with all null/zero values: {cols[0].text}"
                                    )
                                    continue

                                # Skip if channel number itself is None
                                if channel_data["channel"] is None:
                                    _LOGGER.warning("Skipping upstream channel with invalid channel number")
                                    continue

                                # Skip if frequency is 0 (unlocked channel)
                                if channel_data["frequency"] == 0 or channel_data["frequency"] is None:
                                    _LOGGER.debug(
                                        f"Skipping upstream channel {channel_data['channel']} with zero frequency"
                                    )
                                    continue

                                channels.append(channel_data)
                                _LOGGER.debug(f"Parsed upstream channel {channel_data['channel']}: {channel_data}")
                            except Exception as e:
                                _LOGGER.error(f"Error parsing upstream channel row: {e}")
                                continue

            _LOGGER.debug(f"Total upstream channels parsed: {len(channels)}")

        except Exception as e:
            _LOGGER.error(f"Error parsing upstream channels: {e}")

        return channels

    def _extract_number(self, text: str) -> int | None:
        """Extract integer from text."""
        try:
            # Remove common units and extract number
            cleaned = "".join(c for c in text if c.isdigit() or c == "-")
            return int(cleaned) if cleaned else None
        except ValueError:
            return None

    def _extract_float(self, text: str) -> float | None:
        """Extract float from text."""
        try:
            # Remove units (dB, dBmV, MHz, etc.) and extract number
            cleaned = "".join(c for c in text if c.isdigit() or c in ".-")
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    def _parse_software_version(self, soup: BeautifulSoup) -> str:
        """Parse software version from modem page."""
        try:
            # Look for "Software Version" label in cells with class="moto-param-name"
            # The value will be in the next cell with class="moto-param-value"
            rows = soup.find_all("tr")

            for row in rows:
                # Find cells with the specific class for parameter names
                name_cell = row.find("td", class_="moto-param-name")
                if name_cell and "Software Version" in name_cell.text:
                    # Get the corresponding value cell
                    value_cell = row.find("td", class_="moto-param-value")
                    if value_cell:
                        version = value_cell.text.strip()
                        if version and version != "N/A":
                            _LOGGER.debug(f"Found software version: {version}")
                            return version

            _LOGGER.debug("Software version not found")
            return "Unknown"

        except Exception as e:
            _LOGGER.error(f"Error parsing software version: {e}")
            return "Unknown"

    def _parse_system_uptime(self, soup: BeautifulSoup) -> str:
        """Parse system uptime from MotoConnection.asp page."""
        try:
            # Look for "System Up Time" label, value is in cell with class='moto-content-value'
            rows = soup.find_all("tr")

            for row in rows:
                cells = row.find_all("td")
                # Look for a cell containing "System Up Time" text
                for i, cell in enumerate(cells):
                    if "System Up Time" in cell.text:
                        # The value should be in the next cell with class moto-content-value
                        value_cell = row.find("td", class_="moto-content-value")
                        if value_cell:
                            uptime = value_cell.text.strip()
                            if uptime and uptime != "N/A":
                                _LOGGER.debug(f"Found system uptime: {uptime}")
                                return uptime

            _LOGGER.debug("System uptime not found")
            return "Unknown"

        except Exception as e:
            _LOGGER.error(f"Error parsing system uptime: {e}")
            return "Unknown"

    def _parse_channel_counts(self, soup: BeautifulSoup) -> dict:
        """Parse channel counts from MotoHome.asp page."""
        result = {"downstream": None, "upstream": None}

        try:
            # Look for channel count rows on MotoHome.asp
            # Structure: <td class="moto-param-name">Downstream</td> followed by <td class="moto-param-value">24</td>
            rows = soup.find_all("tr")

            for row in rows:
                cells = row.find_all("td", class_="moto-param-name")
                if cells:
                    label = cells[0].text.strip().lower()
                    # Look for "Downstream" or "Upstream" labels (indented with nbsp)
                    if "downstream" in label:
                        # Get the value from the next cell
                        value_cells = row.find_all("td", class_="moto-param-value")
                        if value_cells and value_cells[0].text.strip():
                            try:
                                result["downstream"] = int(value_cells[0].text.strip())
                                _LOGGER.debug(f"Found downstream channel count: {result['downstream']}")
                            except ValueError:
                                pass
                    elif "upstream" in label:
                        value_cells = row.find_all("td", class_="moto-param-value")
                        if value_cells and value_cells[0].text.strip():
                            try:
                                result["upstream"] = int(value_cells[0].text.strip())
                                _LOGGER.debug(f"Found upstream channel count: {result['upstream']}")
                            except ValueError:
                                pass

        except Exception as e:
            _LOGGER.error(f"Error parsing channel counts: {e}")

        return result

    def _parse_arris_sb6141(self, soup: BeautifulSoup) -> tuple[list, list]:
        """Parse ARRIS SB6141 format (transposed tables where columns are channels)."""
        downstream_channels = []
        upstream_channels = []

        try:
            tables = soup.find_all("table")
            _LOGGER.debug(f"Parsing ARRIS SB6141 format from {len(tables)} tables")

            # Find tables by looking for "Channel ID" row
            for table in tables:
                rows = table.find_all("tr")
                if not rows:
                    continue

                # Check if this table has channel data (look for "Channel ID" row)
                row_labels = []
                for row in rows:
                    cells = row.find_all("td")
                    if cells and len(cells) > 0:
                        label = cells[0].text.strip()
                        row_labels.append(label)

                # Detect table type by its labels
                has_channel_id = "Channel ID" in row_labels
                has_power_level = any("Power Level" in label for label in row_labels)
                has_snr = "Signal to Noise Ratio" in row_labels
                has_downstream_mod = "Downstream Modulation" in row_labels
                has_symbol_rate = "Symbol Rate" in row_labels
                has_upstream_mod = "Upstream Modulation" in row_labels

                if has_channel_id and has_power_level:
                    # Check if it's downstream or upstream
                    if has_snr or has_downstream_mod:
                        # Downstream table
                        _LOGGER.debug("Found ARRIS downstream table")
                        downstream_channels = self._parse_arris_transposed_table(
                            rows, ["Channel ID", "Frequency", "Signal to Noise Ratio", "Power Level"]
                        )
                    elif has_symbol_rate or has_upstream_mod:
                        # Upstream table
                        _LOGGER.debug("Found ARRIS upstream table")
                        upstream_channels = self._parse_arris_transposed_table(
                            rows, ["Channel ID", "Frequency", "Power Level"], is_upstream=True
                        )
                elif "Total Correctable Codewords" in row_labels:
                    # Signal stats table - merge with downstream channels
                    _LOGGER.debug("Found ARRIS signal stats table")
                    self._merge_arris_error_stats(downstream_channels, rows)

            _LOGGER.debug(
                f"ARRIS parsing found {len(downstream_channels)} downstream, "
                f"{len(upstream_channels)} upstream"
            )

        except Exception as e:
            _LOGGER.error(f"Error parsing ARRIS SB6141 format: {e}")

        return downstream_channels, upstream_channels

    def _parse_arris_transposed_table(
        self, rows: list, required_fields: list, is_upstream: bool = False
    ) -> list:
        """Parse ARRIS transposed table where columns are channels."""
        channels = []

        try:
            # Build a map of row_label -> [values for each channel]
            data_map = {}
            channel_count = 0

            for row in rows:
                cells = row.find_all("td")
                if not cells or len(cells) < 2:
                    continue

                label = cells[0].text.strip()
                values = [cell.text.strip() for cell in cells[1:]]  # Skip first cell (label)

                # Normalize label and handle nested tables in Power Level row
                if "Power Level" in label:
                    label = "Power Level"
                    # ARRIS SB6141 has nested table in Power Level row - skip first value
                    # which contains the nested table text
                    if values and "Downstream Power Level reading" in values[0]:
                        values = values[1:]  # Skip nested table text

                # Update channel count from longest row
                if len(values) > channel_count:
                    channel_count = len(values)

                data_map[label] = values

            _LOGGER.debug(f"Transposed table has {channel_count} channels with labels: {list(data_map.keys())}")

            # Now transpose: create one channel dict per column
            for i in range(channel_count):
                channel_data = {}

                # Extract channel ID
                if "Channel ID" in data_map and i < len(data_map["Channel ID"]):
                    channel_id = self._extract_number(data_map["Channel ID"][i])
                    if channel_id is None:
                        continue
                    channel_data["channel"] = channel_id

                # Extract frequency (already in Hz for ARRIS)
                if "Frequency" in data_map and i < len(data_map["Frequency"]):
                    freq_text = data_map["Frequency"][i]
                    # ARRIS format: "519000000 Hz" - extract number
                    freq_hz = self._extract_number(freq_text)
                    channel_data["frequency"] = freq_hz

                # Extract power level
                if "Power Level" in data_map and i < len(data_map["Power Level"]):
                    power_text = data_map["Power Level"][i]
                    channel_data["power"] = self._extract_float(power_text)

                if not is_upstream:
                    # Downstream-specific fields
                    if "Signal to Noise Ratio" in data_map and i < len(data_map["Signal to Noise Ratio"]):
                        snr_text = data_map["Signal to Noise Ratio"][i]
                        channel_data["snr"] = self._extract_float(snr_text)

                    # Initialize error counters (will be filled from stats table)
                    channel_data["corrected"] = None
                    channel_data["uncorrected"] = None

                # Skip if missing required data
                if channel_data.get("channel") is not None:
                    channels.append(channel_data)
                    _LOGGER.debug(f"Parsed ARRIS channel {channel_data.get('channel')}: {channel_data}")

        except Exception as e:
            _LOGGER.error(f"Error parsing ARRIS transposed table: {e}")

        return channels

    def _merge_arris_error_stats(self, downstream_channels: list, stats_rows: list) -> None:
        """Merge error statistics from signal stats table into downstream channels."""
        try:
            # Parse stats table (also transposed)
            data_map = {}
            for row in stats_rows:
                cells = row.find_all("td")
                if not cells or len(cells) < 2:
                    continue

                label = cells[0].text.strip()
                values = [cell.text.strip() for cell in cells[1:]]
                data_map[label] = values

            # Match channels by index
            for i, channel in enumerate(downstream_channels):
                if "Total Correctable Codewords" in data_map and i < len(data_map["Total Correctable Codewords"]):
                    channel["corrected"] = self._extract_number(data_map["Total Correctable Codewords"][i])

                if "Total Uncorrectable Codewords" in data_map and i < len(data_map["Total Uncorrectable Codewords"]):
                    channel["uncorrected"] = self._extract_number(data_map["Total Uncorrectable Codewords"][i])

        except Exception as e:
            _LOGGER.error(f"Error merging ARRIS error stats: {e}")

    def restart_modem(self) -> bool:
        """Restart the cable modem."""
        try:
            # Login first if credentials are provided
            if not self._login():
                _LOGGER.error("Failed to log in to modem for restart")
                return False

            # Common Motorola modem restart endpoints
            restart_urls = [
                f"{self.base_url}/goform/Reboot",
                f"{self.base_url}/goform/restart",
                f"{self.base_url}/restart.cgi",
            ]

            for url in restart_urls:
                try:
                    _LOGGER.info(f"Attempting to restart modem via {url}")
                    response = self.session.post(url, timeout=10)

                    if response.status_code in [200, 302]:
                        _LOGGER.info(f"Modem restart initiated successfully via {url}")
                        return True
                    else:
                        _LOGGER.warning(f"Restart attempt returned status {response.status_code} from {url}")

                except requests.RequestException as e:
                    _LOGGER.debug(f"Failed restart attempt via {url}: {e}")
                    continue

            _LOGGER.error("All modem restart attempts failed")
            return False

        except Exception as e:
            _LOGGER.error(f"Error restarting modem: {e}")
            return False
