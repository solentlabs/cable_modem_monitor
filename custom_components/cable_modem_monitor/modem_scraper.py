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
                _LOGGER.error(f"Login failed - could not access protected page (status={test_response.status_code}, length={len(test_response.text)})")
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
                return {"connection_status": "offline", "downstream": [], "upstream": []}

            # Try common Motorola modem signal data URLs
            # MotoConnection.asp is the primary page for Motorola modems (MB series)
            urls_to_try = [
                f"{self.base_url}/MotoConnection.asp",
                f"{self.base_url}/cmSignalData.htm",
                f"{self.base_url}/cmSignal.html",
                f"{self.base_url}/",
            ]

            html = None
            for url in urls_to_try:
                try:
                    _LOGGER.info(f"Attempting to fetch {url}")
                    response = self.session.get(url, timeout=10)
                    _LOGGER.info(f"Response from {url}: status={response.status_code}")
                    if response.status_code == 200:
                        html = response.text
                        _LOGGER.info(f"Successfully fetched data from {url}")
                        break
                    else:
                        _LOGGER.warning(f"Got status {response.status_code} from {url}")
                except requests.RequestException as e:
                    _LOGGER.error(f"Failed to fetch from {url}: {type(e).__name__}: {e}")
                    continue

            if not html:
                _LOGGER.error("Could not fetch data from any known modem URL")
                return {"connection_status": "offline", "downstream": [], "upstream": []}

            soup = BeautifulSoup(html, "html.parser")

            # Parse downstream channels
            downstream_channels = self._parse_downstream_channels(soup)

            # Parse upstream channels
            upstream_channels = self._parse_upstream_channels(soup)

            # Validate that we got some valid data
            if not downstream_channels and not upstream_channels:
                _LOGGER.error("No valid channel data parsed from modem - skipping update")
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
            return {"connection_status": "offline", "downstream": [], "upstream": []}

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
                header_row = table.find("tr")
                if not header_row:
                    continue

                headers = [td.text.strip() for td in header_row.find_all("td", class_="moto-param-header-s")]

                # If we found the header row with channel data headers
                if headers and "Channel" in headers:
                    _LOGGER.debug(f"Found downstream channel table with headers: {headers}")
                    rows = table.find_all("tr")[1:]  # Skip header row

                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 9:  # Channel, Lock, Modulation, ID, Freq, Pwr, SNR, Corrected, Uncorrected
                            try:
                                # Skip the "Total" row at the bottom of the table
                                channel_text = cols[0].text.strip()
                                if channel_text.lower() == "total":
                                    _LOGGER.debug("Skipping Total row to avoid double-counting errors")
                                    continue

                                channel_data = {
                                    "channel": self._extract_number(cols[0].text),
                                    "frequency": self._extract_float(cols[4].text),  # Freq column
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
                header_row = table.find("tr")
                if not header_row:
                    continue

                headers = [td.text.strip() for td in header_row.find_all("td", class_="moto-param-header-s")]

                # Look for upstream-specific headers
                if headers and any(keyword in " ".join(headers).lower() for keyword in ["upstream", "transmit", "symbol rate"]):
                    _LOGGER.debug(f"Found upstream channel table with headers: {headers}")
                    rows = table.find_all("tr")[1:]  # Skip header row

                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 6:  # Typical upstream: Channel, Lock, Type, ID, Freq, Power
                            try:
                                channel_data = {
                                    "channel": self._extract_number(cols[0].text),
                                    "frequency": self._extract_float(cols[4].text),  # Freq column
                                    "power": self._extract_float(cols[5].text),      # Power column
                                }

                                # Skip channel if all critical values are None (invalid data)
                                if all(v is None for k, v in channel_data.items() if k != "channel"):
                                    _LOGGER.warning(f"Skipping upstream channel with all null values: {cols[0].text}")
                                    continue

                                # Skip if channel number itself is None
                                if channel_data["channel"] is None:
                                    _LOGGER.warning("Skipping upstream channel with invalid channel number")
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
