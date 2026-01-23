"""Parser for Arris/CommScope S34 cable modem using HNAP protocol.

The S34 uses the same HNAP protocol as the S33, with one key difference:
- S34: Uses HMAC-SHA256 for authentication (configured in modem.yaml)
- S33: Uses HMAC-MD5 for authentication

The data format (caret-delimited, pipe-separated) and action names
(GetCustomer*) are identical between the two modems.

Known firmware quirk: The S34's web server sends malformed HTTP headers
containing debug timing data. This is handled by the centralized
_HNAPHeaderParsingFilter in json_builder.py.

Reference: https://github.com/solentlabs/cable_modem_monitor/pull/90
"""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.modem_config.adapter import (
    get_auth_adapter_for_parser,
)

_LOGGER = logging.getLogger(__name__)


class ArrisS34HnapParser(ModemParser):
    """Parser for Arris/CommScope S34 cable modem using HNAP/SOAP protocol."""

    def _get_hnap_hints(self) -> dict[str, str]:
        """Get HNAP hints from modem.yaml."""
        adapter = get_auth_adapter_for_parser(self.__class__.__name__)
        if adapter:
            hints = adapter.get_hnap_hints()
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
            _LOGGER.debug("S34: Parsing pre-fetched HNAP response data")
            return self._parse_hnap_response(hnap_response)

        _LOGGER.warning("S34: No HNAP response data in resources")
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
            "S34: Successfully parsed HNAP data (downstream: %d channels, upstream: %d channels)",
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
        """Parse downstream channels from HNAP JSON response.

        Format: "ChannelSelect^LockStatus^ChannelType^ChannelID^Frequency^PowerLevel^SNRLevel^Corrected^Uncorrected"
        Delimiter: ^ (caret) between fields, |+| between channels

        Note: S34 includes placeholder channels with channel_id=0 for "Not Locked"
        status. These are filtered out as they contain no useful data.
        """
        channels: list[dict] = []

        try:
            # S34 uses CustomerConn* keys (same as S33)
            downstream_response = hnap_data.get("GetCustomerStatusDownstreamChannelInfoResponse", {})
            channel_data = downstream_response.get("CustomerConnDownstreamChannel", "")

            if not channel_data:
                _LOGGER.warning(
                    "S34: No downstream channel data found. Response keys: %s, content: %s",
                    list(hnap_data.keys()),
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
                    _LOGGER.warning("S34: Invalid downstream channel entry: %s", entry)
                    continue

                try:
                    # Parse channel fields
                    # fields[0] = row index (display order only)
                    # fields[3] = DOCSIS Channel ID
                    channel_id = int(fields[3])

                    # Skip placeholder channels with channel_id=0 (S34-specific)
                    # These appear for "Not Locked" slots and contain no useful data
                    if channel_id == 0:
                        continue

                    lock_status = fields[1].strip()
                    modulation = fields[2].strip()

                    # Frequency - could be Hz or need conversion
                    # S34 HNAP returns frequencies already in Hz without suffix
                    # (e.g., "537000000" for 537 MHz)
                    freq_str = fields[4].strip()
                    if "Hz" in freq_str:
                        frequency = int(freq_str.replace(" Hz", "").replace("Hz", ""))
                    else:
                        freq_val = float(freq_str)
                        # If value > 1,000,000 it's already in Hz (e.g., 537000000 Hz)
                        # If value < 1000 it's likely MHz (e.g., 537 MHz)
                        if freq_val > 1_000_000:
                            frequency = int(freq_val)
                        else:
                            frequency = int(round(freq_val * 1_000_000))

                    # Power - strip units if present
                    power_str = fields[5].strip().replace(" dBmV", "").replace("dBmV", "")
                    power = float(power_str)

                    # SNR - strip units if present
                    snr_str = fields[6].strip().replace(" dB", "").replace("dB", "")
                    snr = float(snr_str)

                    corrected = int(fields[7])
                    uncorrected = int(fields[8])

                    # Derive channel_type from modulation string
                    # S34 returns "OFDM PLC" for OFDM channels, "QAM256" etc for SC-QAM
                    channel_type = "ofdm" if "ofdm" in modulation.lower() else "qam"

                    channel_info = {
                        "channel_id": channel_id,
                        "lock_status": lock_status,
                        "modulation": modulation,
                        "channel_type": channel_type,
                        "frequency": frequency,
                        "power": power,
                        "snr": snr,
                        "corrected": corrected,
                        "uncorrected": uncorrected,
                    }

                    channels.append(channel_info)

                except (ValueError, IndexError) as e:
                    _LOGGER.warning("S34: Error parsing downstream channel: %s - %s", entry, e)
                    continue

        except Exception as e:
            _LOGGER.error("S34: Error parsing downstream channels: %s", e)

        return channels

    def _parse_upstream_from_hnap(self, hnap_data: dict) -> list[dict]:
        """Parse upstream channels from HNAP JSON response.

        Format: "ChannelSelect^LockStatus^ChannelType^ChannelID^SymbolRate/Width^Frequency^PowerLevel"
        Delimiter: ^ (caret) between fields, |+| between channels

        Note: S34 includes placeholder channels with channel_id=0 for "Not Locked"
        status. These are filtered out as they contain no useful data.
        """
        channels: list[dict] = []

        try:
            # S34 uses CustomerConn* keys
            upstream_response = hnap_data.get("GetCustomerStatusUpstreamChannelInfoResponse", {})
            channel_data = upstream_response.get("CustomerConnUpstreamChannel", "")

            if not channel_data:
                _LOGGER.warning(
                    "S34: No upstream channel data found. Response keys: %s, content: %s",
                    list(hnap_data.keys()),
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
                    _LOGGER.warning("S34: Invalid upstream channel entry: %s", entry)
                    continue

                try:
                    # Parse channel fields
                    channel_id = int(fields[3])

                    # Skip placeholder channels with channel_id=0 (S34-specific)
                    # These appear for "Not Locked" slots and contain no useful data
                    if channel_id == 0:
                        continue

                    lock_status = fields[1].strip()
                    modulation = fields[2].strip()
                    symbol_rate = fields[4].strip()  # Keep as string, may have units

                    # Frequency - could be Hz or need conversion
                    # S34 HNAP returns frequencies already in Hz without suffix
                    freq_str = fields[5].strip()
                    if "Hz" in freq_str:
                        frequency = int(freq_str.replace(" Hz", "").replace("Hz", ""))
                    else:
                        freq_val = float(freq_str)
                        # If value > 1,000,000 it's already in Hz (e.g., 22800000 Hz)
                        # If value < 1000 it's likely MHz (e.g., 22.8 MHz)
                        if freq_val > 1_000_000:
                            frequency = int(freq_val)
                        else:
                            frequency = int(round(freq_val * 1_000_000))

                    # Power - strip units if present
                    power_str = fields[6].strip().replace(" dBmV", "").replace("dBmV", "")
                    power = float(power_str)

                    # Derive channel_type from modulation string
                    # S34 returns "OFDMA" for OFDMA channels, "SC-QAM"/"ATDMA" etc for SC-QAM
                    channel_type = "ofdma" if "ofdma" in modulation.lower() else "atdma"

                    channel_info = {
                        "channel_id": channel_id,
                        "lock_status": lock_status,
                        "modulation": modulation,
                        "channel_type": channel_type,
                        "symbol_rate": symbol_rate,
                        "frequency": frequency,
                        "power": power,
                    }

                    channels.append(channel_info)

                except (ValueError, IndexError) as e:
                    _LOGGER.warning("S34: Error parsing upstream channel: %s - %s", entry, e)
                    continue

        except Exception as e:
            _LOGGER.error("S34: Error parsing upstream channels: %s", e)

        return channels

    def _parse_system_info_from_hnap(self, hnap_data: dict) -> dict:
        """Parse system info from HNAP JSON response."""
        system_info: dict[str, str] = {}

        try:
            self._extract_connection_info(hnap_data, system_info)
            self._extract_startup_info(hnap_data, system_info)
            self._extract_device_status(hnap_data, system_info)
        except Exception as e:
            _LOGGER.error("S34: Error parsing system info: %s", e)

        return system_info

    def _extract_connection_info(self, hnap_data: dict, system_info: dict) -> None:
        """Extract connection info fields from HNAP data."""
        # S34 uses CustomerConn* keys
        conn_info = hnap_data.get("GetCustomerStatusConnectionInfoResponse", {})
        if not conn_info:
            return

        # Note: CustomerCurSystemTime is the current clock time, NOT uptime.
        # The Arris UI displays this in an element called "SystemUpTime" which is misleading.
        # We intentionally do NOT map it to system_uptime since it's not a duration.
        self._set_if_present(conn_info, "CustomerConnNetworkAccess", system_info, "network_access")
        self._set_if_present(conn_info, "StatusSoftwareModelName", system_info, "model_name")

    def _extract_startup_info(self, hnap_data: dict, system_info: dict) -> None:
        """Extract startup sequence info fields from HNAP data."""
        startup_info = hnap_data.get("GetCustomerStatusStartupSequenceResponse", {})
        if not startup_info:
            return

        self._set_if_present(startup_info, "CustomerConnDSFreq", system_info, "downstream_frequency")
        self._set_if_present(startup_info, "CustomerConnConnectivityStatus", system_info, "connectivity_status")
        self._set_if_present(startup_info, "CustomerConnBootStatus", system_info, "boot_status")
        self._set_if_present(startup_info, "CustomerConnSecurityStatus", system_info, "security_status")

    def _extract_device_status(self, hnap_data: dict, system_info: dict) -> None:
        """Extract device status fields from HNAP data (firmware version, etc.)."""
        device_status = hnap_data.get("GetArrisDeviceStatusResponse", {})
        if not device_status:
            return

        # FirmwareVersion -> software_version
        self._set_if_present(device_status, "FirmwareVersion", system_info, "software_version")
        self._set_if_present(device_status, "InternetConnection", system_info, "internet_connection")

    def _set_if_present(self, source: dict, source_key: str, target: dict, target_key: str) -> None:
        """Set target[key] if source[source_key] exists and is non-empty."""
        value = source.get(source_key, "")
        if value:
            target[target_key] = value
