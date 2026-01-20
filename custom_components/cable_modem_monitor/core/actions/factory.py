"""Factory for creating modem action instances.

The ActionFactory creates restart actions based on modem.yaml configuration.
Actions are the single source of truth for capability support.

HARD BOUNDARIES - This integration is read-only except for restart:
- Factory reset: NEVER (destructive, data loss)
- Password changes: NEVER (security risk)
- Configuration changes: NEVER
"""

from __future__ import annotations

import logging
from typing import Any

from .base import ActionType, ModemAction
from .hnap import HNAPRestartAction
from .html import HTMLRestartAction
from .rest import RESTRestartAction

_LOGGER = logging.getLogger(__name__)


class ActionFactory:
    """Factory for creating modem action instances.

    Actions are defined in modem.yaml under the `actions` key:

        actions:
          restart:
            type: hnap | html_form | rest_api
            action_name: "Reboot"        # HNAP
            endpoint: "/goform/restart"  # HTML/REST

    The `supports()` method checks if an action exists.
    The `create_*_action()` methods create action instances.
    """

    @staticmethod
    def supports(action_type: ActionType, modem_config: dict[str, Any]) -> bool:
        """Check if modem supports an action type.

        This is the single source of truth for capability checks.
        If actions.restart exists in modem.yaml, restart is supported.

        Args:
            action_type: Type of action to check
            modem_config: Full modem configuration from modem.yaml

        Returns:
            True if action is supported, False otherwise
        """
        if action_type == ActionType.RESTART:
            actions = modem_config.get("actions") or {}
            restart_config = actions.get("restart")
            return restart_config is not None

        return False

    @staticmethod
    def create_restart_action(modem_config: dict[str, Any]) -> ModemAction | None:
        """Create a restart action for the modem.

        Uses the `type` field in actions.restart to determine which
        action class to instantiate:
        - type: hnap -> HNAPRestartAction
        - type: html_form -> HTMLRestartAction
        - type: rest_api -> RESTRestartAction

        Args:
            modem_config: Full modem configuration from modem.yaml

        Returns:
            ModemAction instance, or None if restart not configured
        """
        # Get restart config from unified location
        actions_config = modem_config.get("actions") or {}
        restart_config = actions_config.get("restart")

        if not restart_config:
            _LOGGER.debug("No actions.restart configured in modem.yaml")
            return None

        # Use type field to determine action class
        action_type = restart_config.get("type", "html_form")

        if action_type == "hnap":
            _LOGGER.debug("Creating HNAPRestartAction")
            return HNAPRestartAction(modem_config)

        if action_type == "html_form":
            _LOGGER.debug("Creating HTMLRestartAction")
            return HTMLRestartAction(modem_config)

        if action_type == "rest_api":
            _LOGGER.debug("Creating RESTRestartAction")
            return RESTRestartAction(modem_config)

        _LOGGER.warning("Unknown restart action type: %s", action_type)
        return None

    @staticmethod
    def create_action(
        action_type: ActionType,
        modem_config: dict[str, Any],
    ) -> ModemAction | None:
        """Create an action of the specified type.

        Args:
            action_type: Type of action to create
            modem_config: Full modem configuration from modem.yaml

        Returns:
            ModemAction instance, or None if action not supported
        """
        if action_type == ActionType.RESTART:
            return ActionFactory.create_restart_action(modem_config)

        # Only restart is supported - see module docstring for hard boundaries
        _LOGGER.warning("Unsupported action type: %s", action_type)
        return None
