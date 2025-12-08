"""JSON-based HNAP request builder for MB8611 firmwares that use JSON instead of XML/SOAP.

The challenge-response authentication implementation is based on reverse engineering
work by BowlesCR (Chris Bowles) from Issue ***REMOVED***40 and the prior art from xNinjaKittyx's mb8600
repository. The HMAC-MD5 authentication flow was documented through HAR file analysis
of the modem's Login.js and SOAPAction.js files, captured using our Playwright-based
HAR capture tool (scripts/capture_modem.py).

References:
- BowlesCR's MB8600 Login PoC: https://github.com/BowlesCR/MB8600_Login
- xNinjaKittyx's mb8600: https://github.com/xNinjaKittyx/mb8600
- Issue ***REMOVED***40: https://github.com/solentlabs/cable_modem_monitor/issues/40
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import TYPE_CHECKING, cast

import requests

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


def _hmac_md5(key: str, message: str) -> str:
    """Compute HMAC-MD5 and return uppercase hex string.

    This matches the JavaScript hex_hmac_md5() function used by MB8611.
    """
    return hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.md5).hexdigest().upper()


class HNAPJsonRequestBuilder:
    """Helper for building and executing JSON-based HNAP requests.

    Some MB8611 firmware variants use JSON-formatted HNAP requests instead of XML/SOAP.
    This builder handles those cases.
    """

    def __init__(self, endpoint: str, namespace: str):
        """
        Initialize JSON HNAP request builder.

        Args:
            endpoint: HNAP endpoint path (e.g., "/HNAP1/")
            namespace: HNAP namespace (e.g., "http://purenetworks.com/HNAP1/")
        """
        self.endpoint = endpoint
        self.namespace = namespace
        self._private_key: str | None = None  ***REMOVED*** Stored after successful login for auth headers
        ***REMOVED*** Store last request/response for diagnostics (passwords redacted)
        self._last_auth_attempt: dict | None = None

    def clear_auth_cache(self) -> None:
        """Clear cached authentication.

        Call this after modem restart to force re-authentication on next request.
        The modem invalidates all sessions on reboot, so cached credentials become stale.
        """
        self._private_key = None

    def get_last_auth_attempt(self) -> dict | None:
        """Get the last authentication attempt details for diagnostics.

        Returns a dict with request/response data (passwords redacted) or None
        if no auth attempt has been made. Useful for debugging authentication
        issues by comparing what we sent vs what the browser sends.
        """
        return self._last_auth_attempt

    def _get_hnap_auth(self, action: str) -> str:
        """Generate HNAP_AUTH header for authenticated requests.

        The MB8611 requires this header for all requests after login.
        Format: HMAC_MD5(PrivateKey, timestamp + SOAPAction) + " " + timestamp
        """
        if not self._private_key:
            ***REMOVED*** For login requests, use a default key
            private_key = "withoutloginkey"
        else:
            private_key = self._private_key

        ***REMOVED*** Timestamp must fit in 32-bit integer range, matching the JS implementation
        current_time = int(time.time() * 1000) % 2000000000000
        timestamp = str(current_time)
        soap_action_uri = f'"{self.namespace}{action}"'

        auth = _hmac_md5(private_key, timestamp + soap_action_uri)
        return f"{auth} {timestamp}"

    def call_single(self, session: requests.Session, base_url: str, action: str, params: dict | None = None) -> str:
        """
        Make single JSON HNAP action call.

        Args:
            session: requests.Session object
            base_url: Modem base URL
            action: HNAP action name (e.g., "GetMotoStatusConnectionInfo")
            params: Optional parameters for the action

        Returns:
            JSON response text

        Raises:
            requests.RequestException: If request fails
        """
        ***REMOVED*** Build JSON request
        request_data = {action: params or {}}

        url = f"{base_url}{self.endpoint}"
        headers = {
            "SOAPAction": f'"{self.namespace}{action}"',
            "HNAP_AUTH": self._get_hnap_auth(action),
            "Content-Type": "application/json",
        }

        response = session.post(
            url,
            json=request_data,
            headers=headers,
            timeout=10,
            verify=session.verify,
        )

        ***REMOVED*** Enhanced error diagnostics for failed HTTP requests
        if not response.ok:
            _LOGGER.error(
                "HNAP call_single failed: action=%s, status=%s, url=%s",
                action,
                response.status_code,
                url,
            )
            _LOGGER.error("HNAP call_single request: %s", request_data)
            _LOGGER.error("HNAP call_single response: %s", response.text[:500] if response.text else "(empty)")

        response.raise_for_status()
        return cast(str, response.text)

    def call_multiple(self, session: requests.Session, base_url: str, actions: list[str]) -> str:
        """
        Make batched JSON HNAP request (GetMultipleHNAPs).

        Args:
            session: requests.Session object
            base_url: Modem base URL
            actions: List of HNAP action names

        Returns:
            JSON response text containing all action results

        Raises:
            requests.RequestException: If request fails
        """
        ***REMOVED*** Build JSON request with nested action objects
        action_objects: dict[str, dict] = {action: {} for action in actions}
        request_data = {"GetMultipleHNAPs": action_objects}

        _LOGGER.debug(
            "JSON HNAP GetMultipleHNAPs request: actions=%s, request_size=%d bytes",
            actions,
            len(json.dumps(request_data)),
        )

        response = session.post(
            f"{base_url}{self.endpoint}",
            json=request_data,
            headers={
                "SOAPAction": f'"{self.namespace}GetMultipleHNAPs"',
                "HNAP_AUTH": self._get_hnap_auth("GetMultipleHNAPs"),
                "Content-Type": "application/json",
            },
            timeout=10,
            verify=session.verify,
        )

        _LOGGER.debug(
            "JSON HNAP GetMultipleHNAPs response: status=%d, response_size=%d bytes",
            response.status_code,
            len(response.text),
        )

        response.raise_for_status()
        return cast(str, response.text)

    def login(  ***REMOVED*** noqa: C901 - complexity from multi-step auth protocol
        self, session: requests.Session, base_url: str, username: str, password: str
    ) -> tuple[bool, str]:
        """
        Perform JSON-based HNAP login with challenge-response authentication.

        The MB8611 uses a two-step challenge-response protocol:
        1. Request challenge: Send Action="request" to get Challenge, Cookie, PublicKey
        2. Compute credentials using HMAC-MD5
        3. Send login: Send Action="login" with computed LoginPassword

        Args:
            session: requests.Session object
            base_url: Modem base URL
            username: Username for authentication
            password: Password for authentication

        Returns:
            Tuple of (success: bool, response_text: str)
        """
        _LOGGER.debug(
            "JSON HNAP login attempt: URL=%s%s, Username=%s",
            base_url,
            self.endpoint,
            username,
        )

        try:
            ***REMOVED*** Step 1: Request challenge
            ***REMOVED*** Note: PrivateLogin field is required for MB8611 authentication
            ***REMOVED*** It tells the modem which field will contain the hashed password
            challenge_data = {
                "Login": {
                    "Action": "request",
                    "Username": username,
                    "LoginPassword": "",
                    "Captcha": "",
                    "PrivateLogin": "LoginPassword",
                }
            }

            ***REMOVED*** Log request payload for debugging (helps compare with browser requests)
            _LOGGER.debug(
                "HNAP challenge request payload: %s",
                json.dumps(challenge_data, separators=(",", ":")),
            )

            ***REMOVED*** Initialize auth attempt tracking
            self._last_auth_attempt = {
                "challenge_request": challenge_data,
                "challenge_response": None,
                "login_request": None,
                "login_response": None,
                "error": None,
            }

            response = session.post(
                f"{base_url}{self.endpoint}",
                json=challenge_data,
                headers={
                    "SOAPAction": f'"{self.namespace}Login"',
                    "HNAP_AUTH": self._get_hnap_auth("Login"),
                    "Content-Type": "application/json",
                },
                timeout=10,
                verify=session.verify,
            )

            ***REMOVED*** Store challenge response for diagnostics
            self._last_auth_attempt["challenge_response"] = response.text[:1000] if response.text else None

            if response.status_code != 200:
                self._last_auth_attempt["error"] = f"Challenge HTTP {response.status_code}"
                _LOGGER.error(
                    "JSON HNAP challenge request failed with HTTP %d: %s",
                    response.status_code,
                    response.text[:500] if response.text else "empty",
                )
                return (False, response.text)

            ***REMOVED*** Parse challenge response
            try:
                challenge_json = json.loads(response.text)
            except json.JSONDecodeError:
                _LOGGER.error("JSON HNAP challenge response is not valid JSON: %s", response.text[:500])
                return (False, response.text)

            login_response = challenge_json.get("LoginResponse", {})
            challenge = login_response.get("Challenge")
            cookie = login_response.get("Cookie")
            public_key = login_response.get("PublicKey")

            if not all([challenge, cookie, public_key]):
                _LOGGER.error(
                    "JSON HNAP challenge response missing required fields. "
                    "Challenge=%s, Cookie=%s, PublicKey=%s. Response: %s",
                    challenge is not None,
                    cookie is not None,
                    public_key is not None,
                    response.text[:500],
                )
                return (False, response.text)

            _LOGGER.debug(
                "JSON HNAP challenge received: Challenge=%s..., PublicKey=%s...",
                challenge[:8] if challenge else "None",
                public_key[:8] if public_key else "None",
            )

            ***REMOVED*** Step 2: Compute credentials
            ***REMOVED*** PrivateKey = HMAC_MD5(PublicKey + password, Challenge)
            private_key = _hmac_md5(public_key + password, challenge)
            self._private_key = private_key  ***REMOVED*** Store for subsequent authenticated requests

            ***REMOVED*** Set the session cookie
            session.cookies.set("uid", cookie)

            ***REMOVED*** LoginPassword = HMAC_MD5(PrivateKey, Challenge)
            login_password = _hmac_md5(private_key, challenge)

            _LOGGER.debug("JSON HNAP computed credentials, sending login request")

            ***REMOVED*** Step 3: Send login with computed password
            login_data = {
                "Login": {
                    "Action": "login",
                    "Username": username,
                    "LoginPassword": login_password,
                    "Captcha": "",
                    "PrivateLogin": "LoginPassword",
                }
            }

            ***REMOVED*** Log request payload with password redacted for debugging
            redacted_login = {
                "Login": {
                    **login_data["Login"],
                    "LoginPassword": "[REDACTED]",
                }
            }
            _LOGGER.debug(
                "HNAP login request payload: %s",
                json.dumps(redacted_login, separators=(",", ":")),
            )
            self._last_auth_attempt["login_request"] = redacted_login

            response = session.post(
                f"{base_url}{self.endpoint}",
                json=login_data,
                headers={
                    "SOAPAction": f'"{self.namespace}Login"',
                    "HNAP_AUTH": self._get_hnap_auth("Login"),
                    "Content-Type": "application/json",
                },
                timeout=10,
                verify=session.verify,
            )

            _LOGGER.debug(
                "JSON HNAP login response: status=%d, response_length=%d bytes",
                response.status_code,
                len(response.text),
            )

            ***REMOVED*** Store login response for diagnostics
            self._last_auth_attempt["login_response"] = response.text[:1000] if response.text else None

            if response.status_code != 200:
                self._last_auth_attempt["error"] = f"Login HTTP {response.status_code}"
                _LOGGER.error(
                    "JSON HNAP login failed with HTTP status %s. Response: %s",
                    response.status_code,
                    response.text[:500] if response.text else "empty",
                )
                self._private_key = None  ***REMOVED*** Clear on failure
                return (False, response.text)

            ***REMOVED*** Check login result
            try:
                response_json = json.loads(response.text)
                login_response = response_json.get("LoginResponse", {})
                login_result = login_response.get("LoginResult", "")

                if login_result in ("OK", "SUCCESS"):
                    _LOGGER.info(
                        "JSON HNAP login successful! LoginResult=%s",
                        login_result,
                    )
                    return (True, response.text)
                else:
                    self._last_auth_attempt["error"] = f"LoginResult={login_result}"
                    _LOGGER.warning(
                        "JSON HNAP login failed: LoginResult=%s. Response: %s",
                        login_result,
                        response.text[:500],
                    )
                    self._private_key = None  ***REMOVED*** Clear on failure
                    return (False, response.text)

            except json.JSONDecodeError:
                _LOGGER.warning(
                    "JSON HNAP login response not valid JSON but HTTP %d. Response: %s",
                    response.status_code,
                    response.text[:500],
                )
                return (True, response.text)

        except requests.exceptions.Timeout as e:
            _LOGGER.error("JSON HNAP login timeout: %s", str(e))
            self._private_key = None
            if self._last_auth_attempt:
                self._last_auth_attempt["error"] = f"Timeout: {e}"
            return (False, "")
        except requests.exceptions.ConnectionError as e:
            _LOGGER.error("JSON HNAP login connection error: %s", str(e))
            self._private_key = None
            if self._last_auth_attempt:
                self._last_auth_attempt["error"] = f"ConnectionError: {e}"
            return (False, "")
        except Exception as e:
            _LOGGER.error("JSON HNAP login exception: %s", str(e), exc_info=True)
            self._private_key = None
            if self._last_auth_attempt:
                self._last_auth_attempt["error"] = f"Exception: {e}"
            return (False, "")
