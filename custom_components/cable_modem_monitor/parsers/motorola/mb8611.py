"""Parser for Motorola MB8611 cable modem using HNAP protocol."""
import logging
import json
from bs4 import BeautifulSoup
from ..base_parser import ModemParser
from custom_components.cable_modem_monitor.core.auth_config import HNAPAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType
from custom_components.cable_modem_monitor.core.hnap_builder import HNAPRequestBuilder

_LOGGER = logging.getLogger(__name__)


class MotorolaMB8611Parser(ModemParser):
    """Parser for Motorola MB8611 cable modem using HNAP/SOAP protocol."""

    name = "Motorola MB8611"
    manufacturer = "Motorola"
    models = ["MB8611", "MB8612"]
    priority = 100  # Model-specific parser, try before generic

    # HNAP authentication configuration
    auth_config = HNAPAuthConfig(
        strategy=AuthStrategyType.HNAP_SESSION,
        login_url="/Login.html",
        hnap_endpoint="/HNAP1/",
        session_timeout_indicator="UN-AUTH",
        soap_action_namespace="http://purenetworks.com/HNAP1/"
    )

    url_patterns = [
        {"path": "/HNAP1/", "auth_method": "hnap", "auth_required": True},
        {"path": "/MotoStatusConnection.html", "auth_method": "hnap", "auth_required": True},
    ]

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Motorola MB8611 modem."""
        # Check for MB8611-specific indicators
        if "MB8611" in html or "MB 8611" in html or "2251-MB8611" in html:
            return True

        # Check for HNAP/SOAP indicators
        if "HNAP" in html or "purenetworks.com/HNAP1" in html:
            # Additional check for Motorola
            if "Motorola" in html:
                return True

        return False

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

        # Build HNAP request builder
        builder = HNAPRequestBuilder(
            endpoint=self.auth_config.hnap_endpoint,
            namespace=self.auth_config.soap_action_namespace
        )

        try:
            # Make batched HNAP request for all data
            soap_actions = [
                "GetMotoStatusStartupSequence",
                "GetMotoStatusConnectionInfo",
                "GetMotoStatusDownstreamChannelInfo",
                "GetMotoStatusUpstreamChannelInfo",
                "GetMotoLagStatus"
            ]

            _LOGGER.debug("MB8611: Fetching modem data via HNAP GetMultipleHNAPs")
            json_response = builder.call_multiple(session, base_url, soap_actions)

            # Parse JSON response (MB8611 uses JSON, not XML)
            response_data = json.loads(json_response)

            # Extract nested response
            if "GetMultipleHNAPsResponse" in response_data:
                hnap_data = response_data["GetMultipleHNAPsResponse"]
            else:
                hnap_data = response_data

            # Parse downstream channels
            downstream = self._parse_downstream_from_hnap(hnap_data)

            # Parse upstream channels
            upstream = self._parse_upstream_from_hnap(hnap_data)

            # Parse system info
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
        channels = []

        try:
            downstream_response = hnap_data.get("GetMotoStatusDownstreamChannelInfoResponse", {})
            channel_data = downstream_response.get("MotoConnDownstreamChannel", "")

            if not channel_data:
                _LOGGER.warning("MB8611: No downstream channel data found")
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
                    channel_id = int(fields[0])
                    lock_status = fields[1].strip()
                    modulation = fields[2].strip()
                    ch_id = int(fields[3])
                    frequency = float(fields[4].strip()) * 1_000_000  # MHz to Hz
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
        channels = []

        try:
            upstream_response = hnap_data.get("GetMotoStatusUpstreamChannelInfoResponse", {})
            channel_data = upstream_response.get("MotoConnUpstreamChannel", "")

            if not channel_data:
                _LOGGER.warning("MB8611: No upstream channel data found")
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
                    channel_id = int(fields[0])
                    lock_status = fields[1].strip()
                    modulation = fields[2].strip()
                    ch_id = int(fields[3])
                    symbol_rate = int(fields[4])
                    frequency = float(fields[5].strip()) * 1_000_000  # MHz to Hz
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
        system_info = {}

        try:
            # Get connection info
            conn_info = hnap_data.get("GetMotoStatusConnectionInfoResponse", {})
            if conn_info:
                uptime = conn_info.get("MotoConnSystemUpTime", "")
                if uptime:
                    system_info["system_uptime"] = uptime

                network_access = conn_info.get("MotoConnNetworkAccess", "")
                if network_access:
                    system_info["network_access"] = network_access

            # Get startup sequence info
            startup_info = hnap_data.get("GetMotoStatusStartupSequenceResponse", {})
            if startup_info:
                ds_freq = startup_info.get("MotoConnDSFreq", "")
                if ds_freq:
                    system_info["downstream_frequency"] = ds_freq

                connectivity_status = startup_info.get("MotoConnConnectivityStatus", "")
                if connectivity_status:
                    system_info["connectivity_status"] = connectivity_status

                boot_status = startup_info.get("MotoConnBootStatus", "")
                if boot_status:
                    system_info["boot_status"] = boot_status

                security_status = startup_info.get("MotoConnSecurityStatus", "")
                if security_status:
                    system_info["security_status"] = security_status

                security_comment = startup_info.get("MotoConnSecurityComment", "")
                if security_comment:
                    system_info["security_comment"] = security_comment

        except Exception as e:
            _LOGGER.error("MB8611: Error parsing system info: %s", e)

        return system_info
