"""Config flow for Cable Modem Monitor integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_HISTORY_DAYS,
    CONF_SCAN_INTERVAL,
    DEFAULT_HISTORY_DAYS,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    DOMAIN,
)
from .modem_scraper import ModemScraper

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="192.168.100.1"): str,
        vol.Optional(CONF_USERNAME, default=""): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    host = data[CONF_HOST]
    username = data.get(CONF_USERNAME)
    password = data.get(CONF_PASSWORD)

    scraper = ModemScraper(host, username, password)

    # Test the connection
    try:
        modem_data = await hass.async_add_executor_job(scraper.get_modem_data)
    except Exception as err:
        _LOGGER.error(f"Error connecting to modem: {err}")
        raise CannotConnect from err

    if modem_data.get("connection_status") in ["offline", "unreachable"]:
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": f"Cable Modem ({host})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cable Modem Monitor."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Set unique ID to prevent duplicate entries
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Cable Modem Monitor."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_connection_settings()

    async def async_step_connection_settings(self, user_input=None):
        """Handle connection settings configuration."""
        errors = {}

        if user_input is not None:
            # Validate the connection with new settings
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Update the config entry with new data
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=user_input
                )
                return self.async_create_entry(title="", data={})

        # Pre-fill form with current values
        current_host = self.config_entry.data.get(CONF_HOST, "192.168.100.1")
        current_username = self.config_entry.data.get(CONF_USERNAME, "")
        current_history_days = self.config_entry.data.get(
            CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS
        )
        current_scan_interval = self.config_entry.data.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        options_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=current_host): str,
                vol.Optional(CONF_USERNAME, default=current_username): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Required(
                    CONF_SCAN_INTERVAL, default=current_scan_interval
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
                vol.Required(CONF_HISTORY_DAYS, default=current_history_days): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=365)
                ),
            }
        )

        return self.async_show_form(
            step_id="connection_settings",
            data_schema=options_schema,
            errors=errors,
            description_placeholders={
                "current_host": current_host,
                "current_username": current_username,
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
