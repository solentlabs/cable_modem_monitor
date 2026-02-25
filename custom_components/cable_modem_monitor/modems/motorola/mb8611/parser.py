# =============================================================================
# AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
#
# Source: modems/motorola/mb8611/parser.py
# This file is synced from modems/ during build. Edit the source file, then run:
#     make sync
# =============================================================================

"""Parser for Motorola MB8611 cable modem using HNAP protocol."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.modem_config.adapter import (
    get_auth_adapter_for_parser,
)

_LOGGER = logging.getLogger(__name__)


class MotorolaMB8611HnapParser(ModemParser):
    """Parser for Motorola MB8611 cable modem using HNAP/SOAP protocol."""

    def _get_hnap_hints(self) -> dict[str, str | dict]:
        """Get HNAP hints from modem.yaml."""
        adapter = get_auth_adapter_for_parser(self.__class__.__name__)
        if adapter:
            hints: dict[str, str | dict] | None = adapter.get_hnap_hints()  # type: ignore[assignment]
            if hints:
                return hints
        raise ValueError(f"No HNAP hints found in modem.yaml for {self.__class__.__name__}")

    def parse_resources(self, resources: dict[str, Any]) -> dict:
        """Parse all data from pre-fetched resources.

        For HNAP parsers, resources contains:
        - "hnap_response": Pre-fetched HNAP response data from HNAPLoader
        - "/": BeautifulSoup object (for fallback compatibility)

        Args:
            resources: Dictionary of pre-fetched resources

        Returns:
            Dict with downstream, upstream, and system_info
        """
        # Get pre-fetched HNAP response data (provided by HNAPLoader)
        hnap_response = resources.get("hnap_response", {})

        if hnap_response:
            _LOGGER.debug("MB8611: Parsing pre-fetched HNAP response data")
            return self._parse_hnap_response(hnap_response)

        _LOGGER.warning("MB8611: No HNAP response data in resources")
        return {"downstream": [], "upstream": [], "system_info": {}}

    def _parse_hnap_response(self, hnap_data: dict) -> dict:
        """Parse pre-fetched HNAP response data.

        Args:
            hnap_data: Dictionary containing HNAP response data

        Returns:
            Dict with downstream, upstream, and system_info
        """
        # Extract nested response if present
        if "GetMultipleHNAPsResponse" in hnap_data:
            hnap_data = hnap_data["GetMultipleHNAPsResponse"]

        # Parse channels and system info
        downstream = self._parse_downstream_from_hnap(hnap_data)
        upstream = self._parse_upstream_from_hnap(hnap_data)
        system_info = self._parse_system_info_from_hnap(hnap_data)

        _LOGGER.info(
            "MB8611: Successfully parsed HNAP data (downstream: %d channels, upstream: %d channels)",
            len(downstream),
            len(upstream),
        )

        return {
            "downstream": downstream,
            "upstream": upstream,
            "system_info": system_info,
        }

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse data from BeautifulSoup or delegate to parse_resources().

        This method exists for backwards compatibility. New code should use
        parse_resources() which receives pre-fetched HNAP response data via HNAPLoader.

        Note: session and base_url parameters are deprecated. HNAP data fetching
        is now handled by HNAPLoader, and parsers only parse pre-fetched data.

        Args:
            soup: BeautifulSoup object (unused for HNAP parsers)
            session: Deprecated - network calls moved to HNAPLoader
            base_url: Deprecated - network calls moved to HNAPLoader

        Returns:
            Dict with downstream, upstream, and system_info
        """
        # Delegate to parse_resources (HNAP parsers need hnap_response, not soup)
        return self.parse_resources({"/": soup})

    def _parse_downstream_from_hnap(self, hnap_data: dict) -> list[dict]:
        """
        Parse downstream channels from HNAP JSON response.

        Format: "ID^Status^Mod^ChID^Freq^Power^SNR^Corr^Uncorr^|+|..."
        Example: "1^Locked^QAM256^20^543.0^ 1.4^45.1^41^0^"
        """
        channels: list[dict] = []

        try:
            downstream_response = hnap_data.get("GetMotoStatusDownstreamChannelInfoResponse", {})
            channel_data = downstream_response.get("MotoConnDownstreamChannel", "")

            if not channel_data:
                # Enhanced logging to help diagnose the issue
                _LOGGER.warning(
                    "MB8611: No downstream channel data found. "
                    "Response keys: %s, downstream_response type: %s, content: %s",
                    list(hnap_data.keys()),
                    type(downstream_response).__name__,
                    str(downstream_response)[:500] if downstream_response else "empty",
                )
                return channels

            # Split by |+| delimiter
            channel_entries = channel_data.split("|+|")

            for entry in channel_entries:
                if not entry.strip():
                    continue

                # Split by ^ delimiter
                fields = entry.split("^")

                if len(fields) < 9:
                    _LOGGER.warning("MB8611: Invalid downstream channel entry: %s", entry)
                    continue

                try:
                    # Parse channel fields
                    # fields[0] = row index (display order only, not meaningful)
                    # fields[3] = DOCSIS Channel ID (what technicians reference)
                    channel_id = int(fields[3])  # DOCSIS Channel ID
                    lock_status = fields[1].strip()
                    modulation = fields[2].strip()
                    frequency = int(round(float(fields[4].strip()) * 1_000_000))  # MHz to Hz
                    power = float(fields[5].strip())
                    snr = float(fields[6].strip())
                    corrected = int(fields[7])
                    uncorrected = int(fields[8])

                    # Derive channel_type from modulation string
                    # MB8611 returns "OFDM" for OFDM channels, "QAM256" etc for SC-QAM
                    channel_type = "ofdm" if "ofdm" in modulation.lower() else "qam"

                    channel_info = {
                        "channel_id": channel_id,
                        "lock_status": lock_status,
                        "modulation": modulation,
                        "channel_type": channel_type,
                        "frequency": int(frequency),
                        "power": power,
                        "snr": snr,
                        "corrected": corrected,
                        "uncorrected": uncorrected,
                    }

                    channels.append(channel_info)

                except (ValueError, IndexError) as e:
                    _LOGGER.warning("MB8611: Error parsing downstream channel: %s - %s", entry, e)
                    continue

        except Exception as e:
            _LOGGER.error("MB8611: Error parsing downstream channels: %s", e)

        return channels

    def _parse_upstream_from_hnap(self, hnap_data: dict) -> list[dict]:
        """
        Parse upstream channels from HNAP JSON response.

        Format: "ID^Status^Mod^ChID^SymbolRate^Freq^Power^|+|..."
        Example: "1^Locked^SC-QAM^17^5120^16.4^44.3^"
        """
        channels: list[dict] = []

        try:
            upstream_response = hnap_data.get("GetMotoStatusUpstreamChannelInfoResponse", {})
            channel_data = upstream_response.get("MotoConnUpstreamChannel", "")

            if not channel_data:
                # Enhanced logging to help diagnose the issue
                _LOGGER.warning(
                    "MB8611: No upstream channel data found. "
                    "Response keys: %s, upstream_response type: %s, content: %s",
                    list(hnap_data.keys()),
                    type(upstream_response).__name__,
                    str(upstream_response)[:500] if upstream_response else "empty",
                )
                return channels

            # Split by |+| delimiter
            channel_entries = channel_data.split("|+|")

            for entry in channel_entries:
                if not entry.strip():
                    continue

                # Split by ^ delimiter
                fields = entry.split("^")

                if len(fields) < 7:
                    _LOGGER.warning("MB8611: Invalid upstream channel entry: %s", entry)
                    continue

                try:
                    # Parse channel fields
                    # fields[0] = row index (display order only, not meaningful)
                    # fields[3] = DOCSIS Channel ID (what technicians reference)
                    channel_id = int(fields[3])  # DOCSIS Channel ID
                    lock_status = fields[1].strip()
                    modulation = fields[2].strip()
                    symbol_rate = int(fields[4])
                    frequency = int(round(float(fields[5].strip()) * 1_000_000))  # MHz to Hz
                    power = float(fields[6].strip())

                    # Derive channel_type from modulation string
                    # MB8611 returns "OFDMA" for OFDMA channels, "ATDMA"/etc for SC-QAM
                    channel_type = "ofdma" if "ofdma" in modulation.lower() else "atdma"

                    channel_info = {
                        "channel_id": channel_id,
                        "lock_status": lock_status,
                        "modulation": modulation,
                        "channel_type": channel_type,
                        "symbol_rate": symbol_rate,
                        "frequency": int(frequency),
                        "power": power,
                    }

                    channels.append(channel_info)

                except (ValueError, IndexError) as e:
                    _LOGGER.warning("MB8611: Error parsing upstream channel: %s - %s", entry, e)
                    continue

        except Exception as e:
            _LOGGER.error("MB8611: Error parsing upstream channels: %s", e)

        return channels

    def _parse_system_info_from_hnap(self, hnap_data: dict) -> dict:
        """Parse system info from HNAP JSON response."""
        system_info: dict[str, str] = {}

        try:
            self._extract_connection_info(hnap_data, system_info)
            self._extract_startup_info(hnap_data, system_info)
            self._extract_software_info(hnap_data, system_info)
        except Exception as e:
            _LOGGER.error("MB8611: Error parsing system info: %s", e)

        return system_info

    def _extract_connection_info(self, hnap_data: dict, system_info: dict) -> None:
        """Extract connection info fields from HNAP data."""
        conn_info = hnap_data.get("GetMotoStatusConnectionInfoResponse", {})
        if not conn_info:
            return

        self._set_if_present(conn_info, "MotoConnSystemUpTime", system_info, "system_uptime")
        self._set_if_present(conn_info, "MotoConnNetworkAccess", system_info, "network_access")

    def _extract_startup_info(self, hnap_data: dict, system_info: dict) -> None:
        """Extract startup sequence info fields from HNAP data."""
        startup_info = hnap_data.get("GetMotoStatusStartupSequenceResponse", {})
        if not startup_info:
            return

        self._set_if_present(startup_info, "MotoConnDSFreq", system_info, "downstream_frequency")
        self._set_if_present(startup_info, "MotoConnConnectivityStatus", system_info, "connectivity_status")
        self._set_if_present(startup_info, "MotoConnBootStatus", system_info, "boot_status")
        self._set_if_present(startup_info, "MotoConnSecurityStatus", system_info, "security_status")
        self._set_if_present(startup_info, "MotoConnSecurityComment", system_info, "security_comment")

    def _extract_software_info(self, hnap_data: dict, system_info: dict) -> None:
        """Extract software/firmware version info from HNAP data."""
        software_info = hnap_data.get("GetMotoStatusSoftwareResponse", {})
        if not software_info:
            return

        # StatusSoftwareHdVer contains the hardware version (e.g., "7.0")
        self._set_if_present(software_info, "StatusSoftwareHdVer", system_info, "hardware_version")
        # StatusSoftwareSfVer contains the firmware version (e.g., "8611-19.2.18")
        self._set_if_present(software_info, "StatusSoftwareSfVer", system_info, "software_version")
        self._set_if_present(software_info, "StatusSoftwareSpecVer", system_info, "docsis_version")
        self._set_if_present(software_info, "StatusSoftwareSerialNum", system_info, "serial_number")

    def _set_if_present(self, source: dict, source_key: str, target: dict, target_key: str) -> None:
        """Set target[key] if source[source_key] exists and is non-empty."""
        value = source.get(source_key, "")
        if value:
            target[target_key] = value
