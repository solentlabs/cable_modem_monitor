"""Parser for Motorola MB8611 cable modem using HNAP protocol."""

from __future__ import annotations

import json
import logging

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import HNAPAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType
from custom_components.cable_modem_monitor.core.hnap_builder import HNAPRequestBuilder
from custom_components.cable_modem_monitor.core.hnap_json_builder import HNAPJsonRequestBuilder

from ..base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class MotorolaMB8611HnapParser(ModemParser):
    """Parser for Motorola MB8611 cable modem using HNAP/SOAP protocol."""

    name = "Motorola MB8611 (HNAP)"
    manufacturer = "Motorola"
    models = ["MB8611", "MB8612"]
    priority = 101  # Higher priority for the API-based method

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
        Log in using HNAP authentication (tries JSON first, then XML/SOAP).

        Some MB8611 firmware variants use JSON-formatted HNAP authentication,
        while others use XML/SOAP. This method tries both.

        Note: This method is maintained for backward compatibility.
        New code should use auth_config with AuthFactory instead.
        """
        # Try JSON-based HNAP login first
        json_builder = HNAPJsonRequestBuilder(
            endpoint=self.auth_config.hnap_endpoint, namespace=self.auth_config.soap_action_namespace
        )

        _LOGGER.debug("MB8611: Attempting JSON-based HNAP login")
        success: bool
        response: str | None
        success, response = json_builder.login(session, base_url, username, password)

        if success:
            _LOGGER.info("MB8611: JSON HNAP login successful")
            return (True, response)

        # Fall back to XML/SOAP-based HNAP login
        _LOGGER.debug("MB8611: JSON login failed, trying XML/SOAP-based HNAP login")
        from custom_components.cable_modem_monitor.core.authentication import AuthFactory

        auth_strategy = AuthFactory.get_strategy(self.auth_config.strategy)
        success, response = auth_strategy.login(session, base_url, username, password, self.auth_config)

        if success:
            _LOGGER.info("MB8611: XML/SOAP HNAP login successful")
        else:
            _LOGGER.warning("MB8611: Both JSON and XML/SOAP HNAP login methods failed")

        return (success, response)

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

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """
        Parse data using HNAP calls (JSON or XML/SOAP).

        Some MB8611 firmware variants use JSON-formatted HNAP, others use XML/SOAP.
        This method tries JSON first, then falls back to XML/SOAP.

        Args:
            soup: BeautifulSoup object (may not be used for HNAP modems)
            session: requests.Session with authenticated session
            base_url: Modem base URL

        Returns:
            Dict with downstream, upstream, and system_info
        """
        if not session or not base_url:
            raise ValueError("MB8611 requires session and base_url for HNAP calls")

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
                    "MB8611: Both JSON and XML/SOAP HNAP methods failed. " "JSON error: %s, XML error: %s",
                    str(json_error),
                    str(xml_error),
                    exc_info=True,
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
                    _LOGGER.warning("MB8611: HNAP authentication failure detected - modem requires valid credentials")

                return result

    def _parse_with_json_hnap(self, session, base_url: str) -> dict:
        """Parse modem data using JSON-based HNAP requests."""
        _LOGGER.debug("MB8611: Attempting JSON-based HNAP communication")

        # Build JSON HNAP request builder
        builder = HNAPJsonRequestBuilder(
            endpoint=self.auth_config.hnap_endpoint, namespace=self.auth_config.soap_action_namespace
        )

        # Make batched HNAP request for all data
        hnap_actions = [
            "GetMotoStatusStartupSequence",
            "GetMotoStatusConnectionInfo",
            "GetMotoStatusDownstreamChannelInfo",
            "GetMotoStatusUpstreamChannelInfo",
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
        builder = HNAPRequestBuilder(
            endpoint=self.auth_config.hnap_endpoint, namespace=self.auth_config.soap_action_namespace
        )

        # Make batched HNAP request for all data
        soap_actions = [
            "GetMotoStatusStartupSequence",
            "GetMotoStatusConnectionInfo",
            "GetMotoStatusDownstreamChannelInfo",
            "GetMotoStatusUpstreamChannelInfo",
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
                    channel_id = int(fields[0])
                    lock_status = fields[1].strip()
                    modulation = fields[2].strip()
                    ch_id = int(fields[3])
                    frequency = int(round(float(fields[4].strip()) * 1_000_000))  # MHz to Hz
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
                    channel_id = int(fields[0])
                    lock_status = fields[1].strip()
                    modulation = fields[2].strip()
                    ch_id = int(fields[3])
                    symbol_rate = int(fields[4])
                    frequency = int(round(float(fields[5].strip()) * 1_000_000))  # MHz to Hz
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
