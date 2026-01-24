"""Config flow for Cable Modem Monitor integration.

This module handles the Home Assistant UI configuration wizard for adding
and modifying the cable modem monitor integration. It is the primary entry
point for users configuring the integration through the HA UI.

Structure:
    - ValidationProgressHelper: Manages async validation state with progress indicator
    - ConfigFlowMixin: Shared methods for building entry data from validation results
    - CableModemMonitorConfigFlow: Main setup wizard
    - OptionsFlowHandler: Reconfiguration flow

Flow Steps:
    Main Flow (CableModemMonitorConfigFlow):
        1. async_step_user - Collect host, credentials, parser choice
        2. async_step_validate - Show progress during validation
        3. async_step_validate_success - Create config entry on success
        4. async_step_user_with_errors - Re-show form on failure

    Options Flow (OptionsFlowHandler):
        1. async_step_init - Show current config with edit form
        2. async_step_options_validate - Validate changes with progress
        3. async_step_options_success - Update config entry on success
        4. async_step_options_with_errors - Re-show form on failure

Validation logic (validate_input, etc.) lives in config_flow_helpers.py.
Core utilities (exceptions, parser utils) live in core/ modules.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .config_flow_helpers import (
    build_parser_dropdown,
    classify_error,
    get_auth_type_dropdown,
    needs_auth_type_selection,
    validate_input,
)
from .const import (
    CONF_ACTUAL_MODEL,
    CONF_AUTH_DISCOVERY_ERROR,
    CONF_AUTH_DISCOVERY_FAILED,
    CONF_AUTH_DISCOVERY_STATUS,
    CONF_AUTH_FORM_CONFIG,
    CONF_AUTH_HNAP_CONFIG,
    CONF_AUTH_STRATEGY,
    CONF_AUTH_TYPE,
    CONF_AUTH_URL_TOKEN_CONFIG,
    CONF_DETECTED_MANUFACTURER,
    CONF_DETECTED_MODEM,
    CONF_DOCSIS_VERSION,
    CONF_ENTITY_PREFIX,
    CONF_HOST,
    CONF_LEGACY_SSL,
    CONF_MODEM_CHOICE,
    CONF_PARSER_NAME,
    CONF_PARSER_SELECTED_AT,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SUPPORTS_ICMP,
    CONF_USERNAME,
    CONF_WORKING_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENTITY_PREFIX_IP,
    ENTITY_PREFIX_MODEL,
    ENTITY_PREFIX_NONE,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .core.exceptions import (
    CannotConnectError,
    InvalidAuthError,
    UnsupportedModemError,
)
from .core.parser_utils import create_title

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# Validation Progress Helper
# =============================================================================


class ValidationProgressHelper:
    """Manages async validation state for progress indicator flows.

    HA config flows support showing a progress spinner during long-running
    validation. This helper encapsulates the task state, result caching,
    and error handling needed for that pattern.

    Used by both CableModemMonitorConfigFlow and OptionsFlowHandler.

    Attributes:
        user_input: The form data being validated.
        task: The running asyncio.Task, or None.
        error: The caught exception if validation failed, or None.
        info: The validation result dict if successful, or None.
    """

    def __init__(self) -> None:
        """Initialize with empty state."""
        self.user_input: dict[str, Any] | None = None
        self.task: asyncio.Task | None = None
        self.error: Exception | None = None
        self.info: dict[str, Any] | None = None

    def start(self, hass: HomeAssistant, user_input: dict[str, Any]) -> None:
        """Start the validation task.

        Args:
            hass: Home Assistant instance for task creation.
            user_input: Form data to validate.
        """
        self.user_input = user_input
        self.task = hass.async_create_task(validate_input(hass, user_input))

    def is_running(self) -> bool:
        """Check if validation task is still running."""
        return self.task is not None and not self.task.done()

    async def get_result(self) -> str | None:
        """Wait for task completion and return error type if failed.

        Returns:
            None if validation succeeded (result stored in self.info).
            Error type string if failed (exception stored in self.error).
        """
        if not self.task:
            return "missing_input"

        try:
            self.info = await self.task
            return None
        except Exception as err:
            if not isinstance(err, InvalidAuthError | UnsupportedModemError | CannotConnectError):
                _LOGGER.exception("Unexpected exception during validation")
            self.error = err
            return classify_error(err)
        finally:
            self.task = None

    def get_error_type(self) -> str:
        """Get error type string for the stored error."""
        return classify_error(self.error)

    def reset(self) -> None:
        """Clear all state for next validation attempt."""
        self.user_input = None
        self.task = None
        self.error = None
        self.info = None


# =============================================================================
# Config Flow Mixin
# =============================================================================


class ConfigFlowMixin:
    """Shared methods for config flow and options flow.

    Provides common functionality for building parser dropdowns and
    applying validation results to config entry data.

    Type stubs declare attributes that exist on the HA base classes.
    """

    # Type stubs for attributes from HA base classes
    _modem_choices: list[str]
    hass: HomeAssistant
    config_entry: config_entries.ConfigEntry  # Only on OptionsFlow

    async def _ensure_parser_dropdown(self) -> None:
        """Load parser dropdown options from index.yaml, caching for the session."""
        if not self._modem_choices:
            self._modem_choices = await build_parser_dropdown(self.hass)

    def _apply_detection_info(
        self,
        data: dict[str, Any],
        detection_info: dict[str, Any],
        log_prefix: str = "",
    ) -> None:
        """Apply modem detection results to config entry data.

        Args:
            data: Target dict to update with detection fields.
            detection_info: Detection results from validation.
            log_prefix: Optional prefix for log messages (e.g., "Options flow: ").
        """
        detected_modem_name = detection_info.get("modem_name")
        data[CONF_PARSER_NAME] = detected_modem_name
        data[CONF_DETECTED_MODEM] = detection_info.get("modem_name", "Unknown")
        data[CONF_DETECTED_MANUFACTURER] = detection_info.get("manufacturer", "Unknown")
        data[CONF_DOCSIS_VERSION] = detection_info.get("docsis_version")
        data[CONF_PARSER_SELECTED_AT] = datetime.now().isoformat()

        if detection_info.get("actual_model"):
            data[CONF_ACTUAL_MODEL] = detection_info["actual_model"]

    def _apply_auth_discovery_info(
        self,
        data: dict[str, Any],
        info: dict[str, Any],
        fallback_data: Mapping[str, Any] | None = None,
    ) -> None:
        """Apply auth discovery results to config entry data.

        Args:
            data: Target dict to update with auth fields.
            info: Validation info containing new auth discovery results.
            fallback_data: Existing entry data for fallback values (options flow).
        """
        # Prefer new values, fall back to existing
        for key in (
            CONF_AUTH_STRATEGY,
            CONF_AUTH_FORM_CONFIG,
            CONF_AUTH_HNAP_CONFIG,
            CONF_AUTH_URL_TOKEN_CONFIG,
        ):
            if info.get(key):
                data[key] = info[key]
            elif fallback_data and fallback_data.get(key):
                data[key] = fallback_data[key]

        # Status fields always come from current validation
        if info.get(CONF_AUTH_DISCOVERY_STATUS):
            data[CONF_AUTH_DISCOVERY_STATUS] = info[CONF_AUTH_DISCOVERY_STATUS]
        if info.get(CONF_AUTH_DISCOVERY_FAILED) is not None:
            data[CONF_AUTH_DISCOVERY_FAILED] = info[CONF_AUTH_DISCOVERY_FAILED]
        if info.get(CONF_AUTH_DISCOVERY_ERROR):
            data[CONF_AUTH_DISCOVERY_ERROR] = info[CONF_AUTH_DISCOVERY_ERROR]


# =============================================================================
# Main Config Flow
# =============================================================================


@config_entries.HANDLERS.register(DOMAIN)
class CableModemMonitorConfigFlow(ConfigFlowMixin, config_entries.ConfigFlow):
    """Handle initial setup flow for Cable Modem Monitor.

    This flow guides users through adding a new modem to Home Assistant:
    1. Enter modem IP, credentials, and select parser
    2. Select auth type (only if modem has multiple options)
    3. Validate connectivity and authentication
    4. Create config entry on success
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow state."""
        self._progress = ValidationProgressHelper()
        self._modem_choices: list[str] = []
        self._selected_auth_type: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Return the options flow handler."""
        return OptionsFlowHandler()

    def _build_user_schema(
        self,
        default_host: str = "192.168.100.1",
        default_username: str = "",
        default_password: str = "",
        default_modem: str = "",
        default_entity_prefix: str = "",
    ) -> vol.Schema:
        """Build the form schema for user input step."""
        # Determine entity prefix options based on existing entries
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)

        if existing_entries:
            # Second+ modem: no "None" option, default to "Model"
            prefix_options = [
                selector.SelectOptionDict(value=ENTITY_PREFIX_MODEL, label="Model"),
                selector.SelectOptionDict(value=ENTITY_PREFIX_IP, label="IP Address"),
            ]
            prefix_default = default_entity_prefix or ENTITY_PREFIX_MODEL
        else:
            # First modem: all options available, default to "None"
            prefix_options = [
                selector.SelectOptionDict(value=ENTITY_PREFIX_NONE, label="None"),
                selector.SelectOptionDict(value=ENTITY_PREFIX_MODEL, label="Model"),
                selector.SelectOptionDict(value=ENTITY_PREFIX_IP, label="IP Address"),
            ]
            prefix_default = default_entity_prefix or ENTITY_PREFIX_NONE

        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=default_host): str,
                vol.Optional(CONF_USERNAME, default=default_username): str,
                vol.Optional(CONF_PASSWORD, default=default_password): str,
                vol.Required(CONF_MODEM_CHOICE, default=default_modem): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._modem_choices,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_ENTITY_PREFIX, default=prefix_default): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=prefix_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Handle the initial user input step."""
        # Restore user input when returning from progress step
        if user_input is None and self._progress.user_input:
            user_input = self._progress.user_input

        await self._ensure_parser_dropdown()

        if user_input is not None:
            self._progress.user_input = user_input

            # Check if auth type selection is needed
            from .core.parser_registry import get_parser_by_name

            modem_choice = user_input.get(CONF_MODEM_CHOICE, "")
            choice_clean = modem_choice.rstrip(" *")
            selected_parser = await self.hass.async_add_executor_job(get_parser_by_name, choice_clean)

            if await needs_auth_type_selection(self.hass, selected_parser):
                return await self.async_step_auth_type()

            return await self.async_step_validate()

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_user_schema(),
        )

    async def async_step_auth_type(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Show auth type selection if modem has multiple types.

        This step is only shown for modems with auth.types{} in modem.yaml
        that have more than one option (e.g., SB8200 with "none" and "url_token").
        """
        from .core.parser_registry import get_parser_by_name

        if user_input is not None:
            # Store selected auth type and proceed to validation
            self._selected_auth_type = user_input.get(CONF_AUTH_TYPE)
            if self._progress.user_input:
                self._progress.user_input[CONF_AUTH_TYPE] = self._selected_auth_type
            return await self.async_step_validate()

        # Get selected parser to build auth type dropdown
        saved_input = self._progress.user_input or {}
        modem_choice = saved_input.get(CONF_MODEM_CHOICE, "")
        choice_clean = modem_choice.rstrip(" *")
        selected_parser = await self.hass.async_add_executor_job(get_parser_by_name, choice_clean)

        # Get auth type options for dropdown
        auth_type_options = await get_auth_type_dropdown(self.hass, selected_parser)

        return self.async_show_form(
            step_id="auth_type",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AUTH_TYPE): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[selector.SelectOptionDict(value=k, label=v) for k, v in auth_type_options.items()],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            description_placeholders={
                "modem_name": choice_clean,
            },
        )

    async def async_step_validate(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Show progress indicator during validation."""
        if not self._progress.task:
            if not self._progress.user_input:
                return self.async_abort(reason="missing_input")
            self._progress.start(self.hass, self._progress.user_input)

        if self._progress.is_running():
            return self.async_show_progress(
                step_id="validate",
                progress_action="validate",
                progress_task=self._progress.task,
            )

        error_type = await self._progress.get_result()
        if error_type:
            return self.async_show_progress_done(next_step_id="user_with_errors")

        # HA requires: progress -> progress_done -> final_step
        return self.async_show_progress_done(next_step_id="validate_success")

    async def async_step_validate_success(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create config entry after successful validation."""
        if not self._progress.user_input or not self._progress.info:
            return self.async_abort(reason="missing_input")

        user_input = self._progress.user_input
        info = self._progress.info
        self._progress.reset()

        # Prevent duplicate entries for same host
        await self.async_set_unique_id(user_input[CONF_HOST])
        self._abort_if_unique_id_configured()

        entry_data = self._build_entry_data(user_input, info)
        return self.async_create_entry(title=info["title"], data=entry_data)

    def _build_entry_data(self, user_input: dict[str, Any], info: dict[str, Any]) -> dict[str, Any]:
        """Build config entry data from user input and validation results."""
        data = dict(user_input)
        data.setdefault(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        data[CONF_SUPPORTS_ICMP] = info.get("supports_icmp", True)
        data[CONF_LEGACY_SSL] = info.get("legacy_ssl", False)

        # Store entity prefix (default to "none" for backwards compatibility)
        data[CONF_ENTITY_PREFIX] = user_input.get(CONF_ENTITY_PREFIX, ENTITY_PREFIX_NONE)

        # Store auth type if selected
        if self._selected_auth_type:
            data[CONF_AUTH_TYPE] = self._selected_auth_type

        detection_info = info.get("detection_info", {})
        if detection_info:
            self._apply_detection_info(data, detection_info)

        if info.get(CONF_WORKING_URL):
            data[CONF_WORKING_URL] = info[CONF_WORKING_URL]

        self._apply_auth_discovery_info(data, info)
        return data

    async def async_step_user_with_errors(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Re-show form with error message after validation failure."""
        await self._ensure_parser_dropdown()

        saved_input = self._progress.user_input or {}
        errors = {"base": self._progress.get_error_type()}
        self._progress.reset()

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_user_schema(
                default_host=saved_input.get(CONF_HOST, "192.168.100.1"),
                default_username=saved_input.get(CONF_USERNAME, ""),
                default_password=saved_input.get(CONF_PASSWORD, ""),
                default_modem=saved_input.get(CONF_MODEM_CHOICE, ""),
                default_entity_prefix=saved_input.get(CONF_ENTITY_PREFIX, ""),
            ),
            errors=errors,
        )


# =============================================================================
# Options Flow
# =============================================================================


class OptionsFlowHandler(ConfigFlowMixin, config_entries.OptionsFlow):
    """Handle reconfiguration flow for Cable Modem Monitor.

    Allows users to modify settings after initial setup:
    - Change modem IP address
    - Update credentials
    - Switch parser selection
    - Adjust scan interval
    """

    def __init__(self) -> None:
        """Initialize options flow state."""
        self._progress = ValidationProgressHelper()
        self._modem_choices: list[str] = []

    def _build_options_schema(
        self,
        default_host: str,
        default_username: str,
        default_modem: str,
        default_scan_interval: int,
    ) -> vol.Schema:
        """Build the form schema for options step."""
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=default_host): str,
                vol.Optional(CONF_USERNAME, default=default_username): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Required(CONF_MODEM_CHOICE, default=default_modem): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._modem_choices,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_SCAN_INTERVAL, default=default_scan_interval): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
            }
        )

    def _preserve_credentials(self, user_input: dict[str, Any]) -> None:
        """Fill in existing credentials if user left fields empty."""
        if not user_input.get(CONF_PASSWORD):
            user_input[CONF_PASSWORD] = self.config_entry.data.get(CONF_PASSWORD, "")
        if not user_input.get(CONF_USERNAME):
            user_input[CONF_USERNAME] = self.config_entry.data.get(CONF_USERNAME, "")

    def _get_current_modem_choice(self) -> str:
        """Get stored modem choice, normalized to current dropdown format."""
        stored: str = self.config_entry.data.get(CONF_MODEM_CHOICE, "")
        if stored:
            # Check if stored name is in current dropdown choices
            if stored in self._modem_choices:
                return stored
            # Strip " *" suffix for matching (unverified parser indicator)
            stored_clean = stored.rstrip(" *")
            if stored_clean in self._modem_choices:
                return stored_clean
        return stored

    def _format_parser_selected_at(self, parser_selected_at: str) -> str:
        """Format ISO timestamp for display."""
        if parser_selected_at and parser_selected_at != "Never":
            try:
                dt = datetime.fromisoformat(parser_selected_at)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                pass
        return parser_selected_at

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Show the options form."""
        # Restore user input when returning from progress step
        if user_input is None and self._progress.user_input:
            user_input = self._progress.user_input

        await self._ensure_parser_dropdown()

        if user_input is not None:
            self._preserve_credentials(user_input)
            self._progress.user_input = user_input
            return await self.async_step_options_validate()

        # Load current values for form defaults
        entry_data = self.config_entry.data
        current_host = entry_data.get(CONF_HOST, "192.168.100.1")
        current_username = entry_data.get(CONF_USERNAME, "")
        current_scan_interval = entry_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        current_modem_choice = self._get_current_modem_choice()

        return self.async_show_form(
            step_id="init",
            data_schema=self._build_options_schema(
                default_host=current_host,
                default_username=current_username,
                default_modem=current_modem_choice,
                default_scan_interval=current_scan_interval,
            ),
            description_placeholders={
                "detected_modem": entry_data.get(CONF_DETECTED_MODEM, "Not detected"),
                "parser_selected_at": self._format_parser_selected_at(entry_data.get(CONF_PARSER_SELECTED_AT, "Never")),
            },
        )

    async def async_step_options_validate(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show progress indicator during validation."""
        if not self._progress.task:
            if not self._progress.user_input:
                return self.async_abort(reason="missing_input")
            self._progress.start(self.hass, self._progress.user_input)

        if self._progress.is_running():
            return self.async_show_progress(
                step_id="options_validate",
                progress_action="validate",
                progress_task=self._progress.task,
            )

        error_type = await self._progress.get_result()
        if error_type:
            return self.async_show_progress_done(next_step_id="options_with_errors")

        return self.async_show_progress_done(next_step_id="options_success")

    async def async_step_options_success(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Update config entry after successful validation."""
        if not self._progress.user_input or not self._progress.info:
            return self.async_abort(reason="missing_input")

        user_input = self._progress.user_input
        info = self._progress.info
        self._progress.reset()

        entry_data = self._build_updated_entry_data(user_input, info)

        # Update title to reflect any detection changes
        detection_info = {
            "modem_name": entry_data.get(CONF_DETECTED_MODEM, "Cable Modem"),
            "manufacturer": entry_data.get(CONF_DETECTED_MANUFACTURER, ""),
        }
        new_title = create_title(detection_info, entry_data.get(CONF_HOST, ""))

        self.hass.config_entries.async_update_entry(self.config_entry, title=new_title, data=entry_data)
        return self.async_create_entry(title="", data={})

    def _build_updated_entry_data(self, user_input: dict[str, Any], info: dict[str, Any]) -> dict[str, Any]:
        """Build updated config entry data from user input and validation results."""
        data = dict(user_input)

        # These are re-tested on every validation
        data[CONF_SUPPORTS_ICMP] = info.get("supports_icmp", True)
        data[CONF_LEGACY_SSL] = info.get("legacy_ssl", False)

        # Apply new detection info, or preserve existing
        detection_info = info.get("detection_info", {})
        if detection_info:
            self._apply_detection_info(data, detection_info, log_prefix="Options flow: ")
        else:
            self._preserve_detection_info(data)

        # Preserve working URL if not in new results
        if info.get(CONF_WORKING_URL):
            data[CONF_WORKING_URL] = info[CONF_WORKING_URL]
        elif self.config_entry.data.get(CONF_WORKING_URL):
            data[CONF_WORKING_URL] = self.config_entry.data[CONF_WORKING_URL]

        self._apply_auth_discovery_info(data, info, fallback_data=self.config_entry.data)
        return data

    def _preserve_detection_info(self, data: dict[str, Any]) -> None:
        """Copy existing detection info when validation didn't return new info.

        This is not in ConfigFlowMixin because it requires self.config_entry,
        which only exists on OptionsFlow (not on the initial ConfigFlow).
        """
        entry_data = self.config_entry.data
        data[CONF_PARSER_NAME] = entry_data.get(CONF_PARSER_NAME)
        data[CONF_DETECTED_MODEM] = entry_data.get(CONF_DETECTED_MODEM, "Unknown")
        data[CONF_DETECTED_MANUFACTURER] = entry_data.get(CONF_DETECTED_MANUFACTURER, "Unknown")
        data[CONF_DOCSIS_VERSION] = entry_data.get(CONF_DOCSIS_VERSION)
        data[CONF_PARSER_SELECTED_AT] = entry_data.get(CONF_PARSER_SELECTED_AT)
        data[CONF_ACTUAL_MODEL] = entry_data.get(CONF_ACTUAL_MODEL)

    async def async_step_options_with_errors(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Re-show form with error message after validation failure."""
        await self._ensure_parser_dropdown()

        saved_input = self._progress.user_input or {}
        errors = {"base": self._progress.get_error_type()}
        self._progress.reset()

        entry_data = self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=self._build_options_schema(
                default_host=saved_input.get(CONF_HOST, entry_data.get(CONF_HOST, "192.168.100.1")),
                default_username=saved_input.get(CONF_USERNAME, entry_data.get(CONF_USERNAME, "")),
                default_modem=saved_input.get(CONF_MODEM_CHOICE, entry_data.get(CONF_MODEM_CHOICE, "")),
                default_scan_interval=saved_input.get(
                    CONF_SCAN_INTERVAL, entry_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ),
            ),
            errors=errors,
            description_placeholders={
                "detected_modem": entry_data.get(CONF_DETECTED_MODEM, "Not detected"),
                "parser_selected_at": self._format_parser_selected_at(entry_data.get(CONF_PARSER_SELECTED_AT, "Never")),
            },
        )
