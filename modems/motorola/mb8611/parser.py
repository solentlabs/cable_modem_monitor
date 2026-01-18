"""Parser for Motorola MB8611 cable modem using HNAP protocol."""

from __future__ import annotations

import json
import logging
from typing import Any

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth import (
    HNAPJsonRequestBuilder,
    HNAPRequestBuilder,
)
from custom_components.cable_modem_monitor.core.auth.types import HMACAlgorithm
from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.modem_config.adapter import (
    get_auth_adapter_for_parser,
)

_LOGGER = logging.getLogger(__name__)


class MotorolaMB8611HnapParser(ModemParser):
    """Parser for Motorola MB8611 cable modem using HNAP/SOAP protocol."""

    def __init__(self):
        """Initialize the parser with instance-level state."""
        super().__init__()
        # Store the JSON builder instance to preserve private_key across login/parse calls
        self._json_builder: HNAPJsonRequestBuilder | None = None

    def _get_hnap_hints(self) -> dict[str, str | dict]:
        """Get HNAP hints from modem.yaml."""
        adapter = get_auth_adapter_for_parser(self.__class__.__name__)
        if adapter:
            hints: dict[str, str | dict] | None = adapter.get_hnap_hints()  # type: ignore[assignment]
            if hints:
                return hints
        raise ValueError(f"No HNAP hints found in modem.yaml for {self.__class__.__name__}")

    def _is_auth_failure(self, error: Exception) -> bool:
        """
        Detect if an exception indicates an authentication failure.

        Common auth failure indicators:
        - HTTP 401/403 status codes
        - "LoginResult":"FAILED" in response
        - "Unauthorized" or "Forbidden" in error message
        - Session timeout or invalid session errors
        """
        error_str = str(error).lower()

        # Check for common auth failure indicators
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

    def parse_resources(self, resources: dict[str, Any]) -> dict:
        """Parse all data from pre-fetched resources.

        For HNAP parsers, resources contains:
        - "hnap_builder": The HNAPJsonRequestBuilder instance with auth state
        - "hnap_response": Pre-fetched HNAP response data (optional)
        - "/": BeautifulSoup object (for fallback compatibility)

        Args:
            resources: Dictionary of pre-fetched resources

        Returns:
            Dict with downstream, upstream, and system_info
        """
        # Get HNAP builder from resources (set by HNAPFetcher)
        builder = resources.get("hnap_builder")
        if builder:
            self._json_builder = builder
            _LOGGER.debug("MB8611: Using HNAP builder from resources")

        # Get pre-fetched HNAP response data if available
        hnap_response = resources.get("hnap_response", {})

        # HNAP parsers use JSON responses (hnap_response), not HTML (soup).
        # The resources dict may contain "/" key with HTML soup, but we don't use it.

        # If we have pre-fetched HNAP response data, parse it directly
        if hnap_response:
            _LOGGER.debug("MB8611: Parsing pre-fetched HNAP response data")
            return self._parse_hnap_response(hnap_response)

        # Otherwise, use the builder to make HNAP calls
        # Note: This path requires session/base_url which aren't in resources
        # The new architecture should provide hnap_response instead
        if self._json_builder:
            _LOGGER.debug("MB8611: HNAP builder available but no pre-fetched data")
            # Return empty result - the fetcher should provide hnap_response
            return {"downstream": [], "upstream": [], "system_info": {}}

        _LOGGER.warning("MB8611: No HNAP builder or response data in resources")
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
        """Parse data using HNAP calls (legacy interface).

        This method provides backwards compatibility. New code should use
        parse_resources() which receives pre-fetched HNAP response data.

        Some MB8611 firmware variants use JSON-formatted HNAP, others use XML/SOAP.
        This method tries JSON first, then falls back to XML/SOAP.

        Args:
            soup: BeautifulSoup object (may not be used for HNAP modems)
            session: requests.Session with authenticated session
            base_url: Modem base URL

        Returns:
            Dict with downstream, upstream, and system_info
        """
        # Build resources dict for parse_resources
        resources: dict[str, Any] = {"/": soup}
        if hasattr(self, "_json_builder") and self._json_builder:
            resources["hnap_builder"] = self._json_builder

        # If we have session and base_url, use legacy HNAP call path
        if session and base_url:
            # Try JSON-based HNAP first (newer firmware)
            try:
                return self._parse_with_json_hnap(session, base_url)
            except Exception as json_error:
                _LOGGER.debug("MB8611: JSON HNAP failed (%s), trying XML/SOAP HNAP...", str(json_error))

                # Fall back to XML/SOAP-based HNAP (older firmware)
                try:
                    return self._parse_with_xml_hnap(session, base_url)
                except Exception as xml_error:
                    _LOGGER.error(
                        "MB8611: Both JSON and XML/SOAP HNAP methods failed. JSON error: %s, XML error: %s",
                        str(json_error),
                        str(xml_error),
                        exc_info=True,
                    )

                    # Log unusual pattern: login succeeded but parse failed
                    if self._json_builder is not None:
                        _LOGGER.warning(
                            "MB8611: Parse failed after successful login - possible session invalidation. "
                            "Cookies: %s, Has private_key: %s, Error: %s",
                            list(session.cookies.keys()) if session else "no session",
                            self._json_builder._private_key is not None,
                            str(json_error)[:100],
                        )

                    # Check if failures are due to authentication issues
                    auth_failure = self._is_auth_failure(json_error) or self._is_auth_failure(xml_error)

                    result: dict[str, list | dict] = {"downstream": [], "upstream": [], "system_info": {}}

                    if auth_failure:
                        # Mark as auth failure so config_flow can block setup
                        result["_auth_failure"] = True  # type: ignore[assignment]
                        result["_login_page_detected"] = True  # type: ignore[assignment]
                        result["_diagnostic_context"] = {
                            "parser": "MB8611 HNAP",
                            "json_error": str(json_error)[:200],
                            "xml_error": str(xml_error)[:200],
                            "error_type": "HNAP authentication failure",
                        }
                        _LOGGER.warning(
                            "MB8611: HNAP authentication failure detected - modem requires valid credentials"
                        )

                    return result

        # No session/base_url - delegate to parse_resources
        return self.parse_resources(resources)

    def _parse_with_json_hnap(self, session, base_url: str) -> dict:
        """Parse modem data using JSON-based HNAP requests."""
        _LOGGER.debug("MB8611: Attempting JSON-based HNAP communication")

        # Reuse the builder from login() to preserve the private_key for authenticated requests
        # If login() wasn't called (e.g., session reuse), create a new builder
        if self._json_builder is not None:
            builder = self._json_builder
            _LOGGER.debug("MB8611: Reusing JSON builder from login (private_key preserved)")
        else:
            hints = self._get_hnap_hints()
            builder = HNAPJsonRequestBuilder(
                endpoint=str(hints["endpoint"]),
                namespace=str(hints["namespace"]),
                hmac_algorithm=HMACAlgorithm(hints["hmac_algorithm"]),
                empty_action_value=hints.get("empty_action_value", {}),
            )
            _LOGGER.warning("MB8611: No stored JSON builder - creating new one (may lack auth)")

        # Make batched HNAP request for all data
        hnap_actions = [
            "GetMotoStatusStartupSequence",
            "GetMotoStatusConnectionInfo",
            "GetMotoStatusDownstreamChannelInfo",
            "GetMotoStatusUpstreamChannelInfo",
            "GetMotoStatusSoftware",
            "GetMotoLagStatus",
        ]

        _LOGGER.debug("MB8611: Fetching modem data via JSON HNAP GetMultipleHNAPs")
        json_response = builder.call_multiple(session, base_url, hnap_actions)

        # Parse JSON response
        response_data = json.loads(json_response)

        # Extract nested response
        hnap_data = response_data.get("GetMultipleHNAPsResponse", response_data)

        # Enhanced logging to help diagnose response structure
        _LOGGER.debug(
            "MB8611: JSON HNAP response received. Top-level keys: %s, response size: %d bytes",
            list(hnap_data.keys()),
            len(json_response),
        )

        # Parse channels and system info
        downstream = self._parse_downstream_from_hnap(hnap_data)
        upstream = self._parse_upstream_from_hnap(hnap_data)
        system_info = self._parse_system_info_from_hnap(hnap_data)

        _LOGGER.info(
            "MB8611: Successfully parsed data using JSON HNAP " "(downstream: %d channels, upstream: %d channels)",
            len(downstream),
            len(upstream),
        )

        return {
            "downstream": downstream,
            "upstream": upstream,
            "system_info": system_info,
        }

    def _parse_with_xml_hnap(self, session, base_url: str) -> dict:
        """Parse modem data using XML/SOAP-based HNAP requests."""
        _LOGGER.debug("MB8611: Attempting XML/SOAP-based HNAP communication")

        # Build XML/SOAP HNAP request builder
        hints = self._get_hnap_hints()
        builder = HNAPRequestBuilder(
            endpoint=str(hints["endpoint"]),
            namespace=str(hints["namespace"]),
        )

        # Make batched HNAP request for all data
        soap_actions = [
            "GetMotoStatusStartupSequence",
            "GetMotoStatusConnectionInfo",
            "GetMotoStatusDownstreamChannelInfo",
            "GetMotoStatusUpstreamChannelInfo",
            "GetMotoStatusSoftware",
            "GetMotoLagStatus",
        ]

        _LOGGER.debug("MB8611: Fetching modem data via XML/SOAP HNAP GetMultipleHNAPs")
        json_response = builder.call_multiple(session, base_url, soap_actions)

        # Parse JSON response (MB8611 uses JSON, not XML)
        response_data = json.loads(json_response)

        # Extract nested response
        hnap_data = response_data.get("GetMultipleHNAPsResponse", response_data)

        # Enhanced logging to help diagnose response structure
        _LOGGER.debug(
            "MB8611: XML/SOAP HNAP response received. Top-level keys: %s, response size: %d bytes",
            list(hnap_data.keys()),
            len(json_response),
        )

        # Parse channels and system info
        downstream = self._parse_downstream_from_hnap(hnap_data)
        upstream = self._parse_upstream_from_hnap(hnap_data)
        system_info = self._parse_system_info_from_hnap(hnap_data)

        _LOGGER.info(
            "MB8611: Successfully parsed data using XML/SOAP HNAP " "(downstream: %d channels, upstream: %d channels)",
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

    def restart(self, session, base_url) -> bool:
        """Restart the MB8611 modem via HNAP SetStatusSecuritySettings action.

        The restart is triggered from the Security settings page (MotoStatusSecurity.html)
        using the SetStatusSecuritySettings HNAP action with MotoStatusSecurityAction=1.

        Based on analysis of modem's JavaScript in MotoStatusSecurity.html:
        - Action 1 = Reboot
        - Action 2 = Factory Reset
        - Action 3 = Change password
        """
        try:
            # Use JSON builder if available (from login), otherwise create new
            if self._json_builder is not None:
                builder = self._json_builder
            else:
                hints = self._get_hnap_hints()
                builder = HNAPJsonRequestBuilder(
                    endpoint=str(hints["endpoint"]),
                    namespace=str(hints["namespace"]),
                    hmac_algorithm=HMACAlgorithm(hints["hmac_algorithm"]),
                    empty_action_value=hints.get("empty_action_value", {}),
                )
                _LOGGER.warning("MB8611: No stored JSON builder for restart - may lack auth")

            # Build the restart request - action=1 triggers reboot
            # Based on modem's MotoStatusSecurity.html JavaScript:
            # result_xml.Set("SetStatusSecuritySettings/MotoStatusSecurityAction", "1");
            # result_xml.Set("SetStatusSecuritySettings/MotoStatusSecXXX", "XXX");
            restart_data = {
                "MotoStatusSecurityAction": "1",
                "MotoStatusSecXXX": "XXX",
            }

            _LOGGER.info("MB8611: Sending restart command via HNAP SetStatusSecuritySettings")
            response = builder.call_single(session, base_url, "SetStatusSecuritySettings", restart_data)

            # Parse response to check result
            response_data = json.loads(response)
            result = response_data.get("SetStatusSecuritySettingsResponse", {}).get(
                "SetStatusSecuritySettingsResult", ""
            )

            if result == "OK":
                _LOGGER.info("MB8611: Restart command sent successfully")
                return True
            else:
                # Enhanced error diagnostics - log full request/response for debugging
                _LOGGER.error("MB8611: Restart failed with result: %s", result)
                _LOGGER.error(
                    "MB8611: Restart diagnostics - Request: action=SetStatusSecuritySettings, " "params=%s",
                    restart_data,
                )
                _LOGGER.error("MB8611: Restart diagnostics - Full response: %s", response)
                return False

        except ConnectionResetError:
            # Connection reset is expected - modem reboots immediately
            _LOGGER.info("MB8611: Restart sent successfully (connection reset by rebooting modem)")
            return True
        except Exception as e:
            if "Connection aborted" in str(e) or "Connection reset" in str(e):
                _LOGGER.info("MB8611: Restart sent successfully (connection reset by rebooting modem)")
                return True
            _LOGGER.error("MB8611: Error sending restart command: %s", e)
            return False
