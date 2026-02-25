"""HNAP action implementations.

HNAP modems use SOAP-like JSON requests for actions. This module provides
a generic, data-driven action implementation that reads all configuration
from modem.yaml.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from ..auth import HNAPJsonRequestBuilder
from ..auth.types import HMACAlgorithm
from .base import ActionResult, ActionType, ModemAction

if TYPE_CHECKING:
    import requests

    from ..auth.handler import AuthHandler

_LOGGER = logging.getLogger(__name__)


class HNAPRestartAction(ModemAction):
    """Restart action for HNAP-based modems.

    Fully data-driven from modem.yaml configuration:
    - actions.restart.action_name: HNAP action name (preferred)
    - actions.restart.params: Parameters to send
    - actions.restart.pre_fetch_action: Optional action to call first
    - actions.restart.response_key: Key to extract from response
    - actions.restart.result_key: Key containing result value
    - actions.restart.success_value: Expected value for success
    """

    action_type = ActionType.RESTART

    def __init__(self, modem_config: dict[str, Any]):
        """Initialize from modem.yaml configuration."""
        super().__init__(modem_config)

        # Get timeout from modem.yaml (schema guarantees this field exists)
        self._timeout: int = modem_config["timeout"]

        # Get HNAP config for protocol settings
        hnap_config = self._get_hnap_config()
        self._endpoint = hnap_config.get("endpoint", "/HNAP1/")
        self._namespace = hnap_config.get("namespace", "http://purenetworks.com/HNAP1/")
        self._hmac_algorithm = hnap_config.get("hmac_algorithm", "md5")
        self._empty_action_value = hnap_config.get("empty_action_value", "")

        # Get action-specific config from actions.restart
        actions_config = self._get_actions_config()
        self._restart_config = actions_config.get("restart") or {}

        # Get restart action name from actions.restart.action_name (preferred)
        self._action_name = self._restart_config.get("action_name")

        # DEPRECATED: Fall back to auth.hnap.actions.restart for migration
        if not self._action_name:
            hnap_actions = hnap_config.get("actions") or {}
            self._action_name = hnap_actions.get("restart")
            if self._action_name:
                _LOGGER.debug(
                    "Using deprecated auth.hnap.actions.restart location. " "Migrate to actions.restart.action_name"
                )

        # Extract config values
        self._params = self._restart_config.get("params", {})
        self._pre_fetch_action = self._restart_config.get("pre_fetch_action")
        self._pre_fetch_response_key = self._restart_config.get("pre_fetch_response_key")
        self._response_key = self._restart_config.get("response_key", "")
        self._result_key = self._restart_config.get("result_key", "")
        self._success_value = self._restart_config.get("success_value", "OK")

    def execute(
        self,
        session: requests.Session,
        base_url: str,
        auth_handler: AuthHandler | None = None,
    ) -> ActionResult:
        """Execute the restart action.

        Args:
            session: Authenticated requests.Session
            base_url: Modem base URL
            auth_handler: Auth handler to get HNAP builder from

        Returns:
            ActionResult with success status and message
        """
        if not self._action_name:
            return ActionResult(
                success=False,
                message="No restart action configured in modem.yaml actions.restart.action_name",
            )

        # Extract HNAP builder from auth handler
        builder = auth_handler.get_hnap_builder() if auth_handler else None
        if not builder:
            _LOGGER.warning("No HNAP builder available - creating new one (may lack auth)")
            builder = self._create_builder()

        try:
            # Execute optional pre-fetch action to get current config
            pre_fetch_data: dict[str, str] = {}
            if self._pre_fetch_action:
                pre_fetch_data = self._execute_pre_fetch(session, base_url, builder)

            # Build params, interpolating any ${var:default} placeholders
            params = self._interpolate_params(self._params, pre_fetch_data)

            # Execute restart action
            _LOGGER.info("Sending HNAP restart via %s", self._action_name)
            _LOGGER.debug("Restart params: %s", params)

            response = builder.call_single(session, base_url, self._action_name, params)
            response_data = json.loads(response)

            # Parse response using configured keys
            return self._parse_response(response_data)

        except ConnectionResetError:
            _LOGGER.info("Restart likely successful (connection reset by rebooting modem)")
            return ActionResult(success=True, message="Restart command sent (connection reset)")

        except Exception as e:
            error_str = str(e)
            if "Connection aborted" in error_str or "Connection reset" in error_str:
                _LOGGER.info("Restart likely successful (connection reset)")
                return ActionResult(success=True, message="Restart command sent (connection reset)")

            _LOGGER.error("Restart failed with error: %s", error_str[:200])
            return ActionResult(success=False, message=f"Restart failed: {error_str[:200]}")

    def _create_builder(self) -> HNAPJsonRequestBuilder:
        """Create a new HNAP builder from modem.yaml config."""
        return HNAPJsonRequestBuilder(
            endpoint=self._endpoint,
            namespace=self._namespace,
            hmac_algorithm=HMACAlgorithm(self._hmac_algorithm),
            timeout=self._timeout,
            empty_action_value=self._empty_action_value,
        )

    def _execute_pre_fetch(
        self,
        session: requests.Session,
        base_url: str,
        builder: HNAPJsonRequestBuilder,
    ) -> dict[str, str]:
        """Execute pre-fetch action to get current configuration.

        Returns:
            Dictionary of values from the pre-fetch response
        """
        try:
            action_name = str(self._pre_fetch_action) if self._pre_fetch_action else ""
            _LOGGER.debug("Pre-fetching via %s", action_name)
            response = builder.call_single(session, base_url, action_name, {})
            response_data = json.loads(response)

            # Extract the response data using configured key
            if self._pre_fetch_response_key:
                result = response_data.get(self._pre_fetch_response_key, {})
                return dict(result) if isinstance(result, dict) else {}
            return dict(response_data) if isinstance(response_data, dict) else {}

        except Exception as e:
            _LOGGER.warning("Pre-fetch failed: %s", str(e)[:100])
            return {}

    def _interpolate_params(
        self,
        params: dict[str, str],
        pre_fetch_data: dict[str, str],
    ) -> dict[str, str]:
        """Interpolate ${var:default} placeholders in params.

        Args:
            params: Parameter dictionary with possible ${var:default} placeholders
            pre_fetch_data: Data from pre-fetch action to use for interpolation

        Returns:
            Parameters with placeholders replaced by values
        """
        result = {}
        placeholder_pattern = re.compile(r"\$\{(\w+)(?::([^}]*))?\}")

        for key, value in params.items():
            if isinstance(value, str):
                match = placeholder_pattern.match(value)
                if match:
                    var_name = match.group(1)
                    default = match.group(2) if match.group(2) is not None else ""
                    result[key] = pre_fetch_data.get(var_name, default)
                else:
                    result[key] = value
            else:
                result[key] = value

        return result

    def _parse_response(self, response_data: dict) -> ActionResult:
        """Parse the action response using configured keys.

        Args:
            response_data: Parsed JSON response

        Returns:
            ActionResult based on response parsing
        """
        # Extract nested response if configured
        if self._response_key:
            response_data = response_data.get(self._response_key, {})

        # Get result value
        result = ""
        if self._result_key:
            result = response_data.get(self._result_key, "")

        # Check for success
        if result == self._success_value:
            _LOGGER.info("Restart command accepted (result=%s)", result)
            return ActionResult(
                success=True,
                message="Restart command accepted",
                details={"result": result},
            )
        elif result:
            _LOGGER.warning("Restart returned unexpected result: %s", result)
            return ActionResult(
                success=False,
                message=f"Unexpected result: {result}",
                details={"result": result},
            )
        else:
            # No result key found - assume success if we got a response
            _LOGGER.info("Restart command sent (no result key in response)")
            return ActionResult(
                success=True,
                message="Restart command sent",
                details={"response": response_data},
            )
