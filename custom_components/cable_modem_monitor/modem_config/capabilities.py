"""Modem capability checking utilities.

Provides functions to check what capabilities a modem supports.
ActionFactory.supports() is the single source of truth - if actions.restart
exists in modem.yaml, restart is supported.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from ..core.actions import ActionFactory
from ..core.actions.base import ActionType
from ..parsers import get_parser_by_name
from .adapter import get_auth_adapter_for_parser

_LOGGER = logging.getLogger(__name__)


async def check_restart_support(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Check if modem supports restart via ActionFactory.

    ActionFactory.supports() is the single source of truth:
    - If actions.restart exists in modem.yaml, restart is supported
    - No separate capabilities list check needed

    This runs in an executor because modem.yaml loading does file I/O.

    Args:
        hass: Home Assistant instance
        entry: Config entry with modem configuration

    Returns:
        True if modem supports remote restart, False otherwise
    """
    parser_name = entry.data.get("parser_name", "")
    detected_modem = entry.data.get("detected_modem", "")

    # Fallback mode doesn't support restart
    if "Fallback Mode" in parser_name or "Unknown" in detected_modem:
        return False

    # Get the parser class name to look up modem.yaml
    modem_choice = entry.data.get("modem_choice", "")
    if not modem_choice or modem_choice == "auto":
        # Auto-detected: use parser_name which is the class name
        modem_choice = parser_name

    if not modem_choice:
        return False

    def check_restart_capability() -> bool:
        """Check modem.yaml for restart capability (blocking I/O)."""
        try:
            # Get parser class to find its class name
            parser_class = get_parser_by_name(modem_choice)
            if not parser_class:
                _LOGGER.debug("Parser %s not found", modem_choice)
                return False

            # Get modem.yaml adapter
            adapter = get_auth_adapter_for_parser(parser_class.__name__)
            if not adapter:
                _LOGGER.debug("No modem.yaml adapter for %s", parser_class.__name__)
                return False

            # ActionFactory.supports() is the single source of truth
            modem_config = adapter.get_modem_config_dict()
            if ActionFactory.supports(ActionType.RESTART, modem_config):
                _LOGGER.debug("Restart supported for %s", modem_choice)
                return True

            _LOGGER.debug("Restart not configured in actions.restart for %s", modem_choice)
            return False

        except Exception as e:
            _LOGGER.debug("Error checking restart support for %s: %s", modem_choice, e)
            return False

    return bool(await hass.async_add_executor_job(check_restart_capability))
