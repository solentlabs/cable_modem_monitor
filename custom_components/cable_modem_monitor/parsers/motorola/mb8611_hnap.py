"""Parser for Motorola MB8611 cable modem using HNAP protocol."""

from __future__ import annotations

import json
import logging

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import HNAPAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType
from custom_components.cable_modem_monitor.core.hnap_builder import HNAPRequestBuilder

from ..base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class MotorolaMB8611HnapParser(ModemParser):
    """Parser for Motorola MB8611 cable modem using HNAP/SOAP protocol."""

    name = "Motorola MB8611 (HNAP)"
    manufacturer = "Motorola"
    models = ["MB8611", "MB8612"]
    priority = 101  ***REMOVED*** Higher priority for the API-based method

    ***REMOVED*** HNAP authentication configuration
    auth_config = HNAPAuthConfig(
        strategy=AuthStrategyType.HNAP_SESSION,
        login_url="/Login.html",
        hnap_endpoint="/HNAP1/",
        session_timeout_indicator="UN-AUTH",
        soap_action_namespace="http://purenetworks.com/HNAP1/",
    )

    url_patterns = [
        {"path": "/HNAP1/", "auth_method": "hnap", "auth_required": True},
        {"path": "/MotoStatusConnection.html", "auth_method": "hnap", "auth_required": True},
    ]

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Motorola MB8611 modem."""
        return (
            "MB8611" in html
            or "MB 8611" in html
            or "2251-MB8611" in html
            or (("HNAP" in html or "purenetworks.com/HNAP1" in html) and "Motorola" in html)
        )

    def login(self, session, base_url, username, password) -> tuple[bool, str | None]:
        """
        Log in using HNAP authentication (backward compatibility).

        Note: This method is maintained for backward compatibility.
        New code should use auth_config with AuthFactory instead.
        """
        from custom_components.cable_modem_monitor.core.authentication import AuthFactory

        auth_strategy = AuthFactory.get_strategy(self.auth_config.strategy)
        return auth_strategy.login(session, base_url, username, password, self.auth_config)

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """
        Parse data using HNAP SOAP calls.

        Args:
            soup: BeautifulSoup object (may not be used for HNAP modems)
            session: requests.Session with authenticated session
            base_url: Modem base URL

        Returns:
            Dict with downstream, upstream, and system_info
        """
        if not session or not base_url:
            raise ValueError("MB8611 requires session and base_url for HNAP calls")

        ***REMOVED*** Build HNAP request builder
        builder = HNAPRequestBuilder(
            endpoint=self.auth_config.hnap_endpoint, namespace=self.auth_config.soap_action_namespace
        )

        try:
            ***REMOVED*** Make batched HNAP request for all data
            soap_actions = [
                "GetMotoStatusStartupSequence",
                "GetMotoStatusConnectionInfo",
                "GetMotoStatusDownstreamChannelInfo",
                "GetMotoStatusUpstreamChannelInfo",
                "GetMotoLagStatus",
            ]

            _LOGGER.debug("MB8611: Fetching modem data via HNAP GetMultipleHNAPs")
            json_response = builder.call_multiple(session, base_url, soap_actions)

            ***REMOVED*** Parse JSON response (MB8611 uses JSON, not XML)
            response_data = json.loads(json_response)

            ***REMOVED*** Extract nested response
            if "GetMultipleHNAPsResponse" in response_data:
                hnap_data = response_data["GetMultipleHNAPsResponse"]
            else:
                hnap_data = response_data

            ***REMOVED*** Parse downstream channels
            downstream = self._parse_downstream_from_hnap(hnap_data)

            ***REMOVED*** Parse upstream channels
            upstream = self._parse_upstream_from_hnap(hnap_data)

            ***REMOVED*** Parse system info
            system_info = self._parse_system_info_from_hnap(hnap_data)

            return {
                "downstream": downstream,
                "upstream": upstream,
                "system_info": system_info,
            }

        except json.JSONDecodeError as e:
            _LOGGER.error("MB8611: Failed to parse HNAP JSON response: %s", e)
            return {"downstream": [], "upstream": [], "system_info": {}}
        except Exception as e:
            _LOGGER.error("MB8611: Error parsing HNAP data: %s", e, exc_info=True)
            return {"downstream": [], "upstream": [], "system_info": {}}

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
                _LOGGER.warning("MB8611: No downstream channel data found")
                return channels

            ***REMOVED*** Split by |+| delimiter
            channel_entries = channel_data.split("|+|")

            for entry in channel_entries:
                if not entry.strip():
                    continue

                ***REMOVED*** Split by ^ delimiter
                fields = entry.split("^")

                if len(fields) < 9:
                    _LOGGER.warning("MB8611: Invalid downstream channel entry: %s", entry)
                    continue

                try:
                    ***REMOVED*** Parse channel fields
                    channel_id = int(fields[0])
                    lock_status = fields[1].strip()
                    modulation = fields[2].strip()
                    ch_id = int(fields[3])
                    frequency = int(round(float(fields[4].strip()) * 1_000_000))  ***REMOVED*** MHz to Hz
                    power = float(fields[5].strip())
                    snr = float(fields[6].strip())
                    corrected = int(fields[7])
                    uncorrected = int(fields[8])

                    channel_info = {
                        "channel_id": channel_id,
                        "lock_status": lock_status,
                        "modulation": modulation,
                        "ch_id": ch_id,
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
                _LOGGER.warning("MB8611: No upstream channel data found")
                return channels

            ***REMOVED*** Split by |+| delimiter
            channel_entries = channel_data.split("|+|")

            for entry in channel_entries:
                if not entry.strip():
                    continue

                ***REMOVED*** Split by ^ delimiter
                fields = entry.split("^")

                if len(fields) < 7:
                    _LOGGER.warning("MB8611: Invalid upstream channel entry: %s", entry)
                    continue

                try:
                    ***REMOVED*** Parse channel fields
                    channel_id = int(fields[0])
                    lock_status = fields[1].strip()
                    modulation = fields[2].strip()
                    ch_id = int(fields[3])
                    symbol_rate = int(fields[4])
                    frequency = int(round(float(fields[5].strip()) * 1_000_000))  ***REMOVED*** MHz to Hz
                    power = float(fields[6].strip())

                    channel_info = {
                        "channel_id": channel_id,
                        "lock_status": lock_status,
                        "modulation": modulation,
                        "ch_id": ch_id,
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

    def _set_if_present(self, source: dict, source_key: str, target: dict, target_key: str) -> None:
        """Set target[key] if source[source_key] exists and is non-empty."""
        value = source.get(source_key, "")
        if value:
            target[target_key] = value
