"""Parser for Technicolor TC4400 cable modem."""
import logging
from bs4 import BeautifulSoup
from .base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class TechnicolorTC4400Parser(ModemParser):
    """Parser for Technicolor TC4400 cable modem."""

    name = "Technicolor TC4400"
    manufacturer = "Technicolor"
    models = ["TC4400"]

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Technicolor TC4400 modem."""
        ***REMOVED*** Check URL for TC4400 specific endpoint
        if "cmconnectionstatus.html" in url.lower():
            return True

        ***REMOVED*** Check for Technicolor-specific markers in HTML
        ***REMOVED*** Note: This parser needs real HTML samples to improve detection
        title = soup.find("title")
        if title and "Technicolor" in title.text:
            return True

        return False

    def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """
        Parse downstream channel data from Technicolor TC4400.

        Note: This is a placeholder implementation.
        TC4400 parser needs real HTML samples to implement proper parsing.
        Community users with TC4400 modems should provide HTML samples.
        """
        channels = []

        try:
            ***REMOVED*** TODO: Implement TC4400-specific parsing when HTML samples available
            ***REMOVED*** For now, try generic table parsing similar to Motorola
            tables = soup.find_all("table")
            _LOGGER.debug(f"TC4400: Found {len(tables)} tables to parse")

            for table in tables:
                rows = table.find_all("tr")
                if len(rows) < 2:  ***REMOVED*** Need header + data
                    continue

                ***REMOVED*** Look for downstream channel indicators
                header_row = rows[0]
                header_text = " ".join([th.text.strip().lower() for th in header_row.find_all(['th', 'td'])])

                if any(keyword in header_text for keyword in ['downstream', 'channel', 'frequency', 'power', 'snr']):
                    _LOGGER.debug(f"TC4400: Found potential downstream table with header: {header_text}")

                    ***REMOVED*** Try to parse rows
                    for row in rows[1:]:
                        cols = row.find_all(['td', 'th'])
                        if len(cols) >= 4:  ***REMOVED*** At least channel, freq, power, snr
                            try:
                                channel_data = {
                                    "channel_id": str(self._extract_number(cols[0].text) or len(channels) + 1),
                                    "frequency": self._parse_frequency(cols[1].text),
                                    "power": self._extract_float(cols[2].text),
                                    "snr": self._extract_float(cols[3].text),
                                }

                                ***REMOVED*** Only add if we got valid data
                                if channel_data["frequency"] and channel_data["power"] and channel_data["snr"]:
                                    channels.append(channel_data)
                                    _LOGGER.debug(f"TC4400: Parsed downstream channel: {channel_data}")
                            except Exception as e:
                                _LOGGER.debug(f"TC4400: Error parsing row: {e}")
                                continue

            if not channels:
                _LOGGER.warning(
                    "TC4400 parser found no downstream channels. "
                    "HTML structure may be different than expected. "
                    "Please share HTML sample at: https://github.com/kwschulz/cable_modem_monitor/issues"
                )

        except Exception as e:
            _LOGGER.error(f"Error parsing TC4400 downstream channels: {e}")

        return channels

    def parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """
        Parse upstream channel data from Technicolor TC4400.

        Note: This is a placeholder implementation.
        """
        channels = []

        try:
            tables = soup.find_all("table")

            for table in tables:
                rows = table.find_all("tr")
                if len(rows) < 2:
                    continue

                header_row = rows[0]
                header_text = " ".join([th.text.strip().lower() for th in header_row.find_all(['th', 'td'])])

                if any(keyword in header_text for keyword in ['upstream', 'channel', 'frequency', 'power']):
                    _LOGGER.debug(f"TC4400: Found potential upstream table with header: {header_text}")

                    for row in rows[1:]:
                        cols = row.find_all(['td', 'th'])
                        if len(cols) >= 3:  ***REMOVED*** At least channel, freq, power
                            try:
                                channel_data = {
                                    "channel_id": str(self._extract_number(cols[0].text) or len(channels) + 1),
                                    "frequency": self._parse_frequency(cols[1].text),
                                    "power": self._extract_float(cols[2].text),
                                }

                                if channel_data["frequency"] and channel_data["power"]:
                                    channels.append(channel_data)
                                    _LOGGER.debug(f"TC4400: Parsed upstream channel: {channel_data}")
                            except Exception as e:
                                _LOGGER.debug(f"TC4400: Error parsing row: {e}")
                                continue

            if not channels:
                _LOGGER.warning(
                    "TC4400 parser found no upstream channels. "
                    "HTML structure may be different than expected."
                )

        except Exception as e:
            _LOGGER.error(f"Error parsing TC4400 upstream channels: {e}")

        return channels

    def _parse_frequency(self, text: str) -> int | None:
        """Parse frequency, handling both Hz and MHz formats."""
        try:
            ***REMOVED*** Extract number
            freq = self._extract_float(text)
            if freq is None:
                return None

            ***REMOVED*** Check if it's in MHz (TC4400 might use MHz)
            if "mhz" in text.lower() or (freq > 0 and freq < 2000):
                ***REMOVED*** Convert MHz to Hz
                return int(freq * 1_000_000)
            else:
                ***REMOVED*** Already in Hz
                return int(freq)
        except Exception:
            return None

    def _extract_number(self, text: str) -> int | None:
        """Extract integer from text."""
        try:
            cleaned = "".join(c for c in text if c.isdigit() or c == "-")
            return int(cleaned) if cleaned else None
        except ValueError:
            return None

    def _extract_float(self, text: str) -> float | None:
        """Extract float from text."""
        try:
            cleaned = "".join(c for c in text if c.isdigit() or c in ".-")
            return float(cleaned) if cleaned else None
        except ValueError:
            return None
