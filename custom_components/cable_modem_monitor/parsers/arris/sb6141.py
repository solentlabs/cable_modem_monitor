"""Parser for ARRIS SB6141 cable modem."""
import logging
from bs4 import BeautifulSoup
from ..base_parser import ModemParser
from custom_components.cable_modem_monitor.lib.utils import extract_number, extract_float

_LOGGER = logging.getLogger(__name__)


class ArrisSB6141Parser(ModemParser):
    """Parser for ARRIS SB6141 cable modem."""

    name = "ARRIS SB6141"
    manufacturer = "ARRIS"
    models = ["SB6141"]

    url_patterns = [
        {"path": "/cmSignalData.htm", "auth_method": "none"},
    ]

    def login(self, session, base_url, username, password) -> bool:
        """ARRIS modems do not have a login page."""
        return True

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem."""
        downstream_channels = self._parse_downstream(soup)
        upstream_channels = self._parse_upstream(soup)

        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": {},
        }

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is an ARRIS SB6141 modem."""
        # Look for "Startup Procedure" text which is unique to ARRIS
        if soup.find(string="Startup Procedure"):
            return True

        # Look for transposed table structure with "Channel ID" row
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if cells and cells[0].text.strip() == "Channel ID":
                    # Additional check for "Power Level" row (ARRIS-specific)
                    for check_row in rows:
                        check_cells = check_row.find_all("td")
                        if check_cells and "Power Level" in check_cells[0].text:
                            return True

        return False

    def _parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream channel data from ARRIS SB6141."""
        downstream_channels = []

        try:
            tables = soup.find_all("table")
            _LOGGER.debug(f"Parsing ARRIS SB6141 format from {len(tables)} tables")

            # Find tables by looking for "Channel ID" row
            for table in tables:
                rows = table.find_all("tr")
                if not rows:
                    continue

                # Check if this table has channel data
                row_labels = []
                for row in rows:
                    cells = row.find_all("td")
                    if cells and len(cells) > 0:
                        label = cells[0].text.strip()
                        row_labels.append(label)

                # Detect downstream table
                has_channel_id = "Channel ID" in row_labels
                has_power_level = any("Power Level" in label for label in row_labels)
                has_snr = "Signal to Noise Ratio" in row_labels
                has_downstream_mod = "Downstream Modulation" in row_labels

                if has_channel_id and has_power_level and (has_snr or has_downstream_mod):
                    # Downstream table
                    _LOGGER.debug("Found ARRIS downstream table")
                    downstream_channels = self._parse_transposed_table(
                        rows, ["Channel ID", "Frequency", "Signal to Noise Ratio", "Power Level"]
                    )
                elif "Total Correctable Codewords" in row_labels:
                    # Signal stats table - merge with downstream channels
                    _LOGGER.debug("Found ARRIS signal stats table")
                    self._merge_error_stats(downstream_channels, rows)

            _LOGGER.debug(f"ARRIS parsing found {len(downstream_channels)} downstream channels")

        except Exception as e:
            _LOGGER.error(f"Error parsing ARRIS SB6141 downstream: {e}")

        return downstream_channels

    def _parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream channel data from ARRIS SB6141."""
        upstream_channels = []

        try:
            tables = soup.find_all("table")

            for table in tables:
                rows = table.find_all("tr")
                if not rows:
                    continue

                # Check if this is upstream table
                row_labels = []
                for row in rows:
                    cells = row.find_all("td")
                    if cells and len(cells) > 0:
                        label = cells[0].text.strip()
                        row_labels.append(label)

                # Detect upstream table
                has_channel_id = "Channel ID" in row_labels
                has_power_level = any("Power Level" in label for label in row_labels)
                has_symbol_rate = "Symbol Rate" in row_labels
                has_upstream_mod = "Upstream Modulation" in row_labels

                if has_channel_id and has_power_level and (has_symbol_rate or has_upstream_mod):
                    # Upstream table
                    _LOGGER.debug("Found ARRIS upstream table")
                    upstream_channels = self._parse_transposed_table(
                        rows, ["Channel ID", "Frequency", "Power Level"], is_upstream=True
                    )

            _LOGGER.debug(f"ARRIS parsing found {len(upstream_channels)} upstream channels")

        except Exception as e:
            _LOGGER.error(f"Error parsing ARRIS SB6141 upstream: {e}")

        return upstream_channels

    def _parse_transposed_table(
        self, rows: list, required_fields: list, is_upstream: bool = False
    ) -> list[dict]:
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
                    if values and "Downstream Power Level reading" in values[0]:
                        values = values[1:]  # Skip nested table text

                # Update channel count from longest row
                if len(values) > channel_count:
                    channel_count = len(values)

                data_map[label] = values

            _LOGGER.debug(
                f"Transposed table has {channel_count} channels with labels: {list(data_map.keys())}"
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

                # Extract frequency (already in Hz for ARRIS)
                if "Frequency" in data_map and i < len(data_map["Frequency"]):
                    freq_text = data_map["Frequency"][i]
                    # ARRIS format: "519000000 Hz" - extract number
                    freq_hz = extract_number(freq_text)
                    channel_data["frequency"] = freq_hz

                # Extract power level
                if "Power Level" in data_map and i < len(data_map["Power Level"]):
                    power_text = data_map["Power Level"][i]
                    channel_data["power"] = extract_float(power_text)

                if not is_upstream:
                    # Downstream-specific fields
                    if "Signal to Noise Ratio" in data_map and i < len(
                        data_map["Signal to Noise Ratio"]
                    ):
                        snr_text = data_map["Signal to Noise Ratio"][i]
                        channel_data["snr"] = extract_float(snr_text)

                    # Initialize error counters (will be filled from stats table)
                    channel_data["corrected"] = None
                    channel_data["uncorrected"] = None

                # Skip if missing required data
                if channel_data.get("channel_id") is not None:
                    channels.append(channel_data)
                    _LOGGER.debug(
                        f"Parsed ARRIS channel {channel_data.get('channel_id')}: {channel_data}"
                    )

        except Exception as e:
            _LOGGER.error(f"Error parsing ARRIS transposed table: {e}")

        return channels

    def _merge_error_stats(self, downstream_channels: list[dict], stats_rows: list) -> None:
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
                if "Total Correctable Codewords" in data_map and i < len(
                    data_map["Total Correctable Codewords"]
                ):
                    channel["corrected"] = extract_number(
                        data_map["Total Correctable Codewords"][i]
                    )

                if "Total Uncorrectable Codewords" in data_map and i < len(
                    data_map["Total Uncorrectable Codewords"]
                ):
                    channel["uncorrected"] = extract_number(
                        data_map["Total Uncorrectable Codewords"][i]
                    )

        except Exception as e:
            _LOGGER.error(f"Error merging ARRIS error stats: {e}")
