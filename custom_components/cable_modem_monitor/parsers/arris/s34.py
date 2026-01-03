"""Parser for Arris/CommScope S34 cable modem using HNAP protocol.

The S34 uses HNAP protocol similar to S33, but with key differences:
- Response format: Pure JSON (not caret-delimited like S33)
- Firmware pattern: AT01.01.* (vs S33's TB01.03.*)
- Authentication: Uses HMAC-SHA256 (vs S33's HMAC-MD5)

MVP Scope: Authentication + system info only (GetArrisDeviceStatus)
Channel data deferred to Phase 4.

Reference: https://github.com/solentlabs/cable_modem_monitor/issues/TBD
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import HNAPAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType
from custom_components.cable_modem_monitor.core.hnap_json_builder import HNAPJsonRequestBuilder

from ..base_parser import ModemCapability, ModemParser, ParserStatus

_LOGGER = logging.getLogger(__name__)


class ArrisS34HnapParser(ModemParser):
    """Parser for Arris/CommScope S34 cable modem using HNAP/JSON protocol.

    MVP Implementation: Only provides system info (firmware version, model, connection status).
    Downstream/upstream channel data will be added in Phase 4.
    """

    name = "Arris S34"
    manufacturer = "Arris/CommScope"
    models = ["S34", "CommScope S34", "ARRIS S34"]
    priority = 102  # Higher than S33 (101) to ensure S34 is tried first

    # Parser status
    status = ParserStatus.AWAITING_VERIFICATION
    verification_source = "https://github.com/solentlabs/cable_modem_monitor/issues/TBD"

    # Device metadata
    release_date = "2024"
    docsis_version = "3.1"
    fixtures_path = "tests/parsers/arris/fixtures/s34"

    # S34 blocks ICMP ping - skip ping check and use HTTP-only health status
    supports_icmp = False

    def __init__(self):
        """Initialize the parser with instance-level state."""
        super().__init__()
        # Store the JSON builder instance to preserve private_key across login/parse calls
        self._json_builder: HNAPJsonRequestBuilder | None = None
        # Store private key for SHA256 authentication
        self._private_key: str | None = None

    # HNAP authentication configuration (same as S33)
    auth_config = HNAPAuthConfig(
        strategy=AuthStrategyType.HNAP_SESSION,
        login_url="/Login.html",
        hnap_endpoint="/HNAP1/",
        session_timeout_indicator="UN-AUTH",
        soap_action_namespace="http://purenetworks.com/HNAP1/",
    )

    url_patterns = [
        {"path": "/HNAP1/", "auth_method": "hnap", "auth_required": True},
        {"path": "/Login.html", "auth_method": "hnap", "auth_required": False},
    ]

    # MVP Capabilities - only system info for now
    # Channel data (DOWNSTREAM_CHANNELS, UPSTREAM_CHANNELS) deferred to Phase 4
    capabilities = {
        ModemCapability.SOFTWARE_VERSION,
        ModemCapability.RESTART,  # Uses SetArrisConfigurationInfo Action="reboot"
    }

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is an Arris/CommScope S34 modem.

        Detection strategy:
        1. Check for "S34" model identifier in HTML (primary)
        2. Reject if "S33" is present without "S34" (avoid false-positive)
        3. Check for S34-specific firmware pattern (AT01.01.*)
        4. Check for Arris/CommScope branding with HNAP

        Args:
            soup: BeautifulSoup parsed HTML
            url: The URL that returned this HTML
            html: Raw HTML string

        Returns:
            True if this is an S34 modem
        """
        # Primary check: S34 model identifier
        if "S34" in html:
            return True

        # Avoid matching S33-only content
        if "S33" in html and "S34" not in html:
            return False

        # Check for S34-specific firmware pattern
        if "AT01.01" in html:
            return True

        # Check for Arris/CommScope branding with HNAP (less specific)
        # Only match if we see S34-specific indicators
        return (
            ("ARRIS" in html or "CommScope" in html)
            and "purenetworks.com/HNAP1" in html
            and "GetArrisDeviceStatus" in html
        )

    def _hmac_sha256(self, key: str, message: str) -> str:
        """Compute HMAC-SHA256 and return uppercase hex string.

        This matches the JavaScript hex_hmac_sha256() function used by S34.
        The S34 uses SHA256 instead of MD5 (which S33/MB8611 use).
        """
        return hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest().upper()

    def _get_hnap_auth_sha256(self, action: str) -> str:
        """Generate HNAP_AUTH header using SHA256 for authenticated requests.

        Format: HMAC_SHA256(PrivateKey, timestamp + SOAPAction) + " " + timestamp
        """
        if not self._private_key:
            private_key = "withoutloginkey"
        else:
            private_key = self._private_key

        current_time = int(time.time() * 1000) % 2000000000000
        timestamp = str(current_time)
        soap_action_uri = f'"{self.auth_config.soap_action_namespace}{action}"'

        auth = self._hmac_sha256(private_key, timestamp + soap_action_uri)
        return f"{auth} {timestamp}"

    def login(self, session, base_url, username, password) -> tuple[bool, str | None]:
        """
        Log in using HNAP authentication with HMAC-SHA256.

        The S34 uses HMAC-SHA256 (different from S33/MB8611 which use HMAC-MD5):
        1. Request challenge with Action="request"
        2. Compute PrivateKey = HMAC_SHA256(PublicKey + password, Challenge)
        3. Compute LoginPassword = HMAC_SHA256(PrivateKey, Challenge)
        4. Send login with Action="login" and computed LoginPassword

        Note: S34 requires HTTPS with self-signed certificates.
        The session should have verify=False for self-signed certs.

        Args:
            session: requests.Session object
            base_url: Modem base URL (e.g., "https://192.168.100.1")
            username: Username for authentication
            password: Password for authentication

        Returns:
            Tuple of (success, response_text)
        """
        _LOGGER.debug("S34: Attempting HMAC-SHA256 HNAP login to %s", base_url)

        endpoint = self.auth_config.hnap_endpoint
        namespace = self.auth_config.soap_action_namespace

        try:
            # Step 1: Request challenge
            challenge_data = {
                "Login": {
                    "Action": "request",
                    "Username": username,
                    "LoginPassword": "",
                    "Captcha": "",
                }
            }

            _LOGGER.debug("S34: Sending challenge request")

            response = session.post(
                f"{base_url}{endpoint}",
                json=challenge_data,
                headers={
                    "SOAPAction": f'"{namespace}Login"',
                    "HNAP_AUTH": self._get_hnap_auth_sha256("Login"),
                    "Content-Type": "application/json",
                },
                timeout=10,
                verify=session.verify,
            )

            if response.status_code != 200:
                _LOGGER.error("S34: Challenge request failed with HTTP %d", response.status_code)
                return (False, response.text)

            # Parse challenge response
            try:
                challenge_json = json.loads(response.text)
            except json.JSONDecodeError:
                _LOGGER.error("S34: Challenge response is not valid JSON: %s", response.text[:500])
                return (False, response.text)

            login_response = challenge_json.get("LoginResponse", {})
            challenge = login_response.get("Challenge")
            cookie = login_response.get("Cookie")
            public_key = login_response.get("PublicKey")

            if not all([challenge, cookie, public_key]):
                _LOGGER.error(
                    "S34: Challenge response missing required fields. Response: %s",
                    response.text[:500],
                )
                return (False, response.text)

            _LOGGER.debug(
                "S34: Challenge received: Challenge=%s..., PublicKey=%s...",
                challenge[:8] if challenge else "None",
                public_key[:8] if public_key else "None",
            )

            # Step 2: Compute credentials using HMAC-SHA256
            # PrivateKey = HMAC_SHA256(PublicKey + password, Challenge)
            private_key = self._hmac_sha256(public_key + password, challenge)
            self._private_key = private_key

            # Set session cookies
            session.cookies.set("uid", cookie)
            session.cookies.set("PrivateKey", private_key)

            # LoginPassword = HMAC_SHA256(PrivateKey, Challenge)
            login_password = self._hmac_sha256(private_key, challenge)

            _LOGGER.debug("S34: Computed SHA256 credentials, sending login request")

            # Step 3: Send login with computed password
            login_data = {
                "Login": {
                    "Action": "login",
                    "Username": username,
                    "LoginPassword": login_password,
                    "Captcha": "",
                }
            }

            response = session.post(
                f"{base_url}{endpoint}",
                json=login_data,
                headers={
                    "SOAPAction": f'"{namespace}Login"',
                    "HNAP_AUTH": self._get_hnap_auth_sha256("Login"),
                    "Content-Type": "application/json",
                },
                timeout=10,
                verify=session.verify,
            )

            if response.status_code != 200:
                _LOGGER.error("S34: Login request failed with HTTP %d", response.status_code)
                self._private_key = None
                return (False, response.text)

            # Check login result
            try:
                response_json = json.loads(response.text)
                login_result = response_json.get("LoginResponse", {}).get("LoginResult", "")

                if login_result in ("OK", "SUCCESS"):
                    _LOGGER.info("S34: HMAC-SHA256 login successful! LoginResult=%s", login_result)

                    # Create JSON builder for subsequent requests
                    self._json_builder = HNAPJsonRequestBuilder(
                        endpoint=endpoint,
                        namespace=namespace,
                        empty_action_value="",
                    )
                    # Transfer the private key to the builder
                    self._json_builder._private_key = self._private_key

                    return (True, response.text)
                else:
                    _LOGGER.error("S34: Login failed with result: %s. Response: %s", login_result, response.text[:500])
                    self._private_key = None
                    return (False, response.text)

            except json.JSONDecodeError:
                _LOGGER.error("S34: Login response is not valid JSON: %s", response.text[:500])
                self._private_key = None
                return (False, response.text)

        except Exception as e:
            _LOGGER.error("S34: Login failed with exception: %s", str(e))
            self._private_key = None
            return (False, str(e))

    def _is_auth_failure(self, error: Exception) -> bool:
        """Detect if an exception indicates an authentication failure.

        Args:
            error: The exception that occurred

        Returns:
            True if this appears to be an auth failure
        """
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

        MVP Implementation: Only fetches GetArrisDeviceStatus for system info.
        Channel data (downstream/upstream) deferred to Phase 4.

        Args:
            soup: BeautifulSoup object (not used for HNAP modems)
            session: requests.Session with authenticated session
            base_url: Modem base URL

        Returns:
            Dict with downstream, upstream, and system_info
        """
        if not session or not base_url:
            raise ValueError("S34 requires session and base_url for HNAP calls")

        try:
            return self._parse_with_json_hnap(session, base_url)
        except Exception as json_error:
            _LOGGER.error("S34: HNAP parsing failed: %s", str(json_error), exc_info=True)

            # Check if failure is due to authentication
            auth_failure = self._is_auth_failure(json_error)

            # Log unusual pattern: login succeeded but parse failed
            if self._json_builder is not None:
                _LOGGER.warning(
                    "S34: Parse failed after successful login - possible session invalidation. "
                    "Cookies: %s, Has private_key: %s, Error: %s",
                    list(session.cookies.keys()) if session else "no session",
                    self._json_builder._private_key is not None,
                    str(json_error)[:100],
                )

            result: dict[str, list | dict] = {"downstream": [], "upstream": [], "system_info": {}}

            if auth_failure:
                result["_auth_failure"] = True  # type: ignore[assignment]
                result["_login_page_detected"] = True  # type: ignore[assignment]
                result["_diagnostic_context"] = {
                    "parser": "S34 HNAP",
                    "error": str(json_error)[:200],
                    "error_type": "HNAP authentication failure",
                }
                _LOGGER.warning("S34: HNAP authentication failure detected - modem requires valid credentials")

            return result

    def _call_hnap_sha256(self, session, base_url: str, actions: list[str]) -> str:
        """Make HNAP request using SHA256 authentication.

        The S34 requires SHA256 for all authenticated requests, not MD5.

        Args:
            session: Authenticated requests.Session
            base_url: Modem base URL
            actions: List of HNAP action names

        Returns:
            JSON response text
        """
        endpoint = self.auth_config.hnap_endpoint
        namespace = self.auth_config.soap_action_namespace

        # Build request with empty string values (S34 format)
        action_objects = {action: "" for action in actions}
        request_data = {"GetMultipleHNAPs": action_objects}

        response = session.post(
            f"{base_url}{endpoint}",
            json=request_data,
            headers={
                "SOAPAction": f'"{namespace}GetMultipleHNAPs"',
                "HNAP_AUTH": self._get_hnap_auth_sha256("GetMultipleHNAPs"),
                "Content-Type": "application/json",
            },
            timeout=10,
            verify=session.verify,
        )

        response.raise_for_status()
        return response.text

    def _parse_with_json_hnap(self, session, base_url: str) -> dict:
        """Parse modem data using JSON-based HNAP requests with SHA256 auth.

        MVP Implementation: Only fetches GetArrisDeviceStatus.

        Args:
            session: Authenticated requests.Session
            base_url: Modem base URL

        Returns:
            Dict with downstream, upstream, and system_info
        """
        _LOGGER.debug("S34: Attempting JSON-based HNAP communication with SHA256 auth")

        # MVP: Only fetch GetArrisDeviceStatus for system info
        # Phase 4 will add: GetArrisStatusDownstreamChannelInfo, GetArrisStatusUpstreamChannelInfo
        hnap_actions = [
            "GetArrisDeviceStatus",
        ]

        _LOGGER.debug("S34: Fetching modem data via JSON HNAP GetMultipleHNAPs")
        json_response = self._call_hnap_sha256(session, base_url, hnap_actions)

        # Parse JSON response
        response_data = json.loads(json_response)

        # S34 may return direct JSON or wrapped in GetMultipleHNAPsResponse
        if "GetMultipleHNAPsResponse" in response_data:
            hnap_data = response_data["GetMultipleHNAPsResponse"]
        else:
            hnap_data = response_data

        _LOGGER.debug(
            "S34: JSON HNAP response received. Top-level keys: %s, response size: %d bytes",
            list(hnap_data.keys()),
            len(json_response),
        )

        # Parse system info from GetArrisDeviceStatus
        system_info = self._parse_system_info_from_hnap(hnap_data)

        _LOGGER.info(
            "S34: Successfully parsed system info (firmware: %s, model: %s)",
            system_info.get("software_version", "unknown"),
            system_info.get("model_name", "unknown"),
        )

        # MVP: Return empty channel lists (Phase 4 will populate these)
        return {
            "downstream": [],
            "upstream": [],
            "system_info": system_info,
        }

    def _parse_system_info_from_hnap(self, hnap_data: dict) -> dict:
        """Parse system info from HNAP JSON response.

        S34 Response Format (pure JSON, NOT caret-delimited):
        {
            "GetArrisDeviceStatusResponse": {
                "FirmwareVersion": "AT01.01.010.042324_S3.04.735",
                "InternetConnection": "Connected",
                "DownstreamFrequency": "483000000 Hz",
                "StatusSoftwareModelName": "S34",
                "StatusSoftwareModelName2": "S34",
                "GetArrisDeviceStatusResult": "OK"
            }
        }

        Args:
            hnap_data: Parsed JSON response from HNAP call

        Returns:
            Dict with system info fields
        """
        system_info: dict[str, str] = {}

        try:
            # Extract GetArrisDeviceStatus response
            device_status = hnap_data.get("GetArrisDeviceStatusResponse", {})

            if not device_status:
                _LOGGER.warning(
                    "S34: No GetArrisDeviceStatusResponse found. Keys: %s",
                    list(hnap_data.keys()),
                )
                return system_info

            # Check result status
            result = device_status.get("GetArrisDeviceStatusResult", "")
            if result and result != "OK":
                _LOGGER.warning("S34: GetArrisDeviceStatus returned: %s", result)

            # Map S34 fields to standard system_info keys
            # FirmwareVersion -> software_version
            self._set_if_present(device_status, "FirmwareVersion", system_info, "software_version")

            # InternetConnection -> internet_connection
            self._set_if_present(device_status, "InternetConnection", system_info, "internet_connection")

            # StatusSoftwareModelName -> model_name
            self._set_if_present(device_status, "StatusSoftwareModelName", system_info, "model_name")

            # DownstreamFrequency -> downstream_frequency (informational)
            self._set_if_present(device_status, "DownstreamFrequency", system_info, "downstream_frequency")

            _LOGGER.debug("S34: Parsed system_info: %s", system_info)

        except Exception as e:
            _LOGGER.error("S34: Error parsing system info: %s", e)

        return system_info

    def _set_if_present(self, source: dict, source_key: str, target: dict, target_key: str) -> None:
        """Set target[key] if source[source_key] exists and is non-empty.

        Args:
            source: Source dictionary
            source_key: Key to look up in source
            target: Target dictionary to update
            target_key: Key to set in target
        """
        value = source.get(source_key, "")
        if value:
            target[target_key] = value

    def _get_current_config(self, builder, session, base_url: str) -> dict[str, str]:
        """Get current modem configuration (EEE and LED settings).

        The browser fetches this before sending a reboot command to preserve settings.

        Args:
            builder: HNAPJsonRequestBuilder instance
            session: Authenticated session
            base_url: Modem base URL

        Returns:
            Dict with current config values
        """
        try:
            response = builder.call_single(session, base_url, "GetArrisConfigurationInfo", {})
            response_data: dict = json.loads(response)
            config_response: dict[str, str] = response_data.get("GetArrisConfigurationInfoResponse", {})

            if config_response.get("GetArrisConfigurationInfoResult") == "OK":
                _LOGGER.debug(
                    "S34: Got current config: EEE=%s, LED=%s",
                    config_response.get("ethSWEthEEE"),
                    config_response.get("LedStatus"),
                )
                return config_response

            _LOGGER.warning("S34: GetArrisConfigurationInfo returned non-OK result")
            return {}
        except Exception as e:
            _LOGGER.warning("S34: Failed to get current config: %s", str(e)[:100])
            return {}

    def restart(self, session, base_url) -> bool:
        """Restart the S34 modem via HNAP SetArrisConfigurationInfo.

        The S34 uses SetArrisConfigurationInfo with Action="reboot" to restart.
        This is the same mechanism as S33.

        Returns:
            True if restart command was sent successfully, False otherwise
        """
        _LOGGER.info("S34: Sending restart command via SetArrisConfigurationInfo")

        # Use JSON builder if available from login
        if self._json_builder is not None:
            builder = self._json_builder
            _LOGGER.debug("S34: Using stored JSON builder for restart")
        else:
            builder = HNAPJsonRequestBuilder(
                endpoint=self.auth_config.hnap_endpoint,
                namespace=self.auth_config.soap_action_namespace,
                empty_action_value="",
            )
            _LOGGER.warning("S34: No stored JSON builder for restart - creating new one (may lack auth)")

        try:
            # First, get current configuration values (EEE and LED settings)
            current_config = self._get_current_config(builder, session, base_url)

            # Build restart request with current settings preserved
            restart_data = {
                "Action": "reboot",
                "SetEEEEnable": current_config.get("ethSWEthEEE", "0"),
                "LED_Status": current_config.get("LedStatus", "1"),
            }

            _LOGGER.debug("S34: Sending restart with config: %s", restart_data)
            response = builder.call_single(session, base_url, "SetArrisConfigurationInfo", restart_data)

            # Log response for debugging
            _LOGGER.debug("S34: Restart response: %s", response[:500] if response else "empty")

            # Parse response to check result
            response_data = json.loads(response)
            result = response_data.get("SetArrisConfigurationInfoResponse", {}).get(
                "SetArrisConfigurationInfoResult", ""
            )
            action_status = response_data.get("SetArrisConfigurationInfoResponse", {}).get(
                "SetArrisConfigurationInfoAction", ""
            )

            if result == "OK" and action_status == "REBOOT":
                _LOGGER.info("S34: Restart command accepted - modem is rebooting")
                return True
            elif result == "OK":
                # OK but no REBOOT action - might still work
                _LOGGER.info(
                    "S34: Restart command returned OK (action=%s) - modem may be rebooting",
                    action_status,
                )
                return True
            else:
                _LOGGER.warning(
                    "S34: Restart command returned unexpected result=%s, action=%s",
                    result,
                    action_status,
                )
                return False

        except ConnectionResetError:
            # Connection reset often means the modem is rebooting
            _LOGGER.info("S34: Restart likely successful (connection reset by rebooting modem)")
            return True

        except Exception as e:
            error_str = str(e)
            if "Connection aborted" in error_str or "Connection reset" in error_str:
                _LOGGER.info("S34: Restart likely successful (connection reset)")
                return True

            _LOGGER.error("S34: Restart failed with error: %s", error_str[:200])
            return False
