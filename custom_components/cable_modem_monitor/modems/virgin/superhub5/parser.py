# =============================================================================
# AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
#
# Source: modems/virgin/superhub5/parser.py
# This file is synced from modems/ during build. Edit the source file, then run:
#     make sync
# =============================================================================

"""Parser for Virgin Media Hub 5 using REST API.

The Hub 5 is a DOCSIS 3.1 gateway that exposes a REST API at /rest/v1/
with unauthenticated JSON endpoints for modem status.

Naming: Virgin Media has used both "Super Hub 5" and "Hub 5" in their marketing.
We use "superhub5" in filenames/classes for stability, but display as "Virgin Hub 5"
to match their current branding. The models list includes both variations for detection.

Authentication: None required
Data endpoints:
  - GET /rest/v1/cablemodem/downstream
  - GET /rest/v1/cablemodem/upstream
  - GET /rest/v1/cablemodem/state_

Reference: https://github.com/solentlabs/cable_modem_monitor/issues/82
"""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class VirginSuperHub5Parser(ModemParser):
    """Parser for Virgin Media Hub 5 using REST API.

    OEM: Sagemcom F3896LG-VMB
    Chipset: Broadcom 3390S (per ISPreview)

    Note: User's bootFilename shows "vmdg660" - linkage to F3896LG-VMB inferred.
    """

    # Auth handled by AuthDiscovery (v3.12.0+) - no auth_config needed
    # URL patterns now in modem.yaml pages config

    # login() not needed - uses base class default (AuthDiscovery handles auth)

    def parse_resources(self, resources: dict[str, Any]) -> dict:
        """Parse all data from pre-fetched resources.

        Expected resources (JSON dict for each endpoint):
            "/rest/v1/cablemodem/state_": dict with system state
            "/rest/v1/cablemodem/downstream": dict with downstream channels
            "/rest/v1/cablemodem/upstream": dict with upstream channels
        """
        # Get pre-fetched JSON data
        state_data = resources.get("/rest/v1/cablemodem/state_", {})
        downstream_data = resources.get("/rest/v1/cablemodem/downstream", {})
        upstream_data = resources.get("/rest/v1/cablemodem/upstream", {})

        # Parse system info from state
        system_info = self._parse_state_data(state_data)

        # Parse downstream channels
        downstream_channels = self._parse_downstream_data(downstream_data)

        # Parse upstream channels
        upstream_channels = self._parse_upstream_data(upstream_data)

        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem (legacy interface).

        When session and base_url are provided, fetches JSON from REST API
        endpoints and delegates to parse_resources().
        """
        if session and base_url:
            # Legacy path: fetch JSON resources and delegate to parse_resources()
            resources: dict[str, Any] = {}

            # Fetch state
            try:
                response = session.get(f"{base_url}/rest/v1/cablemodem/state_", timeout=30)
                if response.status_code == 200:
                    resources["/rest/v1/cablemodem/state_"] = response.json()
                else:
                    _LOGGER.error("SuperHub 5 state request failed: %s", response.status_code)
            except Exception as e:
                _LOGGER.error("SuperHub 5 state request failed: %s", e)

            # Fetch downstream
            try:
                response = session.get(f"{base_url}/rest/v1/cablemodem/downstream", timeout=30)
                if response.status_code == 200:
                    resources["/rest/v1/cablemodem/downstream"] = response.json()
                else:
                    _LOGGER.error("SuperHub 5 downstream request failed: %s", response.status_code)
            except Exception as e:
                _LOGGER.error("SuperHub 5 downstream request failed: %s", e)

            # Fetch upstream
            try:
                response = session.get(f"{base_url}/rest/v1/cablemodem/upstream", timeout=30)
                if response.status_code == 200:
                    resources["/rest/v1/cablemodem/upstream"] = response.json()
                else:
                    _LOGGER.error("SuperHub 5 upstream request failed: %s", response.status_code)
            except Exception as e:
                _LOGGER.error("SuperHub 5 upstream request failed: %s", e)

            return self.parse_resources(resources)

        # No session - parse with empty resources
        _LOGGER.warning("SuperHub 5 parser requires session and base_url")
        return self.parse_resources({})

    def _parse_state_data(self, data: dict) -> dict[str, Any]:
        """Parse system state from pre-fetched JSON."""
        info: dict[str, Any] = {}
        cm = data.get("cablemodem", {})

        # Uptime in seconds
        uptime_seconds = cm.get("upTime")
        if uptime_seconds is not None:
            info["uptime_seconds"] = uptime_seconds
            info["system_uptime"] = self._format_uptime(uptime_seconds)

        # DOCSIS version
        if cm.get("docsisVersion"):
            info["docsis_version"] = cm["docsisVersion"]

        # Status
        if cm.get("status"):
            info["status"] = cm["status"]

        # Note: REST API doesn't appear to return a model name field.
        # bootFilename contains "vmdg660" (Virgin Media DOCSIS Gateway 660)
        # which is Virgin's internal product code.
        # We don't set model_name here - falls back to parser name ("Virgin Media Hub 5")

        return info

    def _parse_downstream_data(self, data: dict) -> list[dict]:
        """Parse downstream channels from pre-fetched JSON."""
        channels: list[dict] = []
        raw_channels = data.get("downstream", {}).get("channels", [])

        for ch in raw_channels:
            if not ch.get("lockStatus"):
                continue

            channel_type = ch.get("channelType", "").lower()
            is_ofdm = channel_type == "ofdm"

            channel: dict[str, Any] = {
                "channel_id": str(ch.get("channelId", "")),
                "lock_status": "Locked" if ch.get("lockStatus") else "Not Locked",
                "modulation": self._normalize_modulation(ch.get("modulation", "")),
                "frequency": ch.get("frequency", 0),
                "power": self._parse_float(ch.get("power")),
                "snr": self._parse_float(ch.get("snr") or ch.get("rxMer")),
                "corrected": ch.get("correctedErrors", 0),
                "uncorrected": ch.get("uncorrectedErrors", 0),
                "is_ofdm": is_ofdm,
                "channel_type": channel_type,
            }

            # OFDM-specific fields
            if is_ofdm:
                channel["channel_width"] = ch.get("channelWidth", 0)
                channel["fft_type"] = ch.get("fftType", "")
                channel["active_subcarriers"] = ch.get("numberOfActiveSubCarriers", 0)

            channels.append(channel)

        return channels

    def _parse_upstream_data(self, data: dict) -> list[dict]:
        """Parse upstream channels from pre-fetched JSON."""
        channels: list[dict] = []
        raw_channels = data.get("upstream", {}).get("channels", [])

        for ch in raw_channels:
            if not ch.get("lockStatus"):
                continue

            channel_type = ch.get("channelType", "").lower()
            is_ofdm = channel_type == "ofdma"

            channel: dict[str, Any] = {
                "channel_id": str(ch.get("channelId", "")),
                "lock_status": "Locked" if ch.get("lockStatus") else "Not Locked",
                "modulation": self._normalize_modulation(ch.get("modulation", "")),
                "frequency": ch.get("frequency", 0),
                "power": self._parse_float(ch.get("power")),
                "symbol_rate": ch.get("symbolRate", 0),
                "is_ofdm": is_ofdm,
                "channel_type": channel_type,
            }

            # OFDMA-specific fields
            if is_ofdm:
                channel["channel_width"] = ch.get("channelWidth", 0)
                channel["fft_type"] = ch.get("fftType", "")
                channel["active_subcarriers"] = ch.get("numberOfActiveSubCarriers", 0)

            channels.append(channel)

        return channels

    def _format_uptime(self, seconds: int) -> str:
        """Format uptime seconds to human readable string."""
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, secs = divmod(remainder, 60)

        if days > 0:
            return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _parse_float(self, value: Any) -> float:
        """Parse float value, handling various input types."""
        if value is None:
            return 0.0
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return 0.0
            try:
                return float(value)
            except ValueError:
                return 0.0
        return 0.0

    def _normalize_modulation(self, mod: str) -> str:
        """Normalize modulation string to standard format."""
        if not mod:
            return ""
        # Convert from API format (e.g., "qam_256") to display format (e.g., "QAM256")
        mod_upper = mod.upper().replace("_", "")
        return mod_upper
