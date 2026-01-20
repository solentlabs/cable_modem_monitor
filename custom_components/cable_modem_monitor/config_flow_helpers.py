"""Config flow helpers for Cable Modem Monitor.

This module provides HA-specific helpers for config_flow.py. It adapts
the core library functionality for Home Assistant's config entry system.

Functions:
    - classify_error(): Maps exceptions to HA form error keys (strings.json)
    - build_parser_dropdown(): Async helper to build sorted parser list
    - load_parser_hints(): Load auth hints via hass executor
    - validate_input(): Orchestrates discovery pipeline for HA config flow

These functions depend on Home Assistant and cannot be extracted to a
standalone library. Core functionality lives in core/ modules.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from homeassistant.core import HomeAssistant

    from .core.base_parser import ModemParser

from .const import (
    CONF_AUTH_DISCOVERY_ERROR,
    CONF_AUTH_DISCOVERY_FAILED,
    CONF_AUTH_DISCOVERY_STATUS,
    CONF_AUTH_FORM_CONFIG,
    CONF_AUTH_HNAP_CONFIG,
    CONF_AUTH_STRATEGY,
    CONF_AUTH_URL_TOKEN_CONFIG,
    CONF_HOST,
    CONF_MODEM_CHOICE,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_WORKING_URL,
)
from .core.exceptions import (
    CannotConnectError,
    InvalidAuthError,
    UnsupportedModemError,
)
from .core.network import test_icmp_ping
from .core.parser_utils import create_title
from .lib.host_validation import extract_hostname as _validate_host_format
from .parsers import get_parser_by_name, get_parser_dropdown_from_index

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# Error Classification (HA-specific)
# =============================================================================
# Maps exceptions to error key strings for HA form display. These keys are
# looked up in strings.json (and translations/*.json) by HA's frontend.
#
# This code does NOT handle translations - it only returns keys. HA's frontend
# performs the actual i18n lookup based on user's language setting.
#
# Keys must match entries in strings.json under "config.error":
#   - "invalid_auth": Wrong username/password
#   - "unsupported_modem": No parser matches the modem
#   - "invalid_input": Malformed user input (host format, etc.)
#   - "cannot_connect": Network timeout or connection refused
#   - "network_unreachable": Host not reachable (with specific message)
#   - "unknown": Unexpected exception
# =============================================================================

_ERROR_TYPE_MAP: dict[type[Exception], str] = {
    InvalidAuthError: "invalid_auth",
    UnsupportedModemError: "unsupported_modem",
    ValueError: "invalid_input",
    TypeError: "invalid_input",
}


def classify_error(error: Exception | None) -> str:
    """Classify an exception into an error key for HA form display.

    Args:
        error: The exception to classify, or None.

    Returns:
        Error key string (e.g., "invalid_auth") that HA looks up in
        strings.json for the user-facing message. Returns "cannot_connect"
        if error is None.
    """
    if error is None:
        return "cannot_connect"

    # CannotConnectError with user_message indicates specific network issue
    if isinstance(error, CannotConnectError):
        if error.user_message:
            return "network_unreachable"
        return "cannot_connect"

    # Check mapped error types
    for error_class, error_type in _ERROR_TYPE_MAP.items():
        if isinstance(error, error_class):
            return error_type

    return "unknown"


# =============================================================================
# Parser Dropdown (HA-specific - uses hass.async_add_executor_job)
# =============================================================================


async def build_parser_dropdown(hass: HomeAssistant) -> list[str]:
    """Build parser dropdown options from index.yaml.

    Uses index.yaml for O(1) lookup - no parser modules are imported.

    Args:
        hass: Home Assistant instance

    Returns:
        List of modem display names including "auto" option
    """
    parser_names: list[str] = await hass.async_add_executor_job(get_parser_dropdown_from_index)
    return ["auto"] + parser_names


# =============================================================================
# Parser Hints (HA-specific - uses hass.async_add_executor_job)
# =============================================================================


async def load_parser_hints(hass: HomeAssistant, selected_parser: type[ModemParser] | None) -> dict[str, Any] | None:
    """Load auth hints from modem.yaml or parser class.

    Args:
        hass: Home Assistant instance
        selected_parser: Selected parser class or None

    Returns:
        Auth hints dict or None
    """
    if not selected_parser:
        return None

    # Try modem.yaml first (includes success_redirect for verification)
    try:
        from .modem_config import get_auth_adapter_for_parser

        adapter = await hass.async_add_executor_job(get_auth_adapter_for_parser, selected_parser.__name__)
        if adapter:
            hints: dict[str, Any] = adapter.get_auth_form_hints()
            if hints:
                _LOGGER.info(
                    "Using modem.yaml auth hints for %s (encoding=%s, has_redirect=%s)",
                    selected_parser.name,
                    hints.get("password_encoding", "plain"),
                    bool(hints.get("success_redirect")),
                )
                return hints
    except Exception as e:
        _LOGGER.debug("Failed to load modem.yaml hints: %s", e)

    # Fall back to parser class attributes
    fallback_hints: dict[str, Any] | None = getattr(selected_parser, "auth_form_hints", None)
    if fallback_hints:
        _LOGGER.info(
            "Using parser %s auth hints for discovery (encoding=%s)",
            selected_parser.name,
            fallback_hints.get("password_encoding", "plain"),
        )
    return fallback_hints


# =============================================================================
# Input Validation (HA-specific - orchestrates for config flow)
# =============================================================================


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Uses the discovery pipeline for a single-pass, response-driven flow:
    1. Connectivity check -> working_url
    2. Auth discovery -> session, html
    3. Parser detection -> parser (from html, no extra requests)
    4. Validation parse -> modem_data (from html, no extra requests)

    Args:
        hass: Home Assistant instance
        data: User input dict with host, username, password, modem_choice

    Returns:
        Dict with title, detection_info, supports_icmp, working_url, auth config

    Raises:
        CannotConnectError: If connection fails
        InvalidAuthError: If authentication fails
        UnsupportedModemError: If no parser matches
    """
    from .core.discovery import run_discovery_pipeline

    # Validate host format
    host = data[CONF_HOST]
    _validate_host_format(host)

    # Get selected parser if user chose one (uses index for O(1) lookup)
    modem_choice = data.get(CONF_MODEM_CHOICE)
    selected_parser = None
    if modem_choice and modem_choice != "auto":
        # User selected specific parser - load just that one via index
        choice_clean = modem_choice.rstrip(" *")
        selected_parser = await hass.async_add_executor_job(get_parser_by_name, choice_clean)
        if selected_parser:
            _LOGGER.info("User selected parser: %s", choice_clean)
        else:
            _LOGGER.warning("Parser '%s' not found, using auto-detection", choice_clean)

    # Load parser auth hints if user selected a specific parser
    parser_hints = await load_parser_hints(hass, selected_parser)

    # Run discovery pipeline (single-pass, response-driven)
    result = await hass.async_add_executor_job(
        run_discovery_pipeline,
        host,
        data.get(CONF_USERNAME),
        data.get(CONF_PASSWORD),
        selected_parser,
        parser_hints,
    )

    # Handle pipeline failures
    if not result.success:
        _LOGGER.error("Discovery pipeline failed at step '%s': %s", result.failed_step, result.error)
        if result.failed_step == "connectivity":
            raise CannotConnectError(result.error or "Cannot connect to modem")
        elif result.failed_step == "auth":
            raise InvalidAuthError(result.error or "Authentication failed")
        elif result.failed_step == "parser_detection":
            raise UnsupportedModemError(result.error or "Could not detect modem type")
        else:
            raise CannotConnectError(result.error or "Discovery failed")

    # Build detection info from pipeline result
    detection_info = {
        "modem_name": result.parser_name,
        "detected_modem": result.parser_name,
        "manufacturer": result.parser_instance.manufacturer if result.parser_instance else None,
        "detection_method": "discovery_pipeline",
    }

    # Extract actual model from parsed modem data
    if result.parser_instance and result.modem_data:
        actual_model = result.parser_instance.get_actual_model(result.modem_data)
        if actual_model:
            detection_info["actual_model"] = actual_model
            _LOGGER.debug("Actual model extracted from modem: %s", actual_model)

    title = create_title(detection_info, host)

    # Test ICMP ping support AFTER discovery succeeds (for health monitoring)
    supports_icmp = await test_icmp_ping(host)

    return {
        "title": title,
        "detection_info": detection_info,
        "supports_icmp": supports_icmp,
        "legacy_ssl": result.legacy_ssl,
        # Store working URL for polling (skip protocol discovery)
        CONF_WORKING_URL: result.working_url,
        # Auth discovery results
        CONF_AUTH_STRATEGY: result.auth_strategy,
        CONF_AUTH_FORM_CONFIG: result.auth_form_config,
        CONF_AUTH_HNAP_CONFIG: result.auth_hnap_config,
        CONF_AUTH_URL_TOKEN_CONFIG: result.auth_url_token_config,
        CONF_AUTH_DISCOVERY_STATUS: "success",
        CONF_AUTH_DISCOVERY_FAILED: False,
        CONF_AUTH_DISCOVERY_ERROR: None,
    }
