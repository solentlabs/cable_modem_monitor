"""Web scraper for cable modem data."""
import logging
import requests
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


class ModemScraper:
    """Scrape data from cable modem web interface."""

    def __init__(self, host: str):
        """Initialize the modem scraper."""
        self.host = host
        self.base_url = f"http://{host}"

    def get_modem_data(self) -> dict:
        """Fetch and parse modem data."""
        try:
            ***REMOVED*** Try common Motorola modem signal data URLs
            urls_to_try = [
                f"{self.base_url}/cmSignalData.htm",
                f"{self.base_url}/cmSignal.html",
                f"{self.base_url}/",
            ]

            html = None
            for url in urls_to_try:
                try:
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        html = response.text
                        _LOGGER.debug(f"Successfully fetched data from {url}")
                        break
                except requests.RequestException as e:
                    _LOGGER.debug(f"Failed to fetch from {url}: {e}")
                    continue

            if not html:
                _LOGGER.error("Could not fetch data from any known modem URL")
                return {"connection_status": "offline", "downstream": [], "upstream": []}

            soup = BeautifulSoup(html, "html.parser")

            ***REMOVED*** Parse downstream channels
            downstream_channels = self._parse_downstream_channels(soup)

            ***REMOVED*** Parse upstream channels
            upstream_channels = self._parse_upstream_channels(soup)

            ***REMOVED*** Calculate totals
            total_corrected = sum(
                ch.get("corrected", 0) for ch in downstream_channels
            )
            total_uncorrected = sum(
                ch.get("uncorrected", 0) for ch in downstream_channels
            )

            return {
                "connection_status": "online" if downstream_channels else "offline",
                "downstream": downstream_channels,
                "upstream": upstream_channels,
                "total_corrected": total_corrected,
                "total_uncorrected": total_uncorrected,
            }

        except Exception as e:
            _LOGGER.error(f"Error fetching modem data: {e}")
            return {"connection_status": "offline", "downstream": [], "upstream": []}

    def _parse_downstream_channels(self, soup: BeautifulSoup) -> list:
        """Parse downstream channel data from HTML."""
        channels = []

        try:
            ***REMOVED*** Look for common table structures in Motorola modems
            ***REMOVED*** This may need adjustment based on your specific modem model
            tables = soup.find_all("table")

            for table in tables:
                ***REMOVED*** Look for downstream/receive channel tables
                header = table.find("th")
                if header and ("downstream" in header.text.lower() or "receive" in header.text.lower()):
                    rows = table.find_all("tr")[1:]  ***REMOVED*** Skip header row

                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 4:  ***REMOVED*** Typical: Channel, Freq, Power, SNR, Corrected, Uncorrected
                            try:
                                channel_data = {
                                    "channel": self._extract_number(cols[0].text),
                                    "frequency": self._extract_number(cols[1].text),
                                    "power": self._extract_float(cols[2].text),
                                    "snr": self._extract_float(cols[3].text),
                                }

                                ***REMOVED*** Some modems have corrected/uncorrected in columns 4 and 5
                                if len(cols) >= 6:
                                    channel_data["corrected"] = self._extract_number(cols[4].text)
                                    channel_data["uncorrected"] = self._extract_number(cols[5].text)

                                channels.append(channel_data)
                            except Exception as e:
                                _LOGGER.debug(f"Error parsing downstream channel row: {e}")
                                continue

        except Exception as e:
            _LOGGER.error(f"Error parsing downstream channels: {e}")

        return channels

    def _parse_upstream_channels(self, soup: BeautifulSoup) -> list:
        """Parse upstream channel data from HTML."""
        channels = []

        try:
            tables = soup.find_all("table")

            for table in tables:
                ***REMOVED*** Look for upstream/transmit channel tables
                header = table.find("th")
                if header and ("upstream" in header.text.lower() or "transmit" in header.text.lower()):
                    rows = table.find_all("tr")[1:]  ***REMOVED*** Skip header row

                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 3:  ***REMOVED*** Typical: Channel, Freq, Power
                            try:
                                channel_data = {
                                    "channel": self._extract_number(cols[0].text),
                                    "frequency": self._extract_number(cols[1].text),
                                    "power": self._extract_float(cols[2].text),
                                }
                                channels.append(channel_data)
                            except Exception as e:
                                _LOGGER.debug(f"Error parsing upstream channel row: {e}")
                                continue

        except Exception as e:
            _LOGGER.error(f"Error parsing upstream channels: {e}")

        return channels

    def _extract_number(self, text: str) -> int:
        """Extract integer from text."""
        try:
            ***REMOVED*** Remove common units and extract number
            cleaned = "".join(c for c in text if c.isdigit() or c == "-")
            return int(cleaned) if cleaned else 0
        except ValueError:
            return 0

    def _extract_float(self, text: str) -> float:
        """Extract float from text."""
        try:
            ***REMOVED*** Remove units (dB, dBmV, MHz, etc.) and extract number
            cleaned = "".join(c for c in text if c.isdigit() or c in ".-")
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0
