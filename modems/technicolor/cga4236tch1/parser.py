"""Parser for Technicolor CGA4236 cable modem REST API."""

from __future__ import annotations

import html
import logging
from typing import Any

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.lib.utils import extract_float, extract_number

_LOGGER = logging.getLogger(__name__)

_MODEM_ENDPOINT = "/api/v1/modem/exUSTbl,exDSTbl,USTbl,DSTbl,ErrTbl"
_SYSTEM_ENDPOINT = (
    "/api/v1/system/CMStatus,ModelName,Manufacturer,SerialNumber,"
    "HardwareVersion,SoftwareVersion,UpTime,BootloaderVersion,CoreVersion,"
    "FirmwareName,FirmwareBuildTime,ProcessorSpeed,CMMACAddress,LocalTime,"
    "Hardware,MemTotal,MemFree,MTAMACAddress"
)


class TechnicolorCGA4236Parser(ModemParser):
    """Parser for Technicolor CGA4236 JSON API."""

    def parse_resources(self, resources: dict[str, Any]) -> dict:
        """Parse downstream/upstream/system info from pre-fetched JSON resources."""
        modem_data = self._extract_modem_data(resources)
        system_data = self._extract_system_data(resources)

        error_rows = modem_data.get("ErrTbl", [])
        errors_by_index = self._build_errors_by_index(error_rows)

        downstream = self._parse_downstream(modem_data, errors_by_index)
        upstream = self._parse_upstream(modem_data)
        system_info = self._parse_system_info(system_data)

        return {
            "downstream": downstream,
            "upstream": upstream,
            "system_info": system_info,
        }

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Legacy parser interface: fetch API data when session/base_url are available."""
        if session and base_url:
            resources: dict[str, Any] = {}
            for path in (_MODEM_ENDPOINT, _SYSTEM_ENDPOINT):
                try:
                    response = session.get(f"{base_url}{path}", timeout=30, verify=session.verify)
                    if response.status_code == 200:
                        resources[path] = response.json()
                except Exception as err:  # pragma: no cover - defensive
                    _LOGGER.warning("CGA4236 request failed for %s: %s", path, err)

            return self.parse_resources(resources)

        return self.parse_resources({})

    def _extract_modem_data(self, resources: dict[str, Any]) -> dict[str, Any]:
        """Get modem channel table payload from resources."""
        payload = resources.get(_MODEM_ENDPOINT)
        data = self._unwrap_api_data(payload)
        if data and "DSTbl" in data:
            return data

        for value in resources.values():
            data = self._unwrap_api_data(value)
            if data and "DSTbl" in data:
                return data

        return {}

    def _extract_system_data(self, resources: dict[str, Any]) -> dict[str, Any]:
        """Get system info payload from resources."""
        payload = resources.get(_SYSTEM_ENDPOINT)
        data = self._unwrap_api_data(payload)
        if data and "ModelName" in data:
            return data

        for value in resources.values():
            data = self._unwrap_api_data(value)
            if data and "ModelName" in data:
                return data

        return {}

    @staticmethod
    def _unwrap_api_data(payload: Any) -> dict[str, Any]:
        """Return the API `data` object when present, otherwise the dict itself."""
        if not isinstance(payload, dict):
            return {}

        data = payload.get("data")
        if isinstance(data, dict):
            return data

        return payload

    @staticmethod
    def _build_errors_by_index(error_rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        """Build lookup by table row index for corrected/uncorrectable counters."""
        errors_by_index: dict[int, dict[str, Any]] = {}

        for row in error_rows:
            row_index = extract_number(str(row.get("__id", "")))
            if row_index is not None:
                errors_by_index[row_index] = row

        return errors_by_index

    def _parse_downstream(self, data: dict[str, Any], errors_by_index: dict[int, dict[str, Any]]) -> list[dict]:
        """Parse SC-QAM and OFDM downstream channels."""
        channels: list[dict[str, Any]] = []

        # SC-QAM channels
        for row in data.get("DSTbl", []):
            row_index = extract_number(str(row.get("__id", "")))
            error_row = errors_by_index.get(row_index) if row_index is not None else None

            channels.append(
                {
                    "channel_id": str(row.get("ChannelID", "")).strip(),
                    "lock_status": str(row.get("LockStatus", "")).strip(),
                    "channel_type": str(row.get("ChannelType", "")).strip(),
                    "is_ofdm": False,
                    "modulation": self._normalize_modulation(str(row.get("Modulation", ""))),
                    "frequency": self._parse_frequency_hz(row.get("Frequency")),
                    "power": extract_float(str(row.get("PowerLevel", ""))),
                    "snr": extract_float(str(row.get("SNRLevel", ""))),
                    "octets": extract_number(str(row.get("Octets", ""))),
                    "corrected": self._parse_counter(error_row, row, "Correcteds"),
                    "uncorrected": self._parse_counter(error_row, row, "Uncorrectables"),
                }
            )

        # OFDM channels
        for row in data.get("exDSTbl", []):
            row_index = extract_number(str(row.get("ChannelIndex", "")))
            if row_index is None:
                row_index = extract_number(str(row.get("__id", "")))
            error_row = errors_by_index.get(row_index) if row_index is not None else None

            channels.append(
                {
                    "channel_id": str(row.get("ChannelID", "")).strip(),
                    "channel_index": row_index,
                    "lock_status": str(row.get("LockStatus", "")).strip(),
                    "channel_type": str(row.get("ChannelType", "")).strip(),
                    "is_ofdm": True,
                    "modulation": self._normalize_modulation(str(row.get("FFT", ""))),
                    "frequency": self._parse_frequency_hz(row.get("CentralFrequency") or row.get("PLCFrequency")),
                    "frequency_start": self._parse_frequency_hz(row.get("StartFrequency")),
                    "plc_frequency": self._parse_frequency_hz(row.get("PLCFrequency")),
                    "channel_width": self._parse_frequency_hz(row.get("BandWidth")),
                    "power": extract_float(str(row.get("PowerLevel", ""))),
                    "snr": extract_float(str(row.get("SNRLevel", ""))),
                    "profile": str(row.get("Profile", "")).strip() or None,
                    "corrected": self._parse_counter(error_row, row, "Correcteds"),
                    "uncorrected": self._parse_counter(error_row, row, "Uncorrectables"),
                }
            )

        return channels

    def _parse_upstream(self, data: dict[str, Any]) -> list[dict]:
        """Parse SC-QAM and OFDMA upstream channels."""
        channels: list[dict[str, Any]] = []

        # SC-QAM channels
        for row in data.get("USTbl", []):
            channels.append(
                {
                    "channel_id": str(row.get("ChannelID", "")).strip(),
                    "lock_status": str(row.get("LockStatus", "")).strip(),
                    "channel_type": str(row.get("ChannelType", "")).strip(),
                    "is_ofdm": False,
                    "modulation": self._normalize_modulation(str(row.get("Modulation", ""))),
                    "frequency": self._parse_frequency_hz(row.get("Frequency")),
                    "power": extract_float(str(row.get("PowerLevel", ""))),
                    "symbol_rate": extract_number(str(row.get("SymbolRate", ""))),
                }
            )

        # OFDMA channels
        for row in data.get("exUSTbl", []):
            channels.append(
                {
                    "channel_id": str(row.get("ChannelID", "")).strip(),
                    "channel_index": extract_number(str(row.get("ChannelIndex", ""))),
                    "lock_status": str(row.get("LockStatus", "")).strip(),
                    "channel_type": str(row.get("ChannelType", "")).strip(),
                    "is_ofdm": True,
                    "modulation": self._normalize_modulation(str(row.get("FFT", ""))),
                    "frequency": self._parse_frequency_hz(row.get("CentralFrequency") or row.get("PLCFrequency")),
                    "frequency_start": self._parse_frequency_hz(row.get("StartFrequency")),
                    "plc_frequency": self._parse_frequency_hz(row.get("PLCFrequency")),
                    "channel_width": self._parse_frequency_hz(row.get("BandWidth")),
                    "power": extract_float(str(row.get("PowerLevel", ""))),
                }
            )

        return channels

    def _parse_system_info(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse system info from `/api/v1/system/...` payload."""
        if not data:
            return {}

        info: dict[str, Any] = {
            "status": str(data.get("CMStatus", "")).strip() or None,
            "model_name": str(data.get("ModelName", "")).strip() or None,
            "manufacturer": str(data.get("Manufacturer", "")).strip() or None,
            "serial_number": str(data.get("SerialNumber", "")).strip() or None,
            "hardware_version": str(data.get("HardwareVersion", "")).strip() or None,
            "software_version": str(data.get("SoftwareVersion", "")).strip() or None,
            "firmware_name": str(data.get("FirmwareName", "")).strip() or None,
            "firmware_build_time": str(data.get("FirmwareBuildTime", "")).strip() or None,
            "bootloader_version": html.unescape(str(data.get("BootloaderVersion", "")).strip()) or None,
            "local_time": str(data.get("LocalTime", "")).strip() or None,
            "processor_speed_mhz": extract_number(str(data.get("ProcessorSpeed", ""))),
            "mem_total_kb": extract_number(str(data.get("MemTotal", ""))),
            "mem_free_kb": extract_number(str(data.get("MemFree", ""))),
        }

        uptime_seconds = extract_number(str(data.get("UpTime", "")))
        if uptime_seconds is not None:
            info["uptime_seconds"] = uptime_seconds
            info["system_uptime"] = self._format_uptime(uptime_seconds)

        # Remove None values to keep payload clean
        return {k: v for k, v in info.items() if v is not None}

    @staticmethod
    def _parse_counter(error_row: dict[str, Any] | None, fallback_row: dict[str, Any], field: str) -> int | None:
        """Parse counters from error table first, then fallback row."""
        if error_row and field in error_row:
            value = extract_number(str(error_row.get(field, "")))
            if value is not None:
                return value

        return extract_number(str(fallback_row.get(field, "")))

    @staticmethod
    def _parse_frequency_hz(value: Any) -> int | None:
        """Parse frequency values to Hz from strings like '146 MHz' or raw Hz numbers."""
        if value is None:
            return None

        if isinstance(value, int):
            if value < 10_000:
                return value * 1_000_000
            return value

        if isinstance(value, float):
            if value < 10_000:
                return int(round(value * 1_000_000))
            return int(round(value))

        text = str(value).strip()
        if not text:
            return None

        lower = text.lower()
        parsed = extract_float(text)
        if parsed is None:
            return None

        if "mhz" in lower or parsed < 10_000:
            return int(round(parsed * 1_000_000))

        return int(round(parsed))

    @staticmethod
    def _normalize_modulation(modulation: str) -> str:
        """Normalize modulation strings (e.g. `64-qam` -> `64QAM`)."""
        if not modulation:
            return ""

        parts = []
        for part in modulation.split("/"):
            normalized = part.strip().upper().replace("-", "").replace("_", "")
            if normalized:
                parts.append(normalized)

        return "/".join(parts)

    @staticmethod
    def _format_uptime(seconds: int) -> str:
        """Format uptime seconds to `Xd HH:MM:SS` or `HH:MM:SS`."""
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, secs = divmod(remainder, 60)

        if days > 0:
            return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
