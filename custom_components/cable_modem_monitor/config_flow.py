"""Config flow for Cable Modem Monitor integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_DETECTED_MANUFACTURER,
    CONF_DETECTED_MODEM,
    CONF_HOST,
    CONF_LAST_DETECTION,
    CONF_MODEM_CHOICE,
    CONF_PARSER_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_WORKING_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    VERIFY_SSL,
)
from .core.discovery_helpers import ParserNotFoundError
from .core.modem_scraper import ModemScraper
from .parsers import get_parsers

_LOGGER = logging.getLogger(__name__)


def _validate_host_format(host: str) -> str:
    """Validate and extract hostname from host string.

    Returns the cleaned hostname.
    Raises ValueError if validation fails.
    """
    import re
    from urllib.parse import urlparse

    if not host:
        raise ValueError("Host cannot be empty")

    host_clean = host.strip()

    # Extract hostname from URL if provided
    if host_clean.startswith(("http://", "https://")):
        try:
            parsed = urlparse(host_clean)
            if parsed.scheme not in ["http", "https"]:
                raise ValueError("Only HTTP and HTTPS protocols are allowed")
            if not parsed.netloc:
                raise ValueError("Invalid URL format")
            hostname = parsed.hostname or parsed.netloc.split(":")[0]
        except Exception as err:
            raise ValueError(f"Invalid URL format: {err}") from err
    else:
        hostname = host_clean

    # Security: Block shell metacharacters
    invalid_chars = [";", "&", "|", "$", "`", "\n", "\r", "\t", "<", ">", "(", ")", "{", "}", "\\"]
    if any(char in hostname for char in invalid_chars):
        raise ValueError("Invalid characters in host address")

    # Validate format: IPv4, IPv6, or valid hostname
    patterns = {
        "ipv4": r"^(\d{1,3}\.){3}\d{1,3}$",
        "ipv6": r"^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$",
        "hostname": (
            r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?" r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$"
        ),
    }

    if not any(re.match(pattern, hostname) for pattern in patterns.values()):
        raise ValueError("Invalid host format. Must be a valid IP address or hostname")

    return hostname


def _select_parser_for_validation(
    all_parsers: list, modem_choice: str | None, cached_parser_name: str | None
) -> tuple[Any | None, str | None]:
    """Select parser(s) for validation.

    Args:
        all_parsers: List of available parser classes
        modem_choice: User-selected parser name or None/auto for auto-detection
        cached_parser_name: Previously detected parser name or None

    Returns:
        tuple of (selected_parser, parser_name_hint) where:
        - selected_parser: ModemParser instance or None if using auto-detection
        - parser_name_hint: Cached parser name or None
    """
    if modem_choice and modem_choice != "auto":
        # User explicitly selected a parser
        for parser_class in all_parsers:
            if parser_class.name == modem_choice:
                _LOGGER.info("User selected parser: %s", parser_class.name)
                return parser_class(), None
        return None, None
    else:
        # Auto mode - use all parsers with cached name hint
        _LOGGER.info("Using auto-detection mode (modem_choice=%s, cached_parser=%s)", modem_choice, cached_parser_name)
        if cached_parser_name:
            _LOGGER.info("Will try cached parser first: %s", cached_parser_name)
        else:
            _LOGGER.info("No cached parser, will try all available parsers")
        return None, cached_parser_name


def _create_title(detection_info: dict, host: str) -> str:
    """Create user-friendly title from detection info."""
    detected_modem = detection_info.get("modem_name", "Cable Modem")
    detected_manufacturer = detection_info.get("manufacturer", "")

    # Avoid duplicate manufacturer name if already in modem name
    if (
        detected_manufacturer
        and detected_manufacturer != "Unknown"
        and not detected_modem.startswith(detected_manufacturer)
    ):
        return f"{detected_manufacturer} {detected_modem} ({host})"
    else:
        return f"{detected_modem} ({host})"


async def _connect_to_modem(hass: HomeAssistant, scraper) -> dict[str, Any]:
    """Attempt to connect to modem and get data.

    Returns modem_data dict.
    Raises CannotConnectError, InvalidAuthError, or UnsupportedModemError on failure.
    """
    try:
        modem_data: dict[str, Any] = await hass.async_add_executor_job(scraper.get_modem_data)
    except ParserNotFoundError as err:
        _LOGGER.error("Unsupported modem detected: %s", err.get_user_message())
        _LOGGER.info("Attempted parsers: %s", ", ".join(err.attempted_parsers))
        _LOGGER.info(
            "Troubleshooting steps:\n%s",
            "\n".join(f"  {i+1}. {step}" for i, step in enumerate(err.get_troubleshooting_steps())),
        )
        raise UnsupportedModemError(str(err)) from err
    except Exception as err:
        _LOGGER.error("Error connecting to modem: %s", err)
        raise CannotConnectError from err

    # Check for authentication failures (login page detected)
    if modem_data.get("_auth_failure") or modem_data.get("_login_page_detected"):
        _LOGGER.error(
            "Authentication failure detected. Modem returned login page. " "Diagnostic context: %s",
            modem_data.get("_diagnostic_context", {}),
        )
        raise InvalidAuthError("Received login page - please check username and password")

    # Allow installation for various status levels:
    # - "online": Normal operation with channel data
    # - "limited": Fallback mode (unsupported modem)
    # - "parser_issue": Known parser but no channel data (bridge mode, parser bug, etc.)
    # Only reject truly offline/unreachable modems
    status = modem_data.get("cable_modem_connection_status")
    if status in ["offline", "unreachable"]:
        raise CannotConnectError

    return modem_data


def _do_quick_connectivity_check(host: str) -> tuple[bool, str | None]:
    """Perform quick HTTP connectivity check to modem (sync version for executor).

    Args:
        host: Modem IP address or hostname

    Returns:
        tuple of (is_reachable, error_message)
        - (True, None) if modem responds to HTTP request
        - (False, error_message) if unreachable with specific reason
    """
    import requests

    # Determine base URL - try HTTPS first like main scraper
    if host.startswith(("http://", "https://")):
        test_urls = [host]
    else:
        test_urls = [f"https://{host}", f"http://{host}"]

    # Disable SSL warnings for this test
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    for test_url in test_urls:
        try:
            # Quick HEAD request with short timeout
            # Security justification: Cable modems use self-signed certificates on private LAN (192.168.x.x, 10.x.x.x)
            # This is a pre-flight connectivity check only - actual data fetching uses proper SSL validation
            response = requests.head(
                test_url, timeout=2, verify=False, allow_redirects=True
            )  # nosec: cable modem self-signed cert
            # Any response (200, 401, 403, etc.) means modem is reachable
            _LOGGER.debug("Quick connectivity check passed: %s returned status %d", test_url, response.status_code)
            return True, None
        except requests.exceptions.Timeout:
            _LOGGER.debug("Quick connectivity check timeout for %s", test_url)
            continue
        except requests.exceptions.ConnectionError as e:
            _LOGGER.debug("Quick connectivity check connection error for %s: %s", test_url, e)
            continue
        except Exception as e:
            _LOGGER.debug("Quick connectivity check failed for %s: %s", test_url, e)
            continue

    # All attempts failed
    error_msg = (
        f"Cannot reach modem at {host}. "
        f"Please check: (1) Network connection - ensure you're on the correct network, "
        f"not on guest WiFi or VPN. (2) Modem IP address is correct. "
        f"(3) Modem web interface is enabled."
    )
    return False, error_msg


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    # Validate host format
    host = data[CONF_HOST]
    _validate_host_format(host)

    # Quick connectivity pre-check (run in executor to avoid blocking)
    _LOGGER.info("Performing quick connectivity check to %s", host)
    is_reachable, error_msg = await hass.async_add_executor_job(_do_quick_connectivity_check, host)
    if not is_reachable:
        _LOGGER.error("Quick connectivity check failed: %s", error_msg)
        raise CannotConnectError(error_msg)

    # Get parsers and select appropriate one(s)
    all_parsers = await hass.async_add_executor_job(get_parsers)
    selected_parser, parser_name_hint = _select_parser_for_validation(
        all_parsers, data.get(CONF_MODEM_CHOICE), data.get(CONF_PARSER_NAME)
    )

    # Create scraper
    scraper = ModemScraper(
        host,
        data.get(CONF_USERNAME),
        data.get(CONF_PASSWORD),
        parser=selected_parser if selected_parser else all_parsers,
        cached_url=data.get(CONF_WORKING_URL),
        parser_name=parser_name_hint,
        verify_ssl=VERIFY_SSL,
    )

    # Connect and validate
    _LOGGER.info("Attempting to connect to modem at %s", host)
    await _connect_to_modem(hass, scraper)

    # Get detection info and create title
    detection_info = scraper.get_detection_info()
    _LOGGER.info("Detection successful: %s", detection_info)
    title = _create_title(detection_info, host)

    return {
        "title": title,
        "detection_info": detection_info,
    }


@config_entries.HANDLERS.register(DOMAIN)
class CableModemMonitorConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for Cable Modem Monitor."""

    VERSION = 1

    def __init__(self):
        """Initialize config flow."""
        self._user_input: dict[str, Any] | None = None
        self._validation_task: Any = None
        self._validation_error: Exception | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def async_step_user(  # noqa: C901  # noqa: C901
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        # When coming back from progress step, restore user input
        if user_input is None and self._user_input:
            user_input = self._user_input

        # Get parsers for the dropdown
        parsers = await self.hass.async_add_executor_job(get_parsers)

        # Sort by manufacturer (alphabetical), then by name (alphabetical)
        # Generic parsers appear last within their manufacturer group
        # Unknown/Fallback parsers appear at the very end
        def sort_key(p):
            # Unknown manufacturer goes last
            if p.manufacturer == "Unknown":
                return ("ZZZZ", "ZZZZ")  # Sort to end
            # Within each manufacturer, Generic parsers go last
            if "Generic" in p.name:
                return (p.manufacturer, "ZZZZ")  # Generic last in manufacturer
            # Regular parsers sort by manufacturer then name
            return (p.manufacturer, p.name)

        sorted_parsers = sorted(parsers, key=sort_key)
        modem_choices = ["auto"] + [p.name for p in sorted_parsers]

        if user_input is not None:
            # Store user input and start validation with progress
            self._user_input = user_input
            return await self.async_step_validate()

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

        return self.async_show_form(step_id="user", data_schema=data_schema, errors={})

    async def async_step_validate(  # noqa: C901
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle validation with progress indicator."""
        if not self._validation_task:
            if not self._user_input:
                return self.async_abort(reason="missing_input")
            self._validation_task = self.hass.async_create_task(validate_input(self.hass, self._user_input))

        if not self._validation_task.done():
            return self.async_show_progress(
                step_id="validate",
                progress_action="validate",
                progress_task=self._validation_task,
            )

        errors: dict[str, str] = {}
        info: dict[str, Any] | None = None
        try:
            info = await self._validation_task
        except InvalidAuthError as err:
            errors["base"] = "invalid_auth"
            self._validation_error = err
        except UnsupportedModemError as err:
            errors["base"] = "unsupported_modem"
            self._validation_error = err
        except CannotConnectError as err:
            # Use detailed error message if available, otherwise use generic error
            if hasattr(err, "user_message") and err.user_message:
                errors["base"] = "network_unreachable"
            else:
                errors["base"] = "cannot_connect"
            self._validation_error = err
        except (ValueError, TypeError) as err:
            _LOGGER.error("Invalid input data: %s", err)
            errors["base"] = "invalid_input"
            self._validation_error = err
        except Exception as err:
            # Log exception details for debugging, but sanitize error shown to user
            _LOGGER.exception("Unexpected exception during validation")
            errors["base"] = "unknown"
            self._validation_error = err
        finally:
            self._validation_task = None

        if errors or not info:
            # Return to user form with errors
            return self.async_show_progress_done(next_step_id="user_with_errors")

        # Validation successful - complete setup
        if not self._user_input:
            return self.async_abort(reason="missing_input")

        user_input = self._user_input
        self._user_input = None

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
                _LOGGER.info(
                    "Auto-detection successful: updating modem_choice from 'auto' to '%s'", detected_modem_name
                )
                user_input[CONF_MODEM_CHOICE] = detected_modem_name

        return self.async_create_entry(title=info["title"], data=user_input)

    async def async_step_user_with_errors(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show form again with errors after validation failure."""
        # Get parsers for the dropdown
        parsers = await self.hass.async_add_executor_job(get_parsers)

        def sort_key(p):
            if p.manufacturer == "Unknown":
                return ("ZZZZ", "ZZZZ")
            if "Generic" in p.name:
                return (p.manufacturer, "ZZZZ")
            return (p.manufacturer, p.name)

        sorted_parsers = sorted(parsers, key=sort_key)
        modem_choices = ["auto"] + [p.name for p in sorted_parsers]

        from homeassistant.helpers import selector

        # Get the stored user input and errors
        saved_input = self._user_input or {}
        errors = {"base": "cannot_connect"}  # Default error

        # Extract specific error from saved validation error
        if self._validation_error:
            if isinstance(self._validation_error, InvalidAuthError):
                errors["base"] = "invalid_auth"
            elif isinstance(self._validation_error, UnsupportedModemError):
                errors["base"] = "unsupported_modem"
            elif isinstance(self._validation_error, CannotConnectError):
                if hasattr(self._validation_error, "user_message") and self._validation_error.user_message:
                    errors["base"] = "network_unreachable"
                else:
                    errors["base"] = "cannot_connect"
            elif isinstance(self._validation_error, ValueError | TypeError):
                errors["base"] = "invalid_input"
            else:
                errors["base"] = "unknown"

        # Reset for next attempt
        self._user_input = None
        self._validation_task = None
        self._validation_error = None

        # Preserve user input when showing form again after error
        default_host = saved_input.get(CONF_HOST, "192.168.100.1")
        default_username = saved_input.get(CONF_USERNAME, "")
        default_password = saved_input.get(CONF_PASSWORD, "")
        default_modem = saved_input.get(CONF_MODEM_CHOICE, "auto")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=default_host): str,
                vol.Optional(CONF_USERNAME, default=default_username): str,
                vol.Optional(CONF_PASSWORD, default=default_password): str,
                vol.Required(CONF_MODEM_CHOICE, default=default_modem): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=modem_choices,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Cable Modem Monitor."""

    def _preserve_credentials(self, user_input: dict[str, Any]) -> None:
        """Preserve existing credentials if not provided in user input."""
        if not user_input.get(CONF_PASSWORD):
            user_input[CONF_PASSWORD] = self.config_entry.data.get(CONF_PASSWORD, "")
        if not user_input.get(CONF_USERNAME):
            user_input[CONF_USERNAME] = self.config_entry.data.get(CONF_USERNAME, "")

    def _update_detection_info(self, user_input: dict[str, Any], info: dict) -> None:
        """Update user input with detection info from validation."""
        detection_info = info.get("detection_info", {})
        if detection_info:
            detected_modem_name = detection_info.get("modem_name")
            user_input[CONF_PARSER_NAME] = detected_modem_name
            user_input[CONF_DETECTED_MODEM] = detection_info.get("modem_name", "Unknown")
            user_input[CONF_DETECTED_MANUFACTURER] = detection_info.get("manufacturer", "Unknown")
            user_input[CONF_WORKING_URL] = detection_info.get("successful_url")
            from datetime import datetime

            user_input[CONF_LAST_DETECTION] = datetime.now().isoformat()

            # If user selected "auto", update choice to show what was detected
            if user_input.get(CONF_MODEM_CHOICE) == "auto" and detected_modem_name:
                _LOGGER.info(
                    "Auto-detection successful in options flow: updating modem_choice from 'auto' to '%s'",
                    detected_modem_name,
                )
                user_input[CONF_MODEM_CHOICE] = detected_modem_name
        else:
            # Preserve existing detection info if validation didn't return new info
            user_input[CONF_PARSER_NAME] = self.config_entry.data.get(CONF_PARSER_NAME)
            user_input[CONF_DETECTED_MODEM] = self.config_entry.data.get(CONF_DETECTED_MODEM, "Unknown")
            user_input[CONF_DETECTED_MANUFACTURER] = self.config_entry.data.get(CONF_DETECTED_MANUFACTURER, "Unknown")
            user_input[CONF_WORKING_URL] = self.config_entry.data.get(CONF_WORKING_URL)
            user_input[CONF_LAST_DETECTION] = self.config_entry.data.get(CONF_LAST_DETECTION)

    def _create_config_message(self, user_input: dict[str, Any]) -> str:
        """Create configuration message from detected modem info."""
        detected_modem = user_input.get(CONF_DETECTED_MODEM, "Cable Modem")
        detected_manufacturer = user_input.get(CONF_DETECTED_MANUFACTURER, "")

        # Avoid duplicate manufacturer name if modem name already includes it
        if (
            detected_manufacturer
            and detected_manufacturer != "Unknown"
            and not detected_modem.startswith(detected_manufacturer)
        ):
            return f"Configured for {detected_manufacturer} {detected_modem}"
        else:
            return f"Configured for {detected_modem}"

    async def async_step_init(  # noqa: C901  # noqa: C901
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        errors = {}

        # Get parsers for the dropdown
        parsers = await self.hass.async_add_executor_job(get_parsers)

        # Sort by manufacturer (alphabetical), then by name (alphabetical)
        # Generic parsers appear last within their manufacturer group
        # Unknown/Fallback parsers appear at the very end
        def sort_key(p):
            # Unknown manufacturer goes last
            if p.manufacturer == "Unknown":
                return ("ZZZZ", "ZZZZ")  # Sort to end
            # Within each manufacturer, Generic parsers go last
            if "Generic" in p.name:
                return (p.manufacturer, "ZZZZ")  # Generic last in manufacturer
            # Regular parsers sort by manufacturer then name
            return (p.manufacturer, p.name)

        sorted_parsers = sorted(parsers, key=sort_key)
        modem_choices = ["auto"] + [p.name for p in sorted_parsers]

        if user_input is not None:
            # Preserve existing credentials if not provided
            self._preserve_credentials(user_input)

            # Validate the connection with new settings
            try:
                info = await validate_input(self.hass, user_input)
            except UnsupportedModemError:
                errors["base"] = "unsupported_modem"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except (ValueError, TypeError) as err:
                _LOGGER.error("Invalid input data in options flow: %s", err)
                errors["base"] = "invalid_input"
            except Exception:
                _LOGGER.exception("Unexpected exception during options validation")
                errors["base"] = "unknown"
            else:
                # Update detection info from validation
                self._update_detection_info(user_input, info)

                # Update the config entry with all settings
                self.hass.config_entries.async_update_entry(self.config_entry, data=user_input)

                # Create notification with detected modem info
                message = self._create_config_message(user_input)
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
        current_scan_interval = self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

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
                vol.Required(CONF_SCAN_INTERVAL, default=current_scan_interval): vol.All(
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


class CannotConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""

    def __init__(self, message: str | None = None):
        """Initialize error with optional message."""
        super().__init__(message or "Cannot connect to modem")
        self.user_message = message


class InvalidAuthError(HomeAssistantError):
    """Error to indicate authentication failed."""


class UnsupportedModemError(HomeAssistantError):
    """Error to indicate modem is not supported (no parser matches)."""
