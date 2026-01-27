"""The Cable Modem Monitor integration.

Home Assistant integration for monitoring cable modem signal quality and health.
Supports DOCSIS 3.0 and 3.1 modems from various manufacturers.

Entry Points:
    async_setup_entry: Called by HA when integration is configured
    async_unload_entry: Called when integration is removed/reloaded

Services:
    cable_modem_monitor.clear_history: Clear historical sensor data
    cable_modem_monitor.generate_dashboard: Generate Lovelace dashboard YAML

Key Components:
    DataUpdateCoordinator: Polls modem every scan_interval (default 30s)
    DataOrchestrator: Fetches and parses modem data
    ModemHealthMonitor: Tracks ICMP latency to modem

See Also:
    - config_flow.py: Setup wizard UI
    - sensor.py: Sensor entity definitions
    - core/data_orchestrator.py: Data fetching logic
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .core.base_parser import ModemParser

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_AUTH_FORM_CONFIG,
    CONF_AUTH_HNAP_CONFIG,
    CONF_AUTH_STRATEGY,
    CONF_AUTH_URL_TOKEN_CONFIG,
    CONF_DOCSIS_VERSION,
    CONF_ENTITY_PREFIX,
    CONF_HOST,
    CONF_LEGACY_SSL,
    CONF_MODEM_CHOICE,
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
    VERSION,
)
from .coordinator import create_health_monitor, create_update_function, perform_initial_refresh
from .core.data_orchestrator import DataOrchestrator
from .core.fallback import FallbackOrchestrator
from .core.log_buffer import setup_log_buffer
from .core.parser_registry import get_parser_by_name
from .entity_migration import async_migrate_docsis30_entities
from .modem_config.adapter import get_auth_adapter_for_parser
from .services import (
    SERVICE_CLEAR_HISTORY,
    SERVICE_CLEAR_HISTORY_SCHEMA,
    SERVICE_GENERATE_DASHBOARD,
    SERVICE_GENERATE_DASHBOARD_SCHEMA,
    create_clear_history_handler,
    create_generate_dashboard_handler,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]


def _log_missing_auth_config(
    auth_strategy: str | None,
    auth_hnap_config: dict | None,
    auth_url_token_config: dict | None,
) -> None:
    """Log debug message for entries upgraded from pre-v3.12 without stored auth configs."""
    if auth_strategy == "hnap_session" and not auth_hnap_config:
        _LOGGER.debug("HNAP config not stored in entry (pre-v3.12.0 entry), using defaults")
    if auth_strategy == "url_token_session" and not auth_url_token_config:
        _LOGGER.debug("URL token config not stored in entry (pre-v3.12.0 entry), using defaults")


def _update_device_registry(hass: HomeAssistant, entry: ConfigEntry, host: str) -> None:
    """Update device registry with detected modem info.

    Device name is based on entity_prefix setting to ensure unique entity IDs
    when multiple modems are configured. With has_entity_name=True, entity IDs
    are generated from device name + sensor name.

    Prefix options:
    - none: "Cable Modem" -> sensor.cable_modem_downstream_1_power
    - model: "Cable Modem MB7621" -> sensor.cable_modem_mb7621_downstream_1_power
    - ip: "Cable Modem 192_168_100_1" -> sensor.cable_modem_192_168_100_1_downstream_1_power
    """
    device_registry = dr.async_get(hass)

    # Use detected_modem for model field (shown in device info)
    actual_model = entry.data.get("actual_model")
    detected_modem = entry.data.get("detected_modem")
    manufacturer = entry.data.get("detected_manufacturer", "Unknown")

    # Strip manufacturer prefix from model name (e.g., "Motorola MB7621" -> "MB7621")
    model = actual_model or detected_modem or "Cable Modem Monitor"
    if model and manufacturer and model.lower().startswith(manufacturer.lower()):
        model = model[len(manufacturer) :].strip()

    # Determine device name based on entity_prefix setting
    entity_prefix = entry.data.get(CONF_ENTITY_PREFIX, ENTITY_PREFIX_NONE)
    if entity_prefix == ENTITY_PREFIX_MODEL:
        # Use model name (stripped of manufacturer) for prefix
        device_name = f"Cable Modem {model}"
    elif entity_prefix == ENTITY_PREFIX_IP:
        # Sanitize host for entity ID (replace . and : with _)
        sanitized_host = host.replace(".", "_").replace(":", "_")
        device_name = f"Cable Modem {sanitized_host}"
    else:
        # No prefix (default for single modem setups)
        device_name = "Cable Modem"

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=device_name,
    )

    device_registry.async_update_device(
        device.id,
        manufacturer=manufacturer,
        model=model,
    )
    _LOGGER.debug(
        "Updated device registry: name=%s, manufacturer=%s, model=%s",
        device_name,
        manufacturer,
        model,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # noqa: C901
    """Set up Cable Modem Monitor from a config entry."""
    # Set up log buffer early to capture startup logs for diagnostics
    # This addresses HA 2025.11+ where home-assistant.log was removed
    setup_log_buffer(hass)

    _LOGGER.info("Cable Modem Monitor version %s is starting", VERSION)

    # Extract configuration
    host = entry.data[CONF_HOST]
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    modem_choice = entry.data.get(CONF_MODEM_CHOICE)

    # Load parser for selected modem (user must select modem during config flow)
    selected_parser: ModemParser
    if modem_choice:
        parser_class = await hass.async_add_executor_job(get_parser_by_name, modem_choice)
        if parser_class:
            _LOGGER.info("Loaded parser: %s", modem_choice)
            selected_parser = parser_class()
        else:
            # Parser not found - permanent error, user must reconfigure
            _LOGGER.error("Parser '%s' not found - please reconfigure the integration", modem_choice)
            return False
    else:
        # No modem selected - permanent error, user must reconfigure
        _LOGGER.error("No modem selected - please reconfigure the integration")
        return False

    # Create modem_client
    legacy_ssl = entry.data.get(CONF_LEGACY_SSL, False)
    auth_strategy = entry.data.get(CONF_AUTH_STRATEGY)
    auth_form_config = entry.data.get(CONF_AUTH_FORM_CONFIG)
    auth_hnap_config = entry.data.get(CONF_AUTH_HNAP_CONFIG)
    auth_url_token_config = entry.data.get(CONF_AUTH_URL_TOKEN_CONFIG)

    # Auto-recover from "unknown" auth strategy (failed discovery from previous attempts)
    # Clear it so modem_client uses modem.yaml hints for authentication
    # Also persist the cleared value so we don't repeat this message every restart
    if auth_strategy == "unknown":
        _LOGGER.info("Auth strategy was 'unknown' (previous discovery failed), " "clearing to use modem.yaml hints")
        auth_strategy = None
        # Persist the cleared strategy so this only happens once
        new_data = dict(entry.data)
        new_data[CONF_AUTH_STRATEGY] = None
        hass.config_entries.async_update_entry(entry, data=new_data)

    # Log for entries upgraded from pre-v3.12 that don't have stored auth configs
    # AuthHandler will use defaults for these cases
    _log_missing_auth_config(auth_strategy, auth_hnap_config, auth_url_token_config)

    # Choose orchestrator based on modem selection:
    # - FallbackOrchestrator: For unknown modems, enables auth discovery for HTML capture
    # - DataOrchestrator: For known modems, uses modem.yaml as source of truth
    is_fallback_modem = modem_choice == "Unknown Modem (Fallback Mode)"

    # Base args shared by both orchestrators
    orchestrator_args: dict[str, Any] = {
        "host": host,
        "username": username,
        "password": password,
        "parser": selected_parser,
        "cached_url": entry.data.get(CONF_WORKING_URL),
        "verify_ssl": False,
        "legacy_ssl": legacy_ssl,
        "auth_strategy": auth_strategy,
        "auth_form_config": auth_form_config,
        "auth_hnap_config": auth_hnap_config,
        "auth_url_token_config": auth_url_token_config,
    }

    modem_client: DataOrchestrator
    modem_adapter = None
    if is_fallback_modem:
        # FallbackOrchestrator uses FALLBACK_TIMEOUT (20s) by default
        _LOGGER.info("Using FallbackOrchestrator for unknown modem (auth discovery enabled)")
        modem_client = FallbackOrchestrator(**orchestrator_args)
    else:
        # Known modem - load adapter for timeout and other modem.yaml settings
        parser_name = selected_parser.__class__.__name__
        modem_adapter = await hass.async_add_executor_job(get_auth_adapter_for_parser, parser_name)
        assert modem_adapter is not None  # Known modems always have modem.yaml
        orchestrator_args["timeout"] = modem_adapter.get_timeout()
        _LOGGER.debug("Using DataOrchestrator for known modem (modem.yaml source of truth)")
        modem_client = DataOrchestrator(**orchestrator_args)

    # Create health monitor
    health_monitor = await create_health_monitor(hass, legacy_ssl=legacy_ssl)

    # Get ICMP support setting (auto-detected during setup, re-tested on options change)
    supports_icmp = entry.data.get(CONF_SUPPORTS_ICMP, True)

    # Create coordinator
    async_update_data = create_update_function(hass, modem_client, health_monitor, host, supports_icmp)
    coordinator = DataUpdateCoordinator[dict[str, Any]](
        hass,
        _LOGGER,
        name=f"Cable Modem {host}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
        config_entry=entry,
    )

    # Store modem_client reference for cache invalidation after modem restart
    coordinator.modem_client = modem_client  # type: ignore[attr-defined]

    # Perform initial data fetch
    await perform_initial_refresh(coordinator, entry)

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Migrate entity IDs for DOCSIS 3.0 modems (v3.11+ naming change)
    # Must run before platform setup so sensors don't create duplicates
    # Only applies to known modems - fallback modems don't have entity naming conventions
    # TODO: Remove after v3.14 release when all users have migrated
    if not is_fallback_modem:
        assert modem_adapter is not None  # Known modem path always sets modem_adapter
        docsis_version = entry.data.get(CONF_DOCSIS_VERSION)
        if not docsis_version:
            docsis_version = modem_adapter.get_docsis_version()
            _LOGGER.debug("Using modem.yaml docsis_version for migration: %s", docsis_version)
        migrated = await async_migrate_docsis30_entities(hass, entry, docsis_version)
        if migrated > 0:
            _LOGGER.info("Entity migration complete: %d entities updated", migrated)

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Update device registry
    _update_device_registry(hass, entry, host)

    # Register update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register services (only once)
    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_HISTORY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_HISTORY,
            create_clear_history_handler(hass),
            schema=SERVICE_CLEAR_HISTORY_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_GENERATE_DASHBOARD):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GENERATE_DASHBOARD,
            create_generate_dashboard_handler(hass),
            schema=SERVICE_GENERATE_DASHBOARD_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Try to unload platforms, but handle case where they were never loaded
    try:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    except ValueError as err:
        # Platforms were never loaded (setup failed before platforms were added)
        _LOGGER.debug("Platforms were never loaded for entry %s: %s", entry.entry_id, err)
        unload_ok = True  # Consider it successful since there's nothing to unload

    if unload_ok:
        # Clean up coordinator data
        hass.data[DOMAIN].pop(entry.entry_id, None)

        # Unregister services if this is the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_CLEAR_HISTORY)
            hass.services.async_remove(DOMAIN, SERVICE_GENERATE_DASHBOARD)

    return bool(unload_ok)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
