"""Parser for Arris/CommScope G54 Gateway using LuCI JSON API.

The G54 is a DOCSIS 3.1 gateway (modem + router combo) that uses OpenWrt's
LuCI web interface instead of the traditional Arris Surfboard HTML pages.

Authentication: Form-based login sets a 'sysauth' session cookie.
Data endpoint: GET /cgi-bin/luci/admin/gateway/wan_status?status=1

Reference: https://github.com/solentlabs/cable_modem_monitor/issues/72
"""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class ArrisG54Parser(ModemParser):
    """Parser for Arris/CommScope G54 Gateway using LuCI JSON API."""

    # Auth handled by AuthDiscovery (v3.12.0+) - form hints now in modem.yaml auth.form
    # URL patterns now in modem.yaml pages config

    # login() not needed - uses base class default (AuthDiscovery handles auth)

    def parse_resources(self, resources: dict[str, Any]) -> dict:
        """Parse all data from pre-fetched resources."""
        downstream_channels: list[dict] = []
        upstream_channels: list[dict] = []
        system_info: dict[str, Any] = {}

        # Get wan_status JSON data from resources
        data = resources.get("/cgi-bin/luci/admin/gateway/wan_status")
        if data is None:
            # Fallback: try to find any dict in resources (JSON data)
            for value in resources.values():
                if isinstance(value, dict) and "docsis" in value:
                    data = value
                    break

        if data is None:
            _LOGGER.warning("G54 parser: No wan_status data found in resources")
            return {
                "downstream": downstream_channels,
                "upstream": upstream_channels,
                "system_info": system_info,
            }

        # Parse system info
        system_info = self._parse_system_info(data)

        # Parse channels
        docsis = data.get("docsis", {})
        downstream_channels = self._parse_downstream(docsis)
        upstream_channels = self._parse_upstream(docsis)

        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the G54 gateway (legacy interface)."""
        if not session or not base_url:
            _LOGGER.warning("G54 parser requires session and base_url")
            return {
                "downstream": [],
                "upstream": [],
                "system_info": {},
            }

        # Fetch wan_status JSON API
        try:
            response = session.get(
                f"{base_url}/cgi-bin/luci/admin/gateway/wan_status",
                params={"status": "1"},
                timeout=30,
            )
            if response.status_code != 200:
                _LOGGER.error("G54 wan_status request failed: %s", response.status_code)
                return {
                    "downstream": [],
                    "upstream": [],
                    "system_info": {},
                }

            data = response.json()

        except Exception as e:
            _LOGGER.error("G54 API request failed: %s", e)
            return {
                "downstream": [],
                "upstream": [],
                "system_info": {},
            }

        # Delegate to parse_resources
        return self.parse_resources({"/cgi-bin/luci/admin/gateway/wan_status": data})

    def _parse_system_info(self, data: dict) -> dict[str, Any]:
        """Parse system information from wan_status response."""
        info: dict[str, Any] = {}

        # Uptime in seconds
        uptime_seconds = data.get("uptime")
        if uptime_seconds is not None:
            info["uptime_seconds"] = uptime_seconds
            info["system_uptime"] = self._format_uptime(uptime_seconds)

        # Release/version info
        release = data.get("release", {})
        if release:
            info["software_version"] = release.get("version", "")
            info["model"] = release.get("model", "G54")
            info["manufacturer"] = release.get("manufacturer", "CommScope")
            info["docsis_mode"] = release.get("docsis_operating_mode", "3.1")
            info["hardware_version"] = release.get("hwversion", "")

        # Hostname
        if data.get("hostname"):
            info["hostname"] = data["hostname"]

        return info

    def _format_uptime(self, seconds: int) -> str:
        """Format uptime seconds to human readable string."""
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, secs = divmod(remainder, 60)

        if days > 0:
            return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _parse_downstream(self, docsis: dict) -> list[dict]:
        """Parse downstream channels (SC-QAM and OFDM)."""
        channels: list[dict] = []

        # SC-QAM downstream channels
        ds_channels = docsis.get("dschannel", {}).get("dschannel", [])
        for ch in ds_channels:
            # Skip unlocked or empty channels
            if ch.get("lockStatus") != "Locked":
                continue
            if not ch.get("frequency"):
                continue

            freq_hz = self._parse_frequency(ch.get("frequency", ""))
            if freq_hz == 0:
                continue

            qam_channel: dict[str, Any] = {
                "channel_id": str(ch.get("channelID", "")),
                "lock_status": ch.get("lockStatus", ""),
                "modulation": ch.get("modulation", ""),
                "frequency": freq_hz,
                "power": self._parse_float(ch.get("powerLevel")),
                "snr": self._parse_float(ch.get("SNRLevel")),
                "corrected": ch.get("correctableCodewords", 0),
                "uncorrected": ch.get("uncorrectableCodewords", 0),
                "is_ofdm": False,
            }
            channels.append(qam_channel)

        # OFDM downstream channels
        ofdm_channels = docsis.get("ofdmchannel", {}).get("ofdmchannel", [])
        for ch in ofdm_channels:
            # Only include active OFDM channels
            if ch.get("status") != 1:
                continue

            # OFDM uses frequency range, use center frequency for display
            first_freq = self._parse_frequency(ch.get("firstFrequency", ""))
            last_freq = self._parse_frequency(ch.get("lastFrequency", ""))
            center_freq = (first_freq + last_freq) // 2 if first_freq and last_freq else 0

            ofdm_channel: dict[str, Any] = {
                "channel_id": f"OFDM-{ch.get('ofdmID', '')}",
                "lock_status": "Locked" if ch.get("PLCLocked") == "YES" else "Not Locked",
                "modulation": ch.get("modulation", ""),
                "frequency": center_freq,
                "frequency_start": first_freq,
                "frequency_end": last_freq,
                "power": self._parse_float(ch.get("powerLevel")),
                "snr": self._parse_float(ch.get("DataSubcarriersAverageRxMER")),
                "active_subcarriers": ch.get("activeSubcarrierNumber", ""),
                "channel_width": ch.get("channelBandwidth", ""),
                "is_ofdm": True,
            }
            channels.append(ofdm_channel)

        return channels

    def _parse_upstream(self, docsis: dict) -> list[dict]:
        """Parse upstream channels (SC-QAM and OFDMA)."""
        channels: list[dict] = []

        # SC-QAM upstream channels
        us_channels = docsis.get("uschannel", {}).get("uschannel", [])
        for ch in us_channels:
            # Skip unlocked or unsupported channels
            if ch.get("lockStatus") != "Locked":
                continue
            if ch.get("channelType") == "UNSUPPORTED":
                continue

            freq_hz = self._parse_frequency(ch.get("frequency", ""))
            if freq_hz == 0:
                continue

            qam_channel: dict[str, Any] = {
                "channel_id": str(ch.get("channelID", "")),
                "lock_status": ch.get("lockStatus", ""),
                "modulation": ch.get("modulation", ""),
                "channel_type": ch.get("channelType", ""),
                "frequency": freq_hz,
                "power": self._parse_float(ch.get("powerLevel")),
                "symbol_rate": ch.get("symbolRate", ""),
                "is_ofdm": False,
            }
            channels.append(qam_channel)

        # OFDMA upstream channels
        ofdma_channels = docsis.get("ofdmachannel", {}).get("ofdmachannel", [])
        for ch in ofdma_channels:
            # Only include active OFDMA channels
            if ch.get("status") != 1:
                continue

            # OFDMA uses frequency range in MHz
            first_freq_mhz = self._parse_float(ch.get("firstFrequency"))
            last_freq_mhz = self._parse_float(ch.get("lastFrequency"))
            first_freq = int(first_freq_mhz * 1_000_000) if first_freq_mhz else 0
            last_freq = int(last_freq_mhz * 1_000_000) if last_freq_mhz else 0
            center_freq = (first_freq + last_freq) // 2 if first_freq and last_freq else 0

            ofdma_channel: dict[str, Any] = {
                "channel_id": f"OFDMA-{ch.get('ofdmaID', '')}",
                "lock_status": "Active" if ch.get("power") == "ON" else "Inactive",
                "modulation": ch.get("modulation", ""),
                "frequency": center_freq,
                "frequency_start": first_freq,
                "frequency_end": last_freq,
                "power": self._parse_float(ch.get("reportPower")),
                "active_subcarriers": ch.get("activeSubcarrierNumber", 0),
                "fft_size": ch.get("fftSize", ""),
                "is_ofdm": True,
            }
            channels.append(ofdma_channel)

        return channels

    def _parse_frequency(self, value: Any) -> int:
        """Parse frequency value to Hz."""
        if not value:
            return 0
        try:
            # Handle string values that may have whitespace
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    return 0
            return int(float(value))
        except (ValueError, TypeError):
            return 0

    def _parse_float(self, value: Any) -> float:
        """Parse float value, handling strings and edge cases."""
        if value is None:
            return 0.0
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            value = value.strip()
            if not value or value == "-inf":
                return 0.0
            try:
                return float(value)
            except ValueError:
                return 0.0
        return 0.0
