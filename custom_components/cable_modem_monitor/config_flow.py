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
    CONF_SCAN_INTERVAL,
    CONF_MODEM_CHOICE,
    CONF_PARSER_NAME,
    CONF_DETECTED_MODEM,
    CONF_DETECTED_MANUFACTURER,
    CONF_WORKING_URL,
    CONF_LAST_DETECTION,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    DOMAIN,
)
from .core.modem_scraper import ModemScraper
from .parsers import get_parsers

_LOGGER = logging.getLogger(__name__)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    host = data[CONF_HOST]
    username = data.get(CONF_USERNAME)
    password = data.get(CONF_PASSWORD)
    modem_choice = data.get(CONF_MODEM_CHOICE)
    cached_url = data.get(CONF_WORKING_URL)
    cached_parser_name = data.get(CONF_PARSER_NAME)

    all_parsers = await hass.async_add_executor_job(get_parsers)

    ***REMOVED*** Determine which parser(s) to use based on user choice
    selected_parser = None
    parser_name_for_tier2 = None

    if modem_choice and modem_choice != "auto":
        ***REMOVED*** Tier 1: User explicitly selected a parser
        for parser_class in all_parsers:
            if parser_class.name == modem_choice:
                selected_parser = parser_class()  ***REMOVED*** Instantiate the parser
                _LOGGER.info(f"User selected parser: {selected_parser.name}")
                break
    else:
        ***REMOVED*** Tier 2/3: Auto mode - use cached parser name if available
        parser_name_for_tier2 = cached_parser_name

    scraper = ModemScraper(
        host,
        username,
        password,
        parser=selected_parser if selected_parser else all_parsers,
        cached_url=cached_url,
        parser_name=parser_name_for_tier2,
    )

    try:
        modem_data = await hass.async_add_executor_job(scraper.get_modem_data)
    except Exception as err:
        _LOGGER.error(f"Error connecting to modem: {err}")
        raise CannotConnect from err

    if modem_data.get("connection_status") in ["offline", "unreachable"]:
        raise CannotConnect

    ***REMOVED*** Get detection info to store for future use
    detection_info = scraper.get_detection_info()

    ***REMOVED*** Return info that you want to store in the config entry.
    return {
        "title": f"Cable Modem ({host})",
        "detection_info": detection_info,
    }


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

        ***REMOVED*** Get parsers for the dropdown
        parsers = await self.hass.async_add_executor_job(get_parsers)
        modem_choices = ["auto"] + [p.name for p in parsers]

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  ***REMOVED*** pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                ***REMOVED*** Set unique ID to prevent duplicate entries
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()

                ***REMOVED*** Add default values for fields not in initial setup
                user_input.setdefault(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

                ***REMOVED*** Store detection info from validation
                detection_info = info.get("detection_info", {})
                if detection_info:
                    detected_modem_name = detection_info.get("modem_name")
                    user_input[CONF_PARSER_NAME] = detected_modem_name  ***REMOVED*** Cache parser name
                    user_input[CONF_DETECTED_MODEM] = detection_info.get("modem_name", "Unknown")
                    user_input[CONF_DETECTED_MANUFACTURER] = detection_info.get("manufacturer", "Unknown")
                    user_input[CONF_WORKING_URL] = detection_info.get("successful_url")
                    from datetime import datetime
                    user_input[CONF_LAST_DETECTION] = datetime.now().isoformat()

                    ***REMOVED*** If user selected "auto", update the choice to show what was detected
                    if user_input.get(CONF_MODEM_CHOICE) == "auto" and detected_modem_name:
                        user_input[CONF_MODEM_CHOICE] = detected_modem_name

                return self.async_create_entry(title=info["title"], data=user_input)

        from homeassistant.helpers import selector

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default="192.168.100.1"): str,
                vol.Optional(CONF_USERNAME, default=""): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Required(CONF_MODEM_CHOICE, default="auto"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=modem_choices,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Cable Modem Monitor."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        ***REMOVED*** Get parsers for the dropdown
        parsers = await self.hass.async_add_executor_job(get_parsers)
        modem_choices = ["auto"] + [p.name for p in parsers]

        if user_input is not None:
            ***REMOVED*** Validate the connection with new settings
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  ***REMOVED*** pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                ***REMOVED*** Preserve existing password if user left it blank
                if not user_input.get(CONF_PASSWORD):
                    user_input[CONF_PASSWORD] = self.config_entry.data.get(CONF_PASSWORD, "")

                ***REMOVED*** Update detection info from validation
                detection_info = info.get("detection_info", {})
                if detection_info:
                    detected_modem_name = detection_info.get("modem_name")
                    user_input[CONF_PARSER_NAME] = detected_modem_name  ***REMOVED*** Cache parser name
                    user_input[CONF_DETECTED_MODEM] = detection_info.get("modem_name", "Unknown")
                    user_input[CONF_DETECTED_MANUFACTURER] = detection_info.get("manufacturer", "Unknown")
                    user_input[CONF_WORKING_URL] = detection_info.get("successful_url")
                    from datetime import datetime
                    user_input[CONF_LAST_DETECTION] = datetime.now().isoformat()

                    ***REMOVED*** If user selected "auto", update the choice to show what was detected
                    if user_input.get(CONF_MODEM_CHOICE) == "auto" and detected_modem_name:
                        user_input[CONF_MODEM_CHOICE] = detected_modem_name
                else:
                    ***REMOVED*** Preserve existing detection info if validation didn't return new info
                    user_input[CONF_PARSER_NAME] = self.config_entry.data.get(CONF_PARSER_NAME)
                    user_input[CONF_DETECTED_MODEM] = self.config_entry.data.get(CONF_DETECTED_MODEM, "Unknown")
                    user_input[CONF_DETECTED_MANUFACTURER] = self.config_entry.data.get(
                        CONF_DETECTED_MANUFACTURER, "Unknown"
                    )
                    user_input[CONF_WORKING_URL] = self.config_entry.data.get(CONF_WORKING_URL)
                    user_input[CONF_LAST_DETECTION] = self.config_entry.data.get(CONF_LAST_DETECTION)

                ***REMOVED*** Update the config entry with all settings
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=user_input
                )
                return self.async_create_entry(title="", data={})

        ***REMOVED*** Pre-fill form with current values
        current_host = self.config_entry.data.get(CONF_HOST, "192.168.100.1")
        current_username = self.config_entry.data.get(CONF_USERNAME, "")
        current_modem_choice = self.config_entry.data.get(CONF_MODEM_CHOICE, "auto")
        current_scan_interval = self.config_entry.data.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        ***REMOVED*** Get detection info for display
        detected_modem = self.config_entry.data.get(CONF_DETECTED_MODEM, "Not detected")
        detected_manufacturer = self.config_entry.data.get(CONF_DETECTED_MANUFACTURER, "Unknown")
        last_detection = self.config_entry.data.get(CONF_LAST_DETECTION, "Never")

        ***REMOVED*** Format last detection time if available
        if last_detection and last_detection != "Never":
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(last_detection)
                last_detection = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

        from homeassistant.helpers import selector

        options_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=current_host): str,
                vol.Optional(CONF_USERNAME, default=current_username): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Required(CONF_MODEM_CHOICE, default=current_modem_choice): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=modem_choices,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=current_scan_interval
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
            description_placeholders={
                "current_host": current_host,
                "current_username": current_username,
                "detected_modem": detected_modem,
                "detected_manufacturer": detected_manufacturer,
                "last_detection": last_detection,
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
