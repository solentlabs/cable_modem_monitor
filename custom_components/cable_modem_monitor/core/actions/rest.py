"""REST API action implementations.

REST API modems use JSON endpoints for actions like restart.
This module provides action implementations for REST API-based modems.

Note: Currently a stub awaiting real-world capture data. When a user captures
the restart API call for a REST modem (e.g., SuperHub5), this can be completed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .base import ActionResult, ActionType, ModemAction

if TYPE_CHECKING:
    import requests

    from ..auth.handler import AuthHandler

_LOGGER = logging.getLogger(__name__)


class RESTRestartAction(ModemAction):
    """Restart action for REST API-based modems.

    Fully data-driven from modem.yaml configuration:
    - actions.restart.endpoint: REST API endpoint
    - actions.restart.method: HTTP method (POST, PUT, etc.)
    - actions.restart.payload: JSON payload to send
    - actions.restart.success_status: Expected HTTP status code (default 200)
    """

    action_type = ActionType.RESTART

    def __init__(self, modem_config: dict[str, Any]):
        """Initialize the REST API restart action.

        Args:
            modem_config: Full modem configuration from modem.yaml
        """
        super().__init__(modem_config)

        # Get action-specific config from modem.yaml actions.restart
        actions_config = self._get_actions_config()
        self._restart_config = actions_config.get("restart", {})

        # Get restart endpoint and params
        self._endpoint = self._restart_config.get("endpoint", "")
        self._method = self._restart_config.get("method", "POST").upper()
        self._payload = self._restart_config.get("payload", {})
        self._success_status = self._restart_config.get("success_status", 200)

        # Modem info for logging and potential cross-reference validation
        self._manufacturer = modem_config.get("manufacturer", "")
        self._model = modem_config.get("model", "unknown")

    def execute(
        self,
        session: requests.Session,
        base_url: str,
        auth_handler: AuthHandler | None = None,
    ) -> ActionResult:
        """Execute the restart action via REST API.

        Args:
            session: Authenticated requests.Session
            base_url: Modem base URL
            auth_handler: Not used for REST API actions (session already authenticated)

        Returns:
            ActionResult with success status and message
        """
        if not self._endpoint:
            return ActionResult(
                success=False,
                message="No restart endpoint configured in modem.yaml actions.restart.endpoint",
            )

        try:
            restart_url = f"{base_url}{self._endpoint}"
            _LOGGER.info("%s: Sending REST restart to %s", self._model, restart_url)

            if self._method == "POST":
                response = session.post(restart_url, json=self._payload, timeout=10)
            elif self._method == "PUT":
                response = session.put(restart_url, json=self._payload, timeout=10)
            else:
                return ActionResult(
                    success=False,
                    message=f"Unsupported HTTP method: {self._method}",
                )

            _LOGGER.debug(
                "%s: Restart response - status=%d",
                self._model,
                response.status_code,
            )

            if response.status_code == self._success_status:
                _LOGGER.info("%s: Restart command accepted", self._model)
                return ActionResult(success=True, message="Restart command accepted")
            else:
                _LOGGER.warning(
                    "%s: Restart returned status %d (expected %d)",
                    self._model,
                    response.status_code,
                    self._success_status,
                )
                return ActionResult(
                    success=False,
                    message=f"Restart failed with status {response.status_code}",
                )

        except (ConnectionError, ConnectionResetError) as e:
            # Connection dropped = modem is rebooting (success!)
            _LOGGER.info(
                "%s: Modem rebooting (connection dropped): %s",
                self._model,
                type(e).__name__,
            )
            return ActionResult(success=True, message="Restart command sent (connection dropped)")

        except Exception as e:
            error_str = str(e)
            if "Connection aborted" in error_str or "Connection reset" in error_str:
                _LOGGER.info("%s: Restart likely successful (connection reset)", self._model)
                return ActionResult(success=True, message="Restart command sent (connection reset)")

            _LOGGER.error("%s: Error sending restart command: %s", self._model, error_str[:200])
            return ActionResult(success=False, message=f"Restart failed: {error_str[:200]}")
