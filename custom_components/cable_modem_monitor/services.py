"""Service registration wiring for Cable Modem Monitor.

Registers and unregisters all HA services for this integration.
Dev tool implementations (dashboard generator, channel identity
converter) live in dev_tools.py; this module is a thin registration
layer that imports their handler factories.

Services:
    cable_modem_monitor.generate_dashboard:
        Generates Lovelace YAML for a complete modem dashboard based on
        current channel data.
    cable_modem_monitor.request_refresh:
        Triggers an immediate modem data poll, bypassing connectivity
        backoff. Targets a specific config entry via device_id.
    cable_modem_monitor.request_health_check:
        Triggers an immediate health check (ICMP + HTTP probes).
    cable_modem_monitor.convert_channel_identity:
        Migrates recorder statistics between channel naming modes
        (number ↔ id). Reads target from config entry, finds orphaned
        stats from previous installs, renames via recorder task queue.
    cable_modem_monitor.orphaned_statistics:
        Finds recorder statistics for this modem that have no registered
        entity — left behind by a mode switch, channel rebonding (ID mode),
        or a prefix change. Without execute, returns a preview as comments.
        With execute: true, purges them all directly. Purge is permanent.

See HA_ADAPTER_SPEC.md § Services.
"""

from __future__ import annotations

import logging
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse

from .const import DOMAIN
from .coordinator import CableModemConfigEntry, CableModemRuntimeData
from .dev_tools import (
    _resolve_config_entry_for_device,
    create_convert_channel_identity_handler,
    create_generate_dashboard_handler,
    create_orphaned_statistics_handler,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_GENERATE_DASHBOARD = "generate_dashboard"
SERVICE_REQUEST_REFRESH = "request_refresh"
SERVICE_REQUEST_HEALTH_CHECK = "request_health_check"
SERVICE_CONVERT_CHANNEL_IDENTITY = "convert_channel_identity"
SERVICE_ORPHANED_STATISTICS = "orphaned_statistics"
SERVICE_GENERATE_DASHBOARD_SCHEMA = vol.Schema(
    {
        vol.Optional("device_id"): cv.string,
        vol.Optional("include_downstream_power", default=True): cv.boolean,
        vol.Optional("include_downstream_snr", default=True): cv.boolean,
        vol.Optional("include_downstream_frequency", default=True): cv.boolean,
        vol.Optional("include_upstream_power", default=True): cv.boolean,
        vol.Optional("include_upstream_frequency", default=False): cv.boolean,
        vol.Optional("include_errors", default=True): cv.boolean,
        vol.Optional("include_error_rates", default=False): cv.boolean,
        vol.Optional("include_latency", default=True): cv.boolean,
        vol.Optional("include_status_card", default=True): cv.boolean,
        vol.Optional("graph_hours", default=24): cv.positive_int,
        vol.Optional("short_titles", default=False): cv.boolean,
        vol.Optional("channel_label", default="auto"): vol.In(["auto", "full", "id_only", "type_id"]),
        vol.Optional("channel_grouping", default="by_direction"): vol.In(["by_direction", "by_type"]),
    }
)


# ------------------------------------------------------------------
# Shared refresh helper — used by UpdateModemDataButton and services
# ------------------------------------------------------------------


async def async_request_modem_refresh(runtime: CableModemRuntimeData) -> None:
    """Trigger an immediate modem data poll, bypassing connectivity backoff.

    Resets connectivity backoff, refreshes health probes (if enabled),
    then triggers a data poll. Health runs first so the snapshot
    includes fresh health info.

    Used by UpdateModemDataButton.async_press() and the
    request_refresh service.
    """
    runtime.orchestrator.reset_connectivity()

    if runtime.health_coordinator is not None:
        await runtime.health_coordinator.async_request_refresh()

    await runtime.data_coordinator.async_request_refresh()


# ------------------------------------------------------------------
# Device target resolution
# ------------------------------------------------------------------


def _find_loaded_entries(
    hass: HomeAssistant,
) -> list[CableModemConfigEntry]:
    """Find all loaded config entries for our domain."""
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if hasattr(entry, "runtime_data") and entry.runtime_data is not None
    ]


def _resolve_target_entries(
    hass: HomeAssistant,
    call: ServiceCall,
) -> list[CableModemConfigEntry]:
    """Resolve service call target to loaded config entries.

    Checks for device_id in the service call data (provided by HA when
    the automation uses ``target: {device_id: ...}``). Falls back to all
    loaded entries when no target is specified.
    """
    device_ids = call.data.get("device_id")
    if device_ids:
        if isinstance(device_ids, str):
            device_ids = [device_ids]
        entries: list[CableModemConfigEntry] = []
        for did in device_ids:
            entry = _resolve_config_entry_for_device(hass, did)
            if entry is not None:
                entries.append(entry)
        return entries

    return _find_loaded_entries(hass)


# ------------------------------------------------------------------
# request_refresh / request_health_check handler factories
# ------------------------------------------------------------------


def create_request_refresh_handler(
    hass: HomeAssistant,
) -> Any:
    """Create the request_refresh service handler."""

    async def handle_request_refresh(call: ServiceCall) -> None:
        """Handle the request_refresh service call."""
        entries = _resolve_target_entries(hass, call)
        if not entries:
            _LOGGER.warning("request_refresh: no loaded config entry found for target")
            return

        for entry in entries:
            model = entry.runtime_data.modem_identity.model
            _LOGGER.info("Refresh requested via service [%s]", model)
            await async_request_modem_refresh(entry.runtime_data)

    return handle_request_refresh


def create_request_health_check_handler(
    hass: HomeAssistant,
) -> Any:
    """Create the request_health_check service handler."""

    async def handle_request_health_check(call: ServiceCall) -> None:
        """Handle the request_health_check service call."""
        entries = _resolve_target_entries(hass, call)
        if not entries:
            _LOGGER.warning("request_health_check: no loaded config entry found for target")
            return

        for entry in entries:
            runtime = entry.runtime_data
            model = runtime.modem_identity.model

            if runtime.health_coordinator is None:
                _LOGGER.warning(
                    "Health monitoring is not enabled for %s — skipping health check",
                    model,
                )
                continue

            _LOGGER.info("Health check requested via service [%s]", model)
            await runtime.health_coordinator.async_request_refresh()

    return handle_request_health_check


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------


def async_register_services(hass: HomeAssistant) -> None:
    """Register services (called on first entry setup)."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_DASHBOARD,
        create_generate_dashboard_handler(hass),
        schema=SERVICE_GENERATE_DASHBOARD_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REQUEST_REFRESH,
        create_request_refresh_handler(hass),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REQUEST_HEALTH_CHECK,
        create_request_health_check_handler(hass),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CONVERT_CHANNEL_IDENTITY,
        create_convert_channel_identity_handler(hass),
        schema=vol.Schema(
            {
                vol.Optional("device_id"): cv.string,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ORPHANED_STATISTICS,
        create_orphaned_statistics_handler(hass),
        schema=vol.Schema(
            {
                vol.Optional("device_id"): cv.string,
                vol.Optional("execute", default=False): cv.boolean,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    _LOGGER.debug(
        "Registered services: %s, %s, %s, %s, %s",
        SERVICE_GENERATE_DASHBOARD,
        SERVICE_REQUEST_REFRESH,
        SERVICE_REQUEST_HEALTH_CHECK,
        SERVICE_CONVERT_CHANNEL_IDENTITY,
        SERVICE_ORPHANED_STATISTICS,
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister services (called when last entry is removed)."""
    hass.services.async_remove(DOMAIN, SERVICE_GENERATE_DASHBOARD)
    hass.services.async_remove(DOMAIN, SERVICE_REQUEST_REFRESH)
    hass.services.async_remove(DOMAIN, SERVICE_REQUEST_HEALTH_CHECK)
    hass.services.async_remove(DOMAIN, SERVICE_CONVERT_CHANNEL_IDENTITY)
    hass.services.async_remove(DOMAIN, SERVICE_ORPHANED_STATISTICS)
    _LOGGER.debug("Unregistered services")
