"""Parser for ARRIS SB6141 cable modem."""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import NoAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType
from custom_components.cable_modem_monitor.lib.utils import extract_float, extract_number

from ..base_parser import ModemCapability, ModemParser

_LOGGER = logging.getLogger(__name__)


class ArrisSB6141Parser(ModemParser):
    """Parser for ARRIS SB6141 cable modem."""

    name = "ARRIS SB6141"
    manufacturer = "ARRIS"
    models = ["SB6141"]

    ***REMOVED*** Verification status
    verified = True  ***REMOVED*** Confirmed by @captain-coredump (vreihen) in v2.0.0
    verification_source = (
        "https://community.home-assistant.io/t/cable-modem-monitor-track-your-internet-signal-quality-in-home-assistant"
    )

    ***REMOVED*** Device metadata
    release_date = "2012"
    end_of_life = "2020"  ***REMOVED*** No longer manufactured
    docsis_version = "3.0"
    fixtures_path = "tests/parsers/arris/fixtures/sb6141"

    ***REMOVED*** New authentication configuration (declarative)
    auth_config = NoAuthConfig(strategy=AuthStrategyType.NO_AUTH)

    url_patterns = [
        {"path": "/cmSignalData.htm", "auth_method": "none", "auth_required": False},
    ]

    ***REMOVED*** Capabilities - ARRIS SB6141 (no system info available)
    capabilities = {
        ModemCapability.DOWNSTREAM_CHANNELS,
        ModemCapability.UPSTREAM_CHANNELS,
    }

    def login(self, session, base_url, username, password) -> tuple[bool, str | None]:
        """ARRIS modems do not require authentication."""
        return (True, None)

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
        ***REMOVED*** Check for SB6141 model number first (most specific)
        if soup.find(string=lambda s: s and "SB6141" in s):
            return True

        ***REMOVED*** Exclude other known Arris models to avoid conflicts
        if soup.find(string=lambda s: s and "SB6190" in s):
            return False

        ***REMOVED*** Look for "Startup Procedure" text which is common to ARRIS modems
        if soup.find(string="Startup Procedure"):
            return True

        ***REMOVED*** Look for transposed table structure with "Channel ID" row
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if cells and cells[0].text.strip() == "Channel ID":
                    ***REMOVED*** Additional check for "Power Level" row (ARRIS-specific)
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
            _LOGGER.debug("Parsing ARRIS SB6141 format from %s tables", len(tables))

            ***REMOVED*** Find tables by looking for "Channel ID" row
            for table in tables:
                rows = table.find_all("tr")
                if not rows:
                    continue

                ***REMOVED*** Check if this table has channel data
                row_labels = []
                for row in rows:
                    cells = row.find_all("td")
                    if cells and len(cells) > 0:
                        label = cells[0].text.strip()
                        row_labels.append(label)

                ***REMOVED*** Detect downstream table
                has_channel_id = "Channel ID" in row_labels
                has_power_level = any("Power Level" in label for label in row_labels)
                has_snr = "Signal to Noise Ratio" in row_labels
                has_downstream_mod = "Downstream Modulation" in row_labels

                if has_channel_id and has_power_level and (has_snr or has_downstream_mod):
                    ***REMOVED*** Downstream table
                    _LOGGER.debug("Found ARRIS downstream table")
                    downstream_channels = self._parse_transposed_table(
                        rows, ["Channel ID", "Frequency", "Signal to Noise Ratio", "Power Level"]
                    )
                elif "Total Correctable Codewords" in row_labels:
                    ***REMOVED*** Signal stats table - merge with downstream channels
                    _LOGGER.debug("Found ARRIS signal stats table")
                    self._merge_error_stats(downstream_channels, rows)

            _LOGGER.debug("ARRIS parsing found %s downstream channels", len(downstream_channels))

        except Exception as e:
            _LOGGER.error("Error parsing ARRIS SB6141 downstream: %s", e)

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

                ***REMOVED*** Check if this is upstream table
                row_labels = []
                for row in rows:
                    cells = row.find_all("td")
                    if cells and len(cells) > 0:
                        label = cells[0].text.strip()
                        row_labels.append(label)

                ***REMOVED*** Detect upstream table
                has_channel_id = "Channel ID" in row_labels
                has_power_level = any("Power Level" in label for label in row_labels)
                has_symbol_rate = "Symbol Rate" in row_labels
                has_upstream_mod = "Upstream Modulation" in row_labels

                if has_channel_id and has_power_level and (has_symbol_rate or has_upstream_mod):
                    ***REMOVED*** Upstream table
                    _LOGGER.debug("Found ARRIS upstream table")
                    upstream_channels = self._parse_transposed_table(
                        rows, ["Channel ID", "Frequency", "Power Level"], is_upstream=True
                    )

            _LOGGER.debug("ARRIS parsing found %s upstream channels", len(upstream_channels))

        except Exception as e:
            _LOGGER.error("Error parsing ARRIS SB6141 upstream: %s", e)

        return upstream_channels

    def _build_transposed_data_map(self, rows: list) -> tuple[dict, int]:
        """Build data map from transposed table rows.

        Returns:
            Tuple of (data_map, channel_count)
        """
        data_map = {}
        channel_count = 0

        for row in rows:
            cells = row.find_all("td")
            if not cells or len(cells) < 2:
                continue

            label = cells[0].text.strip()
            values = [cell.text.strip() for cell in cells[1:]]  ***REMOVED*** Skip first cell (label)

            ***REMOVED*** Normalize label and handle nested tables in Power Level row
            if "Power Level" in label:
                label = "Power Level"
                ***REMOVED*** ARRIS SB6141 has nested table in Power Level row - skip first value
                if values and "Downstream Power Level reading" in values[0]:
                    values = values[1:]  ***REMOVED*** Skip nested table text

            ***REMOVED*** Update channel count from longest row
            if len(values) > channel_count:
                channel_count = len(values)

            data_map[label] = values

        return data_map, channel_count

    def _extract_channel_data_at_index(self, data_map: dict, index: int, is_upstream: bool) -> dict | None:
        """Extract channel data from data_map at given column index.

        Returns:
            Channel data dict or None if channel_id is missing
        """
        channel_data: dict[str, str | int | float | None] = {}

        ***REMOVED*** Extract channel ID
        if "Channel ID" in data_map and index < len(data_map["Channel ID"]):
            channel_id = extract_number(data_map["Channel ID"][index])
            if channel_id is None:
                return None
            channel_data["channel_id"] = str(channel_id)
        else:
            return None

        ***REMOVED*** Extract frequency (already in Hz for ARRIS)
        if "Frequency" in data_map and index < len(data_map["Frequency"]):
            freq_text = data_map["Frequency"][index]
            freq_hz = extract_number(freq_text)
            channel_data["frequency"] = freq_hz

        ***REMOVED*** Extract power level
        if "Power Level" in data_map and index < len(data_map["Power Level"]):
            power_text = data_map["Power Level"][index]
            channel_data["power"] = extract_float(power_text)

        if not is_upstream:
            ***REMOVED*** Downstream-specific fields
            if "Signal to Noise Ratio" in data_map and index < len(data_map["Signal to Noise Ratio"]):
                snr_text = data_map["Signal to Noise Ratio"][index]
                channel_data["snr"] = extract_float(snr_text)

            ***REMOVED*** Initialize error counters (will be filled from stats table)
            channel_data["corrected"] = None
            channel_data["uncorrected"] = None

        return channel_data

    def _parse_transposed_table(self, rows: list, required_fields: list, is_upstream: bool = False) -> list[dict]:
        """Parse ARRIS transposed table where columns are channels."""
        channels = []

        try:
            ***REMOVED*** Build a map of row_label -> [values for each channel]
            data_map, channel_count = self._build_transposed_data_map(rows)

            _LOGGER.debug(f"Transposed table has {channel_count} channels with labels: {list(data_map.keys())}")

            ***REMOVED*** Now transpose: create one channel dict per column
            for i in range(channel_count):
                channel_data = self._extract_channel_data_at_index(data_map, i, is_upstream)

                if channel_data is not None:
                    channels.append(channel_data)
                    _LOGGER.debug("Parsed ARRIS channel %s: %s", channel_data.get("channel_id"), channel_data)

        except Exception as e:
            _LOGGER.error("Error parsing ARRIS transposed table: %s", e)

        return channels

    def _merge_error_stats(self, downstream_channels: list[dict], stats_rows: list) -> None:
        """Merge error statistics from signal stats table into downstream channels."""
        try:
            ***REMOVED*** Parse stats table (also transposed)
            data_map = {}
            for row in stats_rows:
                cells = row.find_all("td")
                if not cells or len(cells) < 2:
                    continue

                label = cells[0].text.strip()
                values = [cell.text.strip() for cell in cells[1:]]
                data_map[label] = values

            ***REMOVED*** Match channels by index
            for i, channel in enumerate(downstream_channels):
                if "Total Correctable Codewords" in data_map and i < len(data_map["Total Correctable Codewords"]):
                    channel["corrected"] = extract_number(data_map["Total Correctable Codewords"][i])

                if "Total Uncorrectable Codewords" in data_map and i < len(data_map["Total Uncorrectable Codewords"]):
                    channel["uncorrected"] = extract_number(data_map["Total Uncorrectable Codewords"][i])

        except Exception as e:
            _LOGGER.error("Error merging ARRIS error stats: %s", e)
