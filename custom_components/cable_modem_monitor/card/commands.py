"""Websocket command that hands the Cable Modem card its layout.

See DASHBOARD_CARD_SPEC.md § Backend Access.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.decorators import websocket_command
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError

from ..dev_tools import build_card_config, card_watch_entities
from ..services import SERVICE_GENERATE_DASHBOARD_CARD_SCHEMA

CARD_CONFIG_COMMAND = "cable_modem_monitor/card_config"
ERR_CARD_UNAVAILABLE = "card_unavailable"


@websocket_command(
    {
        vol.Required("type"): CARD_CONFIG_COMMAND,
        # The generator's own options schema: one definition, defaults included.
        vol.Optional("options", default=dict): SERVICE_GENERATE_DASHBOARD_CARD_SCHEMA,
    }
)
@callback
def ws_card_config(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send the card dict and the entities that invalidate it, or the reason there is none."""
    try:
        card = build_card_config(hass, msg["options"])
        watch = card_watch_entities(hass, msg["options"])
    except ServiceValidationError as err:
        connection.send_error(msg["id"], ERR_CARD_UNAVAILABLE, str(err))
        return
    connection.send_result(msg["id"], {"card": card, "watch": watch})
