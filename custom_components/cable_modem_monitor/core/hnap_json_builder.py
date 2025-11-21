"""JSON-based HNAP request builder for MB8611 firmwares that use JSON instead of XML/SOAP."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, cast

import requests

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


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
        # Build JSON request
        request_data = {action: params or {}}

        response = session.post(
            f"{base_url}{self.endpoint}",
            json=request_data,
            headers={
                "SOAPAction": f'"{self.namespace}{action}"',
                "Content-Type": "application/json",
            },
            timeout=10,
            verify=session.verify,
        )

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
        # Build JSON request with nested action objects
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

    def login(self, session: requests.Session, base_url: str, username: str, password: str) -> tuple[bool, str]:
        """
        Perform JSON-based HNAP login.

        Args:
            session: requests.Session object
            base_url: Modem base URL
            username: Username for authentication
            password: Password for authentication

        Returns:
            Tuple of (success: bool, response_text: str)
        """
        login_data = {
            "Login": {
                "Username": username,
                "Password": password,
                "Captcha": "",
            }
        }

        _LOGGER.debug(
            "JSON HNAP login attempt: URL=%s%s, Username=%s (length=%d), Password length=%d",
            base_url,
            self.endpoint,
            username,
            len(username),
            len(password),
        )

        try:
            response = session.post(
                f"{base_url}{self.endpoint}",
                json=login_data,
                headers={
                    "SOAPAction": f'"{self.namespace}Login"',
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

            if response.status_code != 200:
                _LOGGER.error(
                    "JSON HNAP login failed with HTTP status %s. Response preview: %s",
                    response.status_code,
                    response.text[:500] if response.text else "empty",
                )
                return (False, response.text)

            # Try to parse JSON response to check for errors
            try:
                response_json = json.loads(response.text)

                # Check for login result
                login_response = response_json.get("LoginResponse", {})
                login_result = login_response.get("LoginResult", "")

                if login_result == "OK" or login_result == "SUCCESS":
                    _LOGGER.info(
                        "JSON HNAP login successful! Session established with modem. "
                        "Response size: %d bytes, LoginResult: %s",
                        len(response.text),
                        login_result,
                    )
                    return (True, response.text)
                else:
                    _LOGGER.warning(
                        "JSON HNAP login failed: LoginResult=%s. Response preview: %s",
                        login_result,
                        response.text[:500],
                    )
                    return (False, response.text)

            except json.JSONDecodeError:
                # If we can't parse JSON, treat non-error HTTP status as success
                _LOGGER.warning(
                    "JSON HNAP login response is not valid JSON, but HTTP status is %d. "
                    "Treating as success. Response preview: %s",
                    response.status_code,
                    response.text[:500],
                )
                return (True, response.text)

        except requests.exceptions.Timeout as e:
            _LOGGER.error("JSON HNAP login timeout - modem took too long to respond: %s", str(e))
            return (False, "")
        except requests.exceptions.ConnectionError as e:
            _LOGGER.error("JSON HNAP login connection error - cannot reach modem: %s", str(e))
            return (False, "")
        except Exception as e:
            _LOGGER.error("JSON HNAP login exception: %s", str(e), exc_info=True)
            return (False, "")
