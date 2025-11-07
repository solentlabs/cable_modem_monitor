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
    VERIFY_SSL,
)
from .core.modem_scraper import ModemScraper
from .core.discovery_helpers import ParserNotFoundError
from .parsers import get_parsers

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    from urllib.parse import urlparse
    import re

    host = data[CONF_HOST]

    # Security: Validate host format to prevent injection attacks
    if not host:
        raise ValueError("Host cannot be empty")

    # Validate host format (IP address, hostname, or URL)
    host_clean = host.strip()

    # Check for URL format
    if host_clean.startswith(('http://', 'https://')):
        try:
            parsed = urlparse(host_clean)
            if parsed.scheme not in ['http', 'https']:
                raise ValueError("Only HTTP and HTTPS protocols are allowed")
            if not parsed.netloc:
                raise ValueError("Invalid URL format")
            # Extract hostname for additional validation
            hostname = parsed.hostname or parsed.netloc.split(':')[0]
        except Exception as err:
            raise ValueError(f"Invalid URL format: {err}")
    else:
        hostname = host_clean

    # Validate hostname/IP format to prevent command injection
    # Block shell metacharacters
    invalid_chars = [';', '&', '|', '$', '`', '\n', '\r', '\t', '<', '>', '(', ')', '{', '}', '\\']
    if any(char in hostname for char in invalid_chars):
        raise ValueError("Invalid characters in host address")

    # Validate format: IPv4, IPv6, or valid hostname
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    ipv6_pattern = r'^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$'
    hostname_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'

    if not (re.match(ipv4_pattern, hostname) or
            re.match(ipv6_pattern, hostname) or
            re.match(hostname_pattern, hostname)):
        raise ValueError("Invalid host format. Must be a valid IP address or hostname")

    username = data.get(CONF_USERNAME)
    password = data.get(CONF_PASSWORD)
    modem_choice = data.get(CONF_MODEM_CHOICE)
    cached_url = data.get(CONF_WORKING_URL)
    cached_parser_name = data.get(CONF_PARSER_NAME)
    # Use hardcoded VERIFY_SSL constant (see const.py for rationale)
    verify_ssl = VERIFY_SSL

    all_parsers = await hass.async_add_executor_job(get_parsers)

    # Determine which parser(s) to use based on user choice
    selected_parser = None
    parser_name_for_tier2 = None

    if modem_choice and modem_choice != "auto":
        # Tier 1: User explicitly selected a parser
        for parser_class in all_parsers:
            if parser_class.name == modem_choice:
                selected_parser = parser_class()  # Instantiate the parser
                _LOGGER.info("User selected parser: %s", selected_parser.name)
                break
    else:
        # Tier 2/3: Auto mode - use cached parser name if available
        parser_name_for_tier2 = cached_parser_name

    scraper = ModemScraper(
        host,
        username,
        password,
        parser=selected_parser if selected_parser else all_parsers,
        cached_url=cached_url,
        parser_name=parser_name_for_tier2,
        verify_ssl=verify_ssl,
    )

    try:
        modem_data = await hass.async_add_executor_job(scraper.get_modem_data)
    except ParserNotFoundError as err:
        # Phase 3: Better error message for unsupported modems
        _LOGGER.error("Unsupported modem detected: %s", err.get_user_message())
        _LOGGER.info("Attempted parsers: %s", ", ".join(err.attempted_parsers))
        _LOGGER.info("Troubleshooting steps:\n%s",
                   "\n".join(f"  {i+1}. {step}" for i, step in enumerate(err.get_troubleshooting_steps())))
        raise UnsupportedModem(str(err)) from err
    except Exception as err:
        _LOGGER.error("Error connecting to modem: %s", err)
        raise CannotConnect from err

    if modem_data.get("cable_modem_connection_status") in ["offline", "unreachable"]:
        raise CannotConnect

    # Get detection info to store for future use
    detection_info = scraper.get_detection_info()

    # Create title with detected modem info
    detected_modem = detection_info.get("modem_name", "Cable Modem")
    detected_manufacturer = detection_info.get("manufacturer", "")

    # Avoid duplicate manufacturer name if modem name already includes it
    if (
        detected_manufacturer
        and detected_manufacturer != "Unknown"
        and not detected_modem.startswith(detected_manufacturer)
    ):
        title = f"{detected_manufacturer} {detected_modem} ({host})"
    else:
        title = f"{detected_modem} ({host})"

    # Return info that you want to store in the config entry.
    return {
        "title": title,
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

        # Get parsers for the dropdown
        parsers = await self.hass.async_add_executor_job(get_parsers)
        # Sort by manufacturer (alphabetical), then by priority (descending) within each manufacturer
        sorted_parsers = sorted(parsers, key=lambda p: (p.manufacturer, -p.priority))
        modem_choices = ["auto"] + [p.name for p in sorted_parsers]

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except UnsupportedModem:
                errors["base"] = "unsupported_modem"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except (ValueError, TypeError) as err:
                _LOGGER.error("Invalid input data: %s", err)
                errors["base"] = "invalid_input"
            except Exception as err:
                # Log exception details for debugging, but sanitize error shown to user
                _LOGGER.exception("Unexpected exception during validation")
                errors["base"] = "unknown"
            else:
                # Set unique ID to prevent duplicate entries
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()

                # Add default values for fields not in initial setup
                user_input.setdefault(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                # Note: VERIFY_SSL is now a hardcoded constant (see const.py)

                # Store detection info from validation
                detection_info = info.get("detection_info", {})
                if detection_info:
                    detected_modem_name = detection_info.get("modem_name")
                    user_input[CONF_PARSER_NAME] = detected_modem_name  # Cache parser name
                    user_input[CONF_DETECTED_MODEM] = detection_info.get("modem_name", "Unknown")
                    user_input[CONF_DETECTED_MANUFACTURER] = detection_info.get("manufacturer", "Unknown")
                    user_input[CONF_WORKING_URL] = detection_info.get("successful_url")
                    from datetime import datetime
                    user_input[CONF_LAST_DETECTION] = datetime.now().isoformat()

                    # If user selected "auto", update the choice to show what was detected
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

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        errors = {}

        # Get parsers for the dropdown
        parsers = await self.hass.async_add_executor_job(get_parsers)
        # Sort by manufacturer (alphabetical), then by priority (descending) within each manufacturer
        sorted_parsers = sorted(parsers, key=lambda p: (p.manufacturer, -p.priority))
        modem_choices = ["auto"] + [p.name for p in sorted_parsers]

        if user_input is not None:
            # Preserve existing password if user left it blank (BEFORE validation)
            if not user_input.get(CONF_PASSWORD):
                user_input[CONF_PASSWORD] = self.config_entry.data.get(CONF_PASSWORD, "")

            # Preserve existing username if user left it blank (BEFORE validation)
            if not user_input.get(CONF_USERNAME):
                user_input[CONF_USERNAME] = self.config_entry.data.get(CONF_USERNAME, "")

            # Validate the connection with new settings
            try:
                info = await validate_input(self.hass, user_input)
            except UnsupportedModem:
                errors["base"] = "unsupported_modem"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except (ValueError, TypeError) as err:
                _LOGGER.error("Invalid input data in options flow: %s", err)
                errors["base"] = "invalid_input"
            except Exception as err:
                # Log exception details for debugging, but sanitize error shown to user
                _LOGGER.exception("Unexpected exception during options validation")
                errors["base"] = "unknown"
            else:

                # Update detection info from validation
                detection_info = info.get("detection_info", {})
                if detection_info:
                    detected_modem_name = detection_info.get("modem_name")
                    user_input[CONF_PARSER_NAME] = detected_modem_name  # Cache parser name
                    user_input[CONF_DETECTED_MODEM] = detection_info.get("modem_name", "Unknown")
                    user_input[CONF_DETECTED_MANUFACTURER] = detection_info.get("manufacturer", "Unknown")
                    user_input[CONF_WORKING_URL] = detection_info.get("successful_url")
                    from datetime import datetime
                    user_input[CONF_LAST_DETECTION] = datetime.now().isoformat()

                    # If user selected "auto", update the choice to show what was detected
                    if user_input.get(CONF_MODEM_CHOICE) == "auto" and detected_modem_name:
                        user_input[CONF_MODEM_CHOICE] = detected_modem_name
                else:
                    # Preserve existing detection info if validation didn't return new info
                    user_input[CONF_PARSER_NAME] = self.config_entry.data.get(CONF_PARSER_NAME)
                    user_input[CONF_DETECTED_MODEM] = self.config_entry.data.get(CONF_DETECTED_MODEM, "Unknown")
                    user_input[CONF_DETECTED_MANUFACTURER] = self.config_entry.data.get(
                        CONF_DETECTED_MANUFACTURER, "Unknown"
                    )
                    user_input[CONF_WORKING_URL] = self.config_entry.data.get(CONF_WORKING_URL)
                    user_input[CONF_LAST_DETECTION] = self.config_entry.data.get(CONF_LAST_DETECTION)

                # Update the config entry with all settings
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=user_input
                )

                # Show notification with detected modem info
                detected_modem = user_input.get(CONF_DETECTED_MODEM, "Cable Modem")
                detected_manufacturer = user_input.get(CONF_DETECTED_MANUFACTURER, "")

                # Avoid duplicate manufacturer name if modem name already includes it
                if (
                    detected_manufacturer
                    and detected_manufacturer != "Unknown"
                    and not detected_modem.startswith(detected_manufacturer)
                ):
                    message = f"Configured for {detected_manufacturer} {detected_modem}"
                else:
                    message = f"Configured for {detected_modem}"

                # Create a notification to show the detected modem
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "Cable Modem Monitor",
                        "message": message,
                        "notification_id": f"cable_modem_config_{self.config_entry.entry_id}",
                    },
                )

                return self.async_create_entry(title="", data={})

        # Pre-fill form with current values
        current_host = self.config_entry.data.get(CONF_HOST, "192.168.100.1")
        current_username = self.config_entry.data.get(CONF_USERNAME, "")
        current_modem_choice = self.config_entry.data.get(CONF_MODEM_CHOICE, "auto")
        current_scan_interval = self.config_entry.data.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        # Get detection info for display
        detected_modem = self.config_entry.data.get(CONF_DETECTED_MODEM, "Not detected")
        detected_manufacturer = self.config_entry.data.get(CONF_DETECTED_MANUFACTURER, "Unknown")
        last_detection = self.config_entry.data.get(CONF_LAST_DETECTION, "Never")

        # Format last detection time if available
        if last_detection and last_detection != "Never":
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(last_detection)
                last_detection = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                # Invalid datetime format, keep original string
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


class UnsupportedModem(HomeAssistantError):
    """Error to indicate modem is not supported (no parser matches)."""
