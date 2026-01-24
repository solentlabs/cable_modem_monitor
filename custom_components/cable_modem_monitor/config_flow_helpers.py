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
    CONF_AUTH_TYPE,
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
from .core.parser_registry import get_parser_by_name, get_parser_dropdown_from_index
from .core.parser_utils import create_title
from .lib.host_validation import extract_hostname as _validate_host_format

# Use config_flow logger for cleaner log output (this module is an impl detail)
_LOGGER = logging.getLogger(__name__.replace("_helpers", ""))


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
        List of modem display names (user must select their modem model)
    """
    parser_names: list[str] = await hass.async_add_executor_job(get_parser_dropdown_from_index)
    return parser_names


# =============================================================================
# Auth Type Helpers (for modems with user-selectable auth variants)
# =============================================================================


async def get_auth_types_for_parser(hass: HomeAssistant, selected_parser: type[ModemParser] | None) -> list[str]:
    """Get available auth types for a parser from modem.yaml.

    Args:
        hass: Home Assistant instance
        selected_parser: Selected parser class or None

    Returns:
        List of auth type strings (e.g., ["none", "url_token"]).
        Returns ["none"] if parser not found or no modem.yaml.
    """
    if not selected_parser:
        _LOGGER.debug("get_auth_types_for_parser: no parser selected")
        return ["none"]

    from .modem_config import get_auth_adapter_for_parser

    parser_name = selected_parser.__name__
    _LOGGER.debug("get_auth_types_for_parser: looking up adapter for %s", parser_name)
    adapter = await hass.async_add_executor_job(get_auth_adapter_for_parser, parser_name)
    if not adapter:
        _LOGGER.debug("get_auth_types_for_parser: no adapter found for %s", parser_name)
        return ["none"]

    auth_types: list[str] = adapter.get_available_auth_types()
    _LOGGER.debug("get_auth_types_for_parser: %s has auth_types=%s", parser_name, auth_types)
    return auth_types if auth_types else ["none"]


async def get_auth_type_dropdown(hass: HomeAssistant, selected_parser: type[ModemParser] | None) -> dict[str, str]:
    """Get auth type dropdown options with labels.

    Args:
        hass: Home Assistant instance
        selected_parser: Selected parser class or None

    Returns:
        Dict mapping auth type keys to display labels
    """
    from .core.auth.workflow import AUTH_TYPE_LABELS

    auth_types = await get_auth_types_for_parser(hass, selected_parser)
    return {t: AUTH_TYPE_LABELS.get(t, t.title()) for t in auth_types}


async def needs_auth_type_selection(hass: HomeAssistant, selected_parser: type[ModemParser] | None) -> bool:
    """Check if the modem needs auth type selection.

    Args:
        hass: Home Assistant instance
        selected_parser: Selected parser class or None

    Returns:
        True if modem has multiple auth types to choose from
    """
    auth_types = await get_auth_types_for_parser(hass, selected_parser)
    parser_name = selected_parser.__name__ if selected_parser else "None"
    _LOGGER.info("Auth type check for %s: types=%s, needs_selection=%s", parser_name, auth_types, len(auth_types) > 1)
    return len(auth_types) > 1


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


async def load_static_auth_config(
    hass: HomeAssistant, selected_parser: type[ModemParser] | None
) -> dict[str, Any] | None:
    """Load static auth config from modem.yaml for known modems.

    This enables the "modem.yaml as source of truth" architecture where
    known modems skip dynamic auth discovery and use verified config directly.

    Args:
        hass: Home Assistant instance
        selected_parser: Selected parser class or None

    Returns:
        Static auth config dict or None if not a known modem
    """
    if not selected_parser:
        return None

    from .modem_config import get_auth_adapter_for_parser

    adapter = await hass.async_add_executor_job(get_auth_adapter_for_parser, selected_parser.__name__)
    if not adapter:
        _LOGGER.info("Using dynamic auth discovery for %s (no modem.yaml)", selected_parser.name)
        return None

    static_config: dict[str, Any] = await hass.async_add_executor_job(adapter.get_static_auth_config)
    _LOGGER.info(
        "Using modem.yaml auth config for %s (strategy=%s)",
        selected_parser.name,
        static_config.get("auth_strategy"),
    )
    return static_config


# =============================================================================
# Input Validation (HA-specific - orchestrates for config flow)
# =============================================================================


async def _build_static_config_for_auth_type(
    hass: HomeAssistant, selected_parser: type[ModemParser] | None, auth_type: str
) -> dict[str, Any] | None:
    """Build static auth config for a specific auth type.

    When user explicitly selects an auth type (from auth.types{} in modem.yaml),
    this builds the appropriate config dict for the discovery pipeline.

    Args:
        hass: Home Assistant instance
        selected_parser: Selected parser class
        auth_type: User-selected auth type (e.g., "none", "form", "url_token")

    Returns:
        Static auth config dict or None if not available
    """
    from .core.auth.workflow import AUTH_TYPE_TO_STRATEGY
    from .modem_config import get_auth_adapter_for_parser

    if not selected_parser:
        return None

    adapter = await hass.async_add_executor_job(get_auth_adapter_for_parser, selected_parser.__name__)
    if not adapter:
        return None

    # Get config for this specific auth type
    type_config = adapter.get_auth_config_for_type(auth_type)

    # Map user-facing auth type to internal strategy string
    strategy = AUTH_TYPE_TO_STRATEGY.get(auth_type, "no_auth")

    # Build static config in the format expected by discovery pipeline
    static_config: dict[str, Any] = {
        "auth_strategy": strategy,
        "auth_form_config": type_config if auth_type == "form" else None,
        "auth_hnap_config": type_config if auth_type == "hnap" else None,
        "auth_url_token_config": type_config if auth_type == "url_token" else None,
    }

    _LOGGER.info(
        "Built static auth config for %s type=%s (strategy=%s)",
        selected_parser.name,
        auth_type,
        strategy,
    )

    return static_config


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:  # noqa: C901
    """Validate the user input allows us to connect.

    Uses the discovery pipeline for a single-pass, response-driven flow:
    1. Connectivity check -> working_url
    2. Auth discovery -> session, html
    3. Parser detection -> parser (from html, no extra requests)
    4. Validation parse -> modem_data (from html, no extra requests)

    Args:
        hass: Home Assistant instance
        data: User input dict with host, username, password, modem_choice, auth_type

    Returns:
        Dict with title, detection_info, supports_icmp, working_url, auth config

    Raises:
        CannotConnectError: If connection fails
        InvalidAuthError: If authentication fails
        UnsupportedModemError: If no parser matches
    """
    from .core.setup import setup_modem

    # Validate host format
    host = data[CONF_HOST]
    _validate_host_format(host)

    # Get selected parser (mandatory - user must select their modem model)
    modem_choice = data.get(CONF_MODEM_CHOICE)
    if not modem_choice:
        raise ValueError("Modem selection is required")

    choice_clean = modem_choice.rstrip(" *")
    selected_parser = await hass.async_add_executor_job(get_parser_by_name, choice_clean)
    if not selected_parser:
        raise UnsupportedModemError(f"Parser '{choice_clean}' not found")
    _LOGGER.info("User selected parser: %s", choice_clean)

    # Check if user explicitly selected an auth type (from auth_type step)
    auth_type = data.get(CONF_AUTH_TYPE)
    static_auth_config: dict[str, Any] | None = None

    if auth_type:
        # User explicitly selected auth type - build config from that
        _LOGGER.info("User selected auth type: %s", auth_type)
        static_auth_config = await _build_static_config_for_auth_type(hass, selected_parser, auth_type)
    else:
        # Get static auth config from modem.yaml for known modems
        static_auth_config = await load_static_auth_config(hass, selected_parser)

    # Require static auth config - all known modems must have modem.yaml
    # Exception: Fallback parser uses dynamic auth discovery (no modem.yaml by design)
    if not static_auth_config:
        if selected_parser.manufacturer == "Unknown":
            # Fallback parser - provide default no_auth config
            # FallbackOrchestrator will discover actual auth at runtime
            _LOGGER.info("Using default no_auth config for fallback parser %s", selected_parser.name)
            static_auth_config = {
                "auth_strategy": "no_auth",
                "auth_form_config": None,
                "auth_hnap_config": None,
                "auth_url_token_config": None,
            }
        else:
            _LOGGER.error(
                "No auth config found for %s - modem.yaml may be incomplete",
                selected_parser.name,
            )
            raise UnsupportedModemError(
                f"Configuration error: {selected_parser.name} is missing auth configuration. "
                "Please report this issue."
            )

    result = await hass.async_add_executor_job(
        setup_modem,
        host,
        selected_parser,
        static_auth_config,
        data.get(CONF_USERNAME),
        data.get(CONF_PASSWORD),
    )

    # Handle setup/discovery failures
    if not result.success:
        _LOGGER.error("Setup failed at step '%s': %s", result.failed_step, result.error)
        if result.failed_step == "connectivity":
            raise CannotConnectError(result.error or "Cannot connect to modem")
        elif result.failed_step == "auth":
            raise InvalidAuthError(result.error or "Authentication failed")
        elif result.failed_step == "parser_detection":
            raise UnsupportedModemError(result.error or "Could not detect modem type")
        else:
            raise CannotConnectError(result.error or "Setup failed")

    # Build detection info from result
    detection_info: dict[str, Any] = {
        "modem_name": result.parser_name,
        "detected_modem": result.parser_name,
        "manufacturer": result.parser_instance.manufacturer if result.parser_instance else None,
    }

    # Extract actual model from parsed modem data
    if result.parser_instance and result.modem_data:
        actual_model = result.parser_instance.get_actual_model(result.modem_data)
        if actual_model:
            detection_info["actual_model"] = actual_model
            _LOGGER.debug("Actual model extracted from modem: %s", actual_model)

    # Extract docsis_version from modem.yaml
    if result.parser_name:
        from .modem_config import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser(result.parser_name)
        if adapter:
            docsis_version = adapter.get_docsis_version()
            if docsis_version:
                detection_info["docsis_version"] = docsis_version
                _LOGGER.debug("DOCSIS version from modem.yaml: %s", docsis_version)

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
