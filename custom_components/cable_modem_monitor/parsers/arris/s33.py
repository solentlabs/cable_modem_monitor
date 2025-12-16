"""Parser for Arris/CommScope S33 cable modem using HNAP protocol.

The S33 uses the same HNAP protocol as the Motorola MB8611, but with different
action and response key prefixes:
- S33: GetCustomer*, CustomerConn* (e.g., GetCustomerStatusDownstreamChannelInfo)
- MB8611: GetMoto*, MotoConn* (e.g., GetMotoStatusDownstreamChannelInfo)

The authentication mechanism and data format (caret-delimited, pipe-separated)
are identical between the two modems.

Reference: https://github.com/solentlabs/cable_modem_monitor/issues/32
"""

from __future__ import annotations

import json
import logging

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import HNAPAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthFactory, AuthStrategyType
from custom_components.cable_modem_monitor.core.hnap_json_builder import HNAPJsonRequestBuilder

from ..base_parser import ModemCapability, ModemParser, ParserStatus

_LOGGER = logging.getLogger(__name__)


class ArrisS33HnapParser(ModemParser):
    """Parser for Arris/CommScope S33 cable modem using HNAP/SOAP protocol."""

    name = "Arris S33"
    manufacturer = "Arris/CommScope"
    models = ["S33", "CommScope S33", "ARRIS S33"]
    priority = 101  # Higher priority for the API-based method

    # Parser status
    status = ParserStatus.AWAITING_VERIFICATION
    verification_source = "https://github.com/solentlabs/cable_modem_monitor/issues/32"

    # Device metadata
    release_date = "2020"
    docsis_version = "3.1"
    fixtures_path = "tests/parsers/arris/fixtures/s33"

    # S33 blocks ICMP ping - skip ping check and use HTTP-only health status
    supports_icmp = False

    def __init__(self):
        """Initialize the parser with instance-level state."""
        super().__init__()
        # Store the JSON builder instance to preserve private_key across login/parse calls
        self._json_builder: HNAPJsonRequestBuilder | None = None

    # HNAP authentication configuration
    auth_config = HNAPAuthConfig(
        strategy=AuthStrategyType.HNAP_SESSION,
        login_url="/Login.html",
        hnap_endpoint="/HNAP1/",
        session_timeout_indicator="UN-AUTH",
        soap_action_namespace="http://purenetworks.com/HNAP1/",
    )

    url_patterns = [
        {"path": "/HNAP1/", "auth_method": "hnap", "auth_required": True},
        {"path": "/Cmconnectionstatus.html", "auth_method": "hnap", "auth_required": True},
    ]

    # Capabilities - S33 HNAP parser
    capabilities = {
        ModemCapability.DOWNSTREAM_CHANNELS,
        ModemCapability.UPSTREAM_CHANNELS,
        ModemCapability.SYSTEM_UPTIME,
        ModemCapability.SOFTWARE_VERSION,
        ModemCapability.RESTART,  # Uses SetArrisConfigurationInfo Action="reboot"
    }

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is an Arris/CommScope S33 modem."""
        # Check for S33 model identifiers
        if "S33" in html:
            return True
        # Check for Arris/CommScope branding with HNAP
        if ("ARRIS" in html or "CommScope" in html) and "purenetworks.com/HNAP1" in html:
            return True
        # Check for SURFboard branding (S33 is a SURFboard model)
        return "SURFboard" in html and "HNAP" in html

    def login(self, session, base_url, username, password) -> tuple[bool, str | None]:
        """
        Log in using HNAP authentication (tries JSON first, then XML/SOAP).

        The S33 uses the same HNAP authentication as the MB8611.

        Note: S33 typically uses HTTPS with self-signed certificates.
        The session should have verify=False for self-signed certs.
        """
        # Try JSON-based HNAP login
        # S33 requires empty string "" for action values (observed in HAR captures)
        self._json_builder = HNAPJsonRequestBuilder(
            endpoint=self.auth_config.hnap_endpoint,
            namespace=self.auth_config.soap_action_namespace,
            empty_action_value="",
        )

        _LOGGER.debug("S33: Attempting JSON-based HNAP login to %s", base_url)
        success: bool
        response: str | None
        success, response = self._json_builder.login(session, base_url, username, password)

        if success:
            _LOGGER.info("S33: JSON HNAP login successful")
            return (True, response)

        # JSON login failed - clear the builder
        self._json_builder = None

        # Fall back to XML/SOAP-based HNAP login
        _LOGGER.debug("S33: JSON login failed, trying XML/SOAP-based HNAP login")
        auth_strategy = AuthFactory.get_strategy(self.auth_config.strategy)
        success, response = auth_strategy.login(session, base_url, username, password, self.auth_config)

        if success:
            _LOGGER.info("S33: XML/SOAP HNAP login successful")
        else:
            _LOGGER.warning("S33: Both JSON and XML/SOAP HNAP login methods failed")

        return (success, response)

    def _is_auth_failure(self, error: Exception) -> bool:
        """Detect if an exception indicates an authentication failure."""
        error_str = str(error).lower()

        auth_indicators = [
            "401",
            "403",
            "unauthorized",
            "forbidden",
            "authentication failed",
            "login failed",
            "invalid credentials",
            "session timeout",
            "invalid session",
            '"loginresult":"failed"',
            '"loginresult": "failed"',
        ]

        return any(indicator in error_str for indicator in auth_indicators)

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """
        Parse data using HNAP calls.

        Args:
            soup: BeautifulSoup object (may not be used for HNAP modems)
            session: requests.Session with authenticated session
            base_url: Modem base URL

        Returns:
            Dict with downstream, upstream, and system_info
        """
        if not session or not base_url:
            raise ValueError("S33 requires session and base_url for HNAP calls")

        try:
            return self._parse_with_json_hnap(session, base_url)
        except Exception as json_error:
            _LOGGER.error("S33: HNAP parsing failed: %s", str(json_error), exc_info=True)

            # Check if failure is due to authentication
            auth_failure = self._is_auth_failure(json_error)

            result: dict[str, list | dict] = {"downstream": [], "upstream": [], "system_info": {}}

            if auth_failure:
                result["_auth_failure"] = True  # type: ignore[assignment]
                result["_login_page_detected"] = True  # type: ignore[assignment]
                result["_diagnostic_context"] = {
                    "parser": "S33 HNAP",
                    "error": str(json_error)[:200],
                    "error_type": "HNAP authentication failure",
                }
                _LOGGER.warning("S33: HNAP authentication failure detected - modem requires valid credentials")

            return result

    def _parse_with_json_hnap(self, session, base_url: str) -> dict:
        """Parse modem data using JSON-based HNAP requests."""
        _LOGGER.debug("S33: Attempting JSON-based HNAP communication")

        # Reuse the builder from login() to preserve the private_key
        if self._json_builder is not None:
            builder = self._json_builder
            _LOGGER.debug("S33: Reusing JSON builder from login (private_key preserved)")
        else:
            builder = HNAPJsonRequestBuilder(
                endpoint=self.auth_config.hnap_endpoint,
                namespace=self.auth_config.soap_action_namespace,
                empty_action_value="",
            )
            _LOGGER.warning("S33: No stored JSON builder - creating new one (may lack auth)")

        # Make batched HNAP request for all data
        # S33 uses GetCustomer* action names (vs MB8611's GetMoto*)
        # GetArrisDeviceStatus provides firmware version
        hnap_actions = [
            "GetCustomerStatusStartupSequence",
            "GetCustomerStatusConnectionInfo",
            "GetCustomerStatusDownstreamChannelInfo",
            "GetCustomerStatusUpstreamChannelInfo",
            "GetArrisDeviceStatus",
        ]

        _LOGGER.debug("S33: Fetching modem data via JSON HNAP GetMultipleHNAPs")
        json_response = builder.call_multiple(session, base_url, hnap_actions)

        # Parse JSON response
        response_data = json.loads(json_response)

        # Extract nested response
        hnap_data = response_data.get("GetMultipleHNAPsResponse", response_data)

        _LOGGER.debug(
            "S33: JSON HNAP response received. Top-level keys: %s, response size: %d bytes",
            list(hnap_data.keys()),
            len(json_response),
        )

        # Parse channels and system info
        downstream = self._parse_downstream_from_hnap(hnap_data)
        upstream = self._parse_upstream_from_hnap(hnap_data)
        system_info = self._parse_system_info_from_hnap(hnap_data)

        _LOGGER.info(
            "S33: Successfully parsed data using JSON HNAP (downstream: %d channels, upstream: %d channels)",
            len(downstream),
            len(upstream),
        )

        return {
            "downstream": downstream,
            "upstream": upstream,
            "system_info": system_info,
        }

    def _parse_downstream_from_hnap(self, hnap_data: dict) -> list[dict]:
        """
        Parse downstream channels from HNAP JSON response.

        Format: "ChannelSelect^LockStatus^ChannelType^ChannelID^Frequency^PowerLevel^SNRLevel^Corrected^Uncorrected"
        Delimiter: ^ (caret) between fields, |+| between channels
        """
        channels: list[dict] = []

        try:
            # S33 uses CustomerConn* keys (vs MB8611's MotoConn*)
            downstream_response = hnap_data.get("GetCustomerStatusDownstreamChannelInfoResponse", {})
            channel_data = downstream_response.get("CustomerConnDownstreamChannel", "")

            if not channel_data:
                _LOGGER.warning(
                    "S33: No downstream channel data found. Response keys: %s, content: %s",
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
                    _LOGGER.warning("S33: Invalid downstream channel entry: %s", entry)
                    continue

                try:
                    # Parse channel fields
                    # fields[0] = row index (display order only)
                    # fields[3] = DOCSIS Channel ID
                    channel_id = int(fields[3])
                    lock_status = fields[1].strip()
                    modulation = fields[2].strip()

                    # Frequency - could be Hz or need conversion
                    freq_str = fields[4].strip()
                    if "Hz" in freq_str:
                        frequency = int(freq_str.replace(" Hz", "").replace("Hz", ""))
                    else:
                        # Assume MHz, convert to Hz
                        frequency = int(round(float(freq_str) * 1_000_000))

                    # Power - strip units if present
                    power_str = fields[5].strip().replace(" dBmV", "").replace("dBmV", "")
                    power = float(power_str)

                    # SNR - strip units if present
                    snr_str = fields[6].strip().replace(" dB", "").replace("dB", "")
                    snr = float(snr_str)

                    corrected = int(fields[7])
                    uncorrected = int(fields[8])

                    channel_info = {
                        "channel_id": channel_id,
                        "lock_status": lock_status,
                        "modulation": modulation,
                        "frequency": frequency,
                        "power": power,
                        "snr": snr,
                        "corrected": corrected,
                        "uncorrected": uncorrected,
                    }

                    channels.append(channel_info)

                except (ValueError, IndexError) as e:
                    _LOGGER.warning("S33: Error parsing downstream channel: %s - %s", entry, e)
                    continue

        except Exception as e:
            _LOGGER.error("S33: Error parsing downstream channels: %s", e)

        return channels

    def _parse_upstream_from_hnap(self, hnap_data: dict) -> list[dict]:
        """
        Parse upstream channels from HNAP JSON response.

        Format: "ChannelSelect^LockStatus^ChannelType^ChannelID^SymbolRate/Width^Frequency^PowerLevel"
        Delimiter: ^ (caret) between fields, |+| between channels
        """
        channels: list[dict] = []

        try:
            # S33 uses CustomerConn* keys
            upstream_response = hnap_data.get("GetCustomerStatusUpstreamChannelInfoResponse", {})
            channel_data = upstream_response.get("CustomerConnUpstreamChannel", "")

            if not channel_data:
                _LOGGER.warning(
                    "S33: No upstream channel data found. Response keys: %s, content: %s",
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
                    _LOGGER.warning("S33: Invalid upstream channel entry: %s", entry)
                    continue

                try:
                    # Parse channel fields
                    channel_id = int(fields[3])
                    lock_status = fields[1].strip()
                    modulation = fields[2].strip()
                    symbol_rate = fields[4].strip()  # Keep as string, may have units

                    # Frequency - could be Hz or need conversion
                    freq_str = fields[5].strip()
                    if "Hz" in freq_str:
                        frequency = int(freq_str.replace(" Hz", "").replace("Hz", ""))
                    else:
                        # Assume MHz, convert to Hz
                        frequency = int(round(float(freq_str) * 1_000_000))

                    # Power - strip units if present
                    power_str = fields[6].strip().replace(" dBmV", "").replace("dBmV", "")
                    power = float(power_str)

                    channel_info = {
                        "channel_id": channel_id,
                        "lock_status": lock_status,
                        "modulation": modulation,
                        "symbol_rate": symbol_rate,
                        "frequency": frequency,
                        "power": power,
                    }

                    channels.append(channel_info)

                except (ValueError, IndexError) as e:
                    _LOGGER.warning("S33: Error parsing upstream channel: %s - %s", entry, e)
                    continue

        except Exception as e:
            _LOGGER.error("S33: Error parsing upstream channels: %s", e)

        return channels

    def _parse_system_info_from_hnap(self, hnap_data: dict) -> dict:
        """Parse system info from HNAP JSON response."""
        system_info: dict[str, str] = {}

        try:
            self._extract_connection_info(hnap_data, system_info)
            self._extract_startup_info(hnap_data, system_info)
            self._extract_device_status(hnap_data, system_info)
        except Exception as e:
            _LOGGER.error("S33: Error parsing system info: %s", e)

        return system_info

    def _extract_connection_info(self, hnap_data: dict, system_info: dict) -> None:
        """Extract connection info fields from HNAP data."""
        # S33 uses CustomerConn* keys
        conn_info = hnap_data.get("GetCustomerStatusConnectionInfoResponse", {})
        if not conn_info:
            return

        self._set_if_present(conn_info, "CustomerCurSystemTime", system_info, "system_uptime")
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

    def _get_current_config(self, builder, session, base_url: str) -> dict[str, str]:
        """Get current modem configuration (EEE and LED settings).

        The browser fetches this before sending a reboot command to preserve settings.
        """
        try:
            response = builder.call_single(session, base_url, "GetArrisConfigurationInfo", {})
            response_data: dict = json.loads(response)
            config_response: dict[str, str] = response_data.get("GetArrisConfigurationInfoResponse", {})

            if config_response.get("GetArrisConfigurationInfoResult") == "OK":
                _LOGGER.debug(
                    "S33: Got current config: EEE=%s, LED=%s",
                    config_response.get("ethSWEthEEE"),
                    config_response.get("LedStatus"),
                )
                return config_response

            _LOGGER.warning("S33: GetArrisConfigurationInfo returned non-OK result")
            return {}
        except Exception as e:
            _LOGGER.warning("S33: Failed to get current config: %s", str(e)[:100])
            return {}

    def restart(self, session, base_url) -> bool:
        """Restart the S33 modem via HNAP SetArrisConfigurationInfo.

        The S33 uses SetArrisConfigurationInfo with Action="reboot" to restart.
        This was discovered from the configuration.js JavaScript in the HAR capture.

        The expected response contains SetArrisConfigurationInfoAction="REBOOT"
        when the restart command is accepted.

        Returns:
            True if restart command was sent successfully, False otherwise
        """
        _LOGGER.info("S33: Sending restart command via SetArrisConfigurationInfo")

        # Use JSON builder if available from login
        if self._json_builder is not None:
            builder = self._json_builder
            _LOGGER.debug("S33: Using stored JSON builder for restart")
        else:
            builder = HNAPJsonRequestBuilder(
                endpoint=self.auth_config.hnap_endpoint,
                namespace=self.auth_config.soap_action_namespace,
                empty_action_value="",
            )
            _LOGGER.warning("S33: No stored JSON builder for restart - creating new one (may lack auth)")

        try:
            # First, get current configuration values (EEE and LED settings)
            # The browser does this before sending reboot to preserve current settings
            current_config = self._get_current_config(builder, session, base_url)

            # Build restart request with current settings preserved
            restart_data = {
                "Action": "reboot",
                "SetEEEEnable": current_config.get("ethSWEthEEE", "0"),
                "LED_Status": current_config.get("LedStatus", "1"),
            }

            _LOGGER.debug("S33: Sending restart with config: %s", restart_data)
            response = builder.call_single(session, base_url, "SetArrisConfigurationInfo", restart_data)

            # Log response for debugging
            _LOGGER.debug("S33: Restart response: %s", response[:500] if response else "empty")

            # Parse response to check result
            response_data = json.loads(response)
            result = response_data.get("SetArrisConfigurationInfoResponse", {}).get(
                "SetArrisConfigurationInfoResult", ""
            )
            action_status = response_data.get("SetArrisConfigurationInfoResponse", {}).get(
                "SetArrisConfigurationInfoAction", ""
            )

            if result == "OK" and action_status == "REBOOT":
                _LOGGER.info("S33: Restart command accepted - modem is rebooting")
                return True
            elif result == "OK":
                # OK but no REBOOT action - might still work
                _LOGGER.info(
                    "S33: Restart command returned OK (action=%s) - modem may be rebooting",
                    action_status,
                )
                return True
            else:
                _LOGGER.warning(
                    "S33: Restart command returned unexpected result=%s, action=%s",
                    result,
                    action_status,
                )
                return False

        except ConnectionResetError:
            # Connection reset often means the modem is rebooting
            _LOGGER.info("S33: Restart likely successful (connection reset by rebooting modem)")
            return True

        except Exception as e:
            error_str = str(e)
            if "Connection aborted" in error_str or "Connection reset" in error_str:
                _LOGGER.info("S33: Restart likely successful (connection reset)")
                return True

            _LOGGER.error("S33: Restart failed with error: %s", error_str[:200])
            return False
