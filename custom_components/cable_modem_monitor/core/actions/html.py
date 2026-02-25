"""HTML restart action for modems using form POST.

This action handles modem restart for HTML-paradigm modems (including ASP-based).
These modems expose restart functionality via HTML form submission.

Configuration (modem.yaml):

    Static endpoint (most modems):
        actions:
          restart:
            endpoint: "/goform/restart"
            params:
              RestartReset: "Restart"

    Dynamic endpoint (Netgear modems with session IDs):
        actions:
          restart:
            pre_fetch_url: "/RouterStatus.htm"
            endpoint_pattern: "RouterStatus"    # Find form action containing this
            params:
              buttonSelect: "2"

The action:
1. If endpoint_pattern: fetches pre_fetch_url, extracts form action URL
2. Otherwise: uses static endpoint
3. POSTs form data to the endpoint
4. Interprets connection drop as success (modem rebooting)
"""

from __future__ import annotations

import logging
import re
from http.client import RemoteDisconnected
from typing import TYPE_CHECKING, Any

from requests.exceptions import ChunkedEncodingError, ConnectionError

from .base import ActionResult, ActionType, ModemAction

if TYPE_CHECKING:
    import requests

    from ..auth.handler import AuthHandler

_LOGGER = logging.getLogger(__name__)


class HTMLRestartAction(ModemAction):
    """Restart action for HTML-paradigm modems.

    Supports two endpoint modes:
    - Static: endpoint is configured directly in modem.yaml
    - Dynamic: endpoint is extracted from a form action in the pre-fetch page
    """

    action_type = ActionType.RESTART

    def __init__(self, modem_config: dict[str, Any]):
        """Initialize the HTML restart action.

        Args:
            modem_config: Full modem configuration from modem.yaml
        """
        super().__init__(modem_config)

        # Get action-specific config from modem.yaml actions.restart
        actions_config = self._get_actions_config()
        self._restart_config = actions_config.get("restart", {})

        # Static endpoint (simple modems)
        self._endpoint = self._restart_config.get("endpoint", "")

        # Dynamic endpoint extraction (Netgear modems with session IDs)
        self._endpoint_pattern = self._restart_config.get("endpoint_pattern", "")
        self._pre_fetch_url = self._restart_config.get("pre_fetch_url", "")

        # Form params to POST
        self._params = self._restart_config.get("params", {})

        # Modem info for logging
        self._model = modem_config.get("model", "unknown")

    def execute(
        self,
        session: requests.Session,
        base_url: str,
        auth_handler: AuthHandler | None = None,
    ) -> ActionResult:
        """Execute the restart action via form POST.

        Args:
            session: Authenticated requests.Session
            base_url: Modem base URL
            auth_handler: Not used for HTML actions (session already authenticated)

        Returns:
            ActionResult with success status and message
        """
        # Resolve the endpoint (static or dynamic)
        endpoint = self._resolve_endpoint(session, base_url)
        if not endpoint:
            return ActionResult(
                success=False,
                message="No restart endpoint: configure 'endpoint' or 'endpoint_pattern' in modem.yaml",
            )

        if not self._params:
            return ActionResult(
                success=False,
                message="No restart params configured in modem.yaml actions.restart.params",
            )

        try:
            restart_url = endpoint if endpoint.startswith("http") else f"{base_url}{endpoint}"
            _LOGGER.info("%s: Sending restart command to %s", self._model, restart_url)

            response = session.post(restart_url, data=self._params, timeout=10)

            _LOGGER.debug(
                "%s: Restart response - status=%d, length=%d bytes",
                self._model,
                response.status_code,
                len(response.text) if response.text else 0,
            )

            if response.status_code == 200:
                _LOGGER.info("%s: Restart command accepted", self._model)
                return ActionResult(success=True, message="Restart command accepted")
            else:
                _LOGGER.warning(
                    "%s: Restart failed with status %d",
                    self._model,
                    response.status_code,
                )
                return ActionResult(
                    success=False,
                    message=f"Restart failed with status {response.status_code}",
                )

        except (RemoteDisconnected, ConnectionError, ChunkedEncodingError, ConnectionResetError) as e:
            # Connection dropped = modem is rebooting (success!)
            _LOGGER.info(
                "%s: Modem rebooting (connection dropped as expected): %s",
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

    def _resolve_endpoint(self, session: requests.Session, base_url: str) -> str:
        """Resolve the restart endpoint (static or dynamic).

        Args:
            session: Authenticated session
            base_url: Modem base URL

        Returns:
            Endpoint path (e.g., "/goform/RouterStatus?id=123") or empty string on failure
        """
        # Static endpoint takes precedence
        if self._endpoint:
            return str(self._endpoint)

        # Dynamic extraction from form action
        if self._endpoint_pattern and self._pre_fetch_url:
            return self._extract_endpoint_from_form(session, base_url)

        return ""

    def _extract_endpoint_from_form(self, session: requests.Session, base_url: str) -> str:
        """Extract endpoint from a form action in the pre-fetch page.

        Finds a <form> element whose action attribute contains the pattern,
        then returns the full action URL (which may include dynamic session IDs).

        Args:
            session: Authenticated session
            base_url: Modem base URL

        Returns:
            Form action URL or empty string if not found
        """
        try:
            pre_url = f"{base_url}{self._pre_fetch_url}"
            _LOGGER.debug("%s: Fetching %s to extract form action", self._model, pre_url)

            response = session.get(pre_url, timeout=10)
            if not response.ok:
                _LOGGER.warning(
                    "%s: Failed to fetch %s (status %d)",
                    self._model,
                    self._pre_fetch_url,
                    response.status_code,
                )
                return ""

            # Extract form action using regex (avoids BeautifulSoup dependency in core)
            # Pattern: <form ... action="..." ... > or <form ... action='...' ...>
            # We look for action containing our pattern
            form_action_pattern = re.compile(
                r'<form[^>]*\saction=["\']([^"\']*' + re.escape(self._endpoint_pattern) + r'[^"\']*)["\']',
                re.IGNORECASE,
            )

            match = form_action_pattern.search(response.text)
            if match:
                action = match.group(1)
                _LOGGER.debug("%s: Extracted form action: %s", self._model, action)
                return action

            _LOGGER.warning(
                "%s: No form with action containing '%s' found in %s",
                self._model,
                self._endpoint_pattern,
                self._pre_fetch_url,
            )
            return ""

        except Exception as e:
            _LOGGER.warning("%s: Error extracting form action: %s", self._model, str(e)[:100])
            return ""
