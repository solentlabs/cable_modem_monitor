"""Bundled Cable Modem Lovelace card: the one entry point the integration calls.

Everything the card needs lives under this package; the rest of the
integration touches it only through ``async_register_card``. The card is
additive: nothing here may stop the modem integration from loading. See
DASHBOARD_CARD_SPEC.md § Boundary.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import websocket_api
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from ..const import VERSION
from .commands import ws_card_config

_LOGGER = logging.getLogger(__name__)

CARD_URL_BASE = "/cable_modem_monitor/card"
CARD_MODULE = "cable-modem-card.js"
_FRONTEND_DIR = Path(__file__).parent / "frontend"


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve and load the card and register its command (once, from async_setup)."""
    # A headless HA has no frontend or http; the card is skipped, not the integration.
    if "frontend" not in hass.config.components or "http" not in hass.config.components:
        _LOGGER.debug("Cable Modem card not registered: frontend or http is not loaded")
        return
    try:
        websocket_api.async_register_command(hass, ws_card_config)
        # The version query busts the browser cache on upgrade; HA keeps the
        # URL in memory only, so this runs on every start.
        await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL_BASE, str(_FRONTEND_DIR), False)])
        add_extra_js_url(hass, f"{CARD_URL_BASE}/{CARD_MODULE}?v={VERSION}")
    except (
        Exception
    ):  # noqa: BLE001  # rationale: the card is additive; any registration failure must not stop modem monitoring from loading
        _LOGGER.warning("Cable Modem card could not be registered; monitoring is unaffected", exc_info=True)
