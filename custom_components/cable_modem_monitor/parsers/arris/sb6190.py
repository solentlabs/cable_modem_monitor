"""Parser for ARRIS SB6190 cable modem."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import NoAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType
from custom_components.cable_modem_monitor.lib.utils import extract_float, extract_number

from ..base_parser import ModemCapability, ModemParser, ParserStatus

_LOGGER = logging.getLogger(__name__)


class ArrisSB6190Parser(ModemParser):
    """Parser for ARRIS SB6190 cable modem."""

    name = "ARRIS SB6190"
    manufacturer = "ARRIS"
    models = ["SB6190"]

    ***REMOVED*** Parser status
    status = ParserStatus.VERIFIED  ***REMOVED*** Confirmed by @sfennell in PR ***REMOVED***22 (v3.0.0)
    verification_source = "https://github.com/solentlabs/cable_modem_monitor/pull/22"

    ***REMOVED*** Device metadata
    release_date = "2016"
    docsis_version = "3.0"
    fixtures_path = "tests/parsers/arris/fixtures/sb6190"

    ***REMOVED*** New authentication configuration (declarative)
    auth_config = NoAuthConfig(strategy=AuthStrategyType.NO_AUTH)

    url_patterns = [
        {"path": "/cgi-bin/status", "auth_method": "none", "auth_required": False},
    ]

    ***REMOVED*** Capabilities - ARRIS SB6190 (no system info available)
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
        """Detect if this is an ARRIS SB6190 modem."""
        ***REMOVED*** Look for model number and Downstream Bonded Channels table
        return bool(soup.find(string=lambda s: s and "SB6190" in s) and soup.find(string="Downstream Bonded Channels"))

    def _parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream channel data from ARRIS SB6190."""
        tables = soup.find_all("table")
        for table in tables:
            if table.find(string="Downstream Bonded Channels"):
                return self._parse_downstream_table(table)
        return []

    def _parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream channel data from ARRIS SB6190."""
        tables = soup.find_all("table")
        for table in tables:
            if table.find(string="Upstream Bonded Channels"):
                return self._parse_upstream_table(table)
        return []

    def _parse_transposed_table(self, rows: list, required_fields: list, is_upstream: bool = False) -> list[dict]:
        """Parse ARRIS transposed table where columns are channels."""
        try:
            data_map, channel_count = self._build_data_map(rows)
            return [
                self._build_channel_data(i, data_map, is_upstream)
                for i in range(channel_count)
                if self._build_channel_data(i, data_map, is_upstream) is not None
            ]
        except Exception as e:
            _LOGGER.error("Error parsing ARRIS SB6190 transposed table: %s", e)
            return []

    def _build_data_map(self, rows):
        data_map = {}
        channel_count = 0
        for row in rows:
            cells = row.find_all("td")
            if not cells or len(cells) < 2:
                continue
            label = cells[0].text.strip()
            values = [cell.text.strip() for cell in cells[1:]]
            if "Power Level" in label:
                label = "Power Level"
                if values and "Downstream Power Level reading" in values[0]:
                    values = values[1:]
            if len(values) > channel_count:
                channel_count = len(values)
            data_map[label] = values
        _LOGGER.debug(f"Transposed table has {channel_count} channels with labels: {list(data_map.keys())}")
        return data_map, channel_count

    def _build_channel_data(self, i, data_map, is_upstream):
        channel_data: dict[str, Any] = {}
        if "Channel ID" in data_map and i < len(data_map["Channel ID"]):
            channel_id = extract_number(data_map["Channel ID"][i])
            if channel_id is None:
                return None
            channel_data["channel_id"] = str(channel_id)
        else:
            return None
        if "Frequency" in data_map and i < len(data_map["Frequency"]):
            freq_text = data_map["Frequency"][i]
            freq_hz = extract_number(freq_text)
            channel_data["frequency"] = freq_hz
        if "Power Level" in data_map and i < len(data_map["Power Level"]):
            power_text = data_map["Power Level"][i]
            channel_data["power"] = extract_float(power_text)
        if not is_upstream:
            if "Signal to Noise Ratio" in data_map and i < len(data_map["Signal to Noise Ratio"]):
                snr_text = data_map["Signal to Noise Ratio"][i]
                channel_data["snr"] = extract_float(snr_text)
            channel_data["corrected"] = None
            channel_data["uncorrected"] = None
        _LOGGER.debug("Parsed ARRIS SB6190 channel %s: %s", channel_data.get("channel_id"), channel_data)
        return channel_data

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
            _LOGGER.error("Error merging ARRIS SB6190 error stats: %s", e)

    def _parse_downstream_table(self, table) -> list[dict]:
        """Parse non-transposed downstream table."""
        channels: list[dict[str, Any]] = []
        rows = table.find_all("tr")
        if not rows or len(rows) < 2:
            return channels

        for row in rows[2:]:
            cells = row.find_all("td")
            if len(cells) < 9:
                continue
            freq_text = cells[4].text.strip()
            freq_hz = None
            if "MHz" in freq_text:
                try:
                    freq_hz = int(float(freq_text.replace("MHz", "").strip()) * 1_000_000)
                except Exception:
                    freq_hz = None
            channel = {
                "channel_id": cells[3].text.strip(),
                "frequency": freq_hz,
                "power": extract_float(cells[5].text),
                "snr": extract_float(cells[6].text),
                "corrected": extract_number(cells[7].text),
                "uncorrected": extract_number(cells[8].text),
            }
            if not channel["channel_id"] or channel["channel_id"] == "----":
                continue
            channels.append(channel)
        return channels

    def _parse_upstream_table(self, table) -> list[dict]:
        """Parse non-transposed upstream table."""
        channels: list[dict[str, Any]] = []
        rows = table.find_all("tr")
        if not rows or len(rows) < 2:
            return channels

        for row in rows[2:]:
            cells = row.find_all("td")
            if len(cells) < 7:
                continue
            ***REMOVED*** Frequency is in MHz, convert to Hz
            freq_text = cells[5].text.strip()
            freq_hz = None
            if "MHz" in freq_text:
                try:
                    freq_hz = int(float(freq_text.replace("MHz", "").strip()) * 1_000_000)
                except Exception:
                    freq_hz = None
            channel = {
                "channel_id": cells[3].text.strip(),
                "frequency": freq_hz,
                "power": extract_float(cells[6].text),
                ***REMOVED*** Add more fields as needed
            }
            if not channel["channel_id"] or channel["channel_id"] == "----":
                continue
            channels.append(channel)
        return channels
