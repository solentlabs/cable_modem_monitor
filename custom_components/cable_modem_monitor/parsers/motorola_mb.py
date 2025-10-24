"""Parser for Motorola MB series cable modems."""
import logging
from bs4 import BeautifulSoup
from .base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class MotorolaMBParser(ModemParser):
    """Parser for Motorola MB series cable modems (MB7420, MB7621, MB8600, etc.)."""

    name = "Motorola MB Series"
    manufacturer = "Motorola"
    models = ["MB7420", "MB7621", "MB8600", "MB8611"]

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Motorola MB series modem."""
        ***REMOVED*** Check for Motorola-specific title
        title = soup.find("title")
        if title and "Motorola Cable Modem" in title.text:
            return True

        ***REMOVED*** Check for Motorola-specific CSS class
        if soup.find("td", class_="moto-param-header-s"):
            return True

        ***REMOVED*** Check for Motorola Connection page URL
        if "MotoConnection.asp" in url:
            return True

        return False

    def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream channel data from Motorola MB modem."""
        channels = []

        try:
            tables = soup.find_all("table")
            _LOGGER.debug(f"Found {len(tables)} tables to parse")

            for table in tables:
                ***REMOVED*** Use direct children only (recursive=False) to avoid nested table issues
                all_rows = table.find_all("tr", recursive=False)

                ***REMOVED*** If no direct children, try one level deeper (for tables wrapped in tbody)
                if not all_rows:
                    tbody = table.find("tbody")
                    if tbody:
                        all_rows = tbody.find_all("tr", recursive=False)

                if not all_rows:
                    continue

                ***REMOVED*** Find the header row by looking for moto-param-header-s class
                header_row = None
                headers = []
                for row in all_rows:
                    potential_headers = [
                        td.text.strip()
                        for td in row.find_all("td", class_="moto-param-header-s")
                    ]
                    if potential_headers and "Channel" in potential_headers:
                        header_row = row
                        headers = potential_headers
                        break

                ***REMOVED*** If we found the header row with channel data headers
                if header_row and headers:
                    _LOGGER.debug(
                        f"Found downstream channel table with headers: {headers}"
                    )
                    ***REMOVED*** Get all rows after the header row
                    header_index = all_rows.index(header_row)
                    data_rows = all_rows[header_index + 1 :]  ***REMOVED*** Skip header row

                    for row in data_rows:
                        cols = row.find_all("td")
                        if len(cols) >= 9:  ***REMOVED*** Channel, Lock, Modulation, ID, Freq, Pwr, SNR, Corrected, Uncorrected
                            try:
                                ***REMOVED*** Skip the "Total" row at the bottom of the table
                                channel_text = cols[0].text.strip()
                                if channel_text.lower() == "total":
                                    _LOGGER.debug(
                                        "Skipping Total row to avoid double-counting errors"
                                    )
                                    continue

                                freq_mhz = self._extract_float(
                                    cols[4].text
                                )  ***REMOVED*** Freq column in MHz
                                ***REMOVED*** Convert MHz to Hz
                                freq_hz = (
                                    freq_mhz * 1_000_000
                                    if freq_mhz is not None
                                    else None
                                )

                                channel_id = self._extract_number(cols[0].text)
                                if channel_id is None:
                                    _LOGGER.warning(
                                        "Skipping downstream channel with invalid channel number"
                                    )
                                    continue

                                channel_data = {
                                    "channel_id": str(channel_id),
                                    "frequency": freq_hz,
                                    "power": self._extract_float(cols[5].text),  ***REMOVED*** Pwr column
                                    "snr": self._extract_float(cols[6].text),  ***REMOVED*** SNR column
                                    "corrected": self._extract_number(cols[7].text),
                                    "uncorrected": self._extract_number(cols[8].text),
                                    "modulation": cols[2].text.strip() if len(cols) > 2 else None,
                                }

                                ***REMOVED*** Skip channel if all critical values are None (invalid data)
                                if all(
                                    v is None
                                    for k, v in channel_data.items()
                                    if k not in ["channel_id", "modulation", "corrected", "uncorrected"]
                                ):
                                    _LOGGER.warning(
                                        f"Skipping downstream channel with all null values: {cols[0].text}"
                                    )
                                    continue

                                channels.append(channel_data)
                                _LOGGER.debug(
                                    f"Parsed downstream channel {channel_data['channel_id']}: {channel_data}"
                                )
                            except Exception as e:
                                _LOGGER.error(f"Error parsing downstream channel row: {e}")
                                continue

            _LOGGER.debug(f"Total downstream channels parsed: {len(channels)}")

        except Exception as e:
            _LOGGER.error(f"Error parsing downstream channels: {e}")

        return channels

    def parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream channel data from Motorola MB modem."""
        channels = []

        try:
            tables = soup.find_all("table")

            for table in tables:
                ***REMOVED*** Use direct children only (recursive=False) to avoid nested table issues
                all_rows = table.find_all("tr", recursive=False)

                ***REMOVED*** If no direct children, try one level deeper (for tables wrapped in tbody)
                if not all_rows:
                    tbody = table.find("tbody")
                    if tbody:
                        all_rows = tbody.find_all("tr", recursive=False)

                if not all_rows:
                    continue

                ***REMOVED*** Find the header row for upstream channels
                header_row = None
                headers = []
                for row in all_rows:
                    potential_headers = [
                        td.text.strip()
                        for td in row.find_all("td", class_="moto-param-header-s")
                    ]
                    ***REMOVED*** Upstream tables have "Channel Type" header
                    if potential_headers and any(
                        "Channel Type" in h or ("Channel" in h and "Type" in potential_headers)
                        for h in potential_headers
                    ):
                        header_row = row
                        headers = potential_headers
                        break

                if header_row and headers:
                    _LOGGER.debug(f"Found upstream channel table with headers: {headers}")
                    ***REMOVED*** Get all rows after the header row
                    header_index = all_rows.index(header_row)
                    data_rows = all_rows[header_index + 1 :]  ***REMOVED*** Skip header row

                    for row in data_rows:
                        cols = row.find_all("td")
                        ***REMOVED*** Upstream table columns: Channel, Lock Status, Channel Type, Channel ID, Symb Rate, Freq (MHz), Pwr (dBmV)
                        if len(cols) >= 7:
                            try:
                                ***REMOVED*** Extract frequency from column 5 (0-indexed)
                                freq_mhz = self._extract_float(cols[5].text)
                                freq_hz = (
                                    freq_mhz * 1_000_000
                                    if freq_mhz is not None
                                    else None
                                )

                                ***REMOVED*** Extract channel number from column 0
                                channel_id = self._extract_number(cols[0].text)
                                if channel_id is None:
                                    _LOGGER.warning(
                                        "Skipping upstream channel with invalid channel number"
                                    )
                                    continue

                                lock_status = cols[1].text.strip() if len(cols) > 1 else None

                                ***REMOVED*** Skip channels that are not locked (inactive channels)
                                if lock_status and "not locked" in lock_status.lower():
                                    _LOGGER.debug(
                                        f"Skipping upstream channel {channel_id}: not locked"
                                    )
                                    continue

                                channel_data = {
                                    "channel_id": str(channel_id),
                                    "frequency": freq_hz,
                                    "power": self._extract_float(cols[6].text),  ***REMOVED*** Power is in column 6
                                    "modulation": lock_status,
                                }

                                ***REMOVED*** Skip if all critical values are None
                                if all(
                                    v is None
                                    for k, v in channel_data.items()
                                    if k not in ["channel_id", "modulation"]
                                ):
                                    _LOGGER.warning(
                                        f"Skipping upstream channel with all null values: {cols[0].text}"
                                    )
                                    continue

                                channels.append(channel_data)
                                _LOGGER.debug(
                                    f"Parsed upstream channel {channel_data['channel_id']}: {channel_data}"
                                )
                            except Exception as e:
                                _LOGGER.error(f"Error parsing upstream channel row: {e}")
                                continue

            _LOGGER.debug(f"Total upstream channels parsed: {len(channels)}")

        except Exception as e:
            _LOGGER.error(f"Error parsing upstream channels: {e}")

        return channels

    def parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information from Motorola MB modem."""
        info = {}

        try:
            ***REMOVED*** Parse system uptime from MotoConnection.asp page
            uptime = self._parse_system_uptime(soup)
            if uptime and uptime != "Unknown":
                info["system_uptime"] = uptime

            ***REMOVED*** Software version and channel counts require MotoHome.asp
            ***REMOVED*** which needs to be fetched separately by the scraper
            ***REMOVED*** For now, just return uptime from connection page

        except Exception as e:
            _LOGGER.error(f"Error parsing system info: {e}")

        return info

    def _parse_system_uptime(self, soup: BeautifulSoup) -> str:
        """Parse system uptime from MotoConnection.asp page."""
        try:
            ***REMOVED*** Look for "System Up Time" label
            rows = soup.find_all("tr")

            for row in rows:
                ***REMOVED*** Check all cells in the row for "System Up Time" text
                cells = row.find_all("td")
                for i, cell in enumerate(cells):
                    if "System Up Time" in cell.text:
                        ***REMOVED*** Value is typically in the next cell or cell with class
                        value_cell = row.find("td", class_="moto-content-value")
                        if value_cell:
                            uptime = value_cell.text.strip()
                            if uptime and uptime != "N/A":
                                _LOGGER.debug(f"Found system uptime: {uptime}")
                                return uptime

                        ***REMOVED*** Or try the next cell
                        if i + 1 < len(cells):
                            uptime = cells[i + 1].text.strip()
                            if uptime and uptime != "N/A":
                                _LOGGER.debug(f"Found system uptime: {uptime}")
                                return uptime

            _LOGGER.debug("System uptime not found")
            return "Unknown"

        except Exception as e:
            _LOGGER.error(f"Error parsing system uptime: {e}")
            return "Unknown"

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
