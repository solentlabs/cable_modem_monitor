"""The Cable Modem Monitor integration."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any, cast

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_HOST,
    CONF_MODEM_CHOICE,
    CONF_PARSER_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_WORKING_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    VERIFY_SSL,
    VERSION,
)
from .core.modem_scraper import ModemScraper

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

SERVICE_CLEAR_HISTORY = "clear_history"
SERVICE_CLEAR_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required("days_to_keep"): cv.positive_int,
    }
)

SERVICE_CLEANUP_ENTITIES = "cleanup_entities"
SERVICE_CLEANUP_ENTITIES_SCHEMA = vol.Schema({})


def _select_parser(parsers: list, modem_choice: str):
    """Select appropriate parser based on user choice.

    Returns either a single parser instance or list of all parsers.
    """
    if not modem_choice or modem_choice == "auto":
        # Auto mode - return all parsers
        return parsers

    # User selected specific parser - find and instantiate it
    for parser_class in parsers:
        if parser_class.name == modem_choice:
            _LOGGER.info("Using user-selected parser: %s", parser_class.name)
            return parser_class()

    _LOGGER.warning("Parser '%s' not found, falling back to auto", modem_choice)
    return parsers


async def _create_health_monitor(hass: HomeAssistant):
    """Create health monitor with SSL context."""
    import ssl

    from .core.health_monitor import ModemHealthMonitor

    def create_ssl_context():
        """Create SSL context (runs in executor to avoid blocking)."""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    ssl_context = await hass.async_add_executor_job(create_ssl_context)
    return ModemHealthMonitor(max_history=100, verify_ssl=VERIFY_SSL, ssl_context=ssl_context)


def _create_update_function(hass: HomeAssistant, scraper, health_monitor, host: str):
    """Create the async update function for the coordinator."""

    async def async_update_data() -> dict[str, Any]:
        """Fetch data from the modem."""
        base_url = f"http://{host}"
        health_result = await health_monitor.check_health(base_url)

        try:
            data: dict[str, Any] = await hass.async_add_executor_job(scraper.get_modem_data)

            # Add health monitoring data
            data["health_status"] = health_result.status
            data["health_diagnosis"] = health_result.diagnosis
            data["ping_success"] = health_result.ping_success
            data["ping_latency_ms"] = health_result.ping_latency_ms
            data["http_success"] = health_result.http_success
            data["http_latency_ms"] = health_result.http_latency_ms
            data["consecutive_failures"] = health_monitor.consecutive_failures

            return data
        except Exception as err:
            # If scraper fails but health check succeeded, return partial data
            if health_result.ping_success or health_result.http_success:
                _LOGGER.warning("Scraper failed but modem is responding to health checks: %s", err)
                return {
                    "cable_modem_connection_status": "offline",
                    "health_status": health_result.status,
                    "health_diagnosis": health_result.diagnosis,
                    "ping_success": health_result.ping_success,
                    "ping_latency_ms": health_result.ping_latency_ms,
                    "http_success": health_result.http_success,
                    "http_latency_ms": health_result.http_latency_ms,
                    "consecutive_failures": health_monitor.consecutive_failures,
                }
            raise UpdateFailed(f"Error communicating with modem: {err}") from err

    return async_update_data


async def _perform_initial_refresh(coordinator, entry: ConfigEntry) -> None:
    """Perform initial data refresh based on entry state."""
    from homeassistant.config_entries import ConfigEntryState

    if entry.state == ConfigEntryState.SETUP_IN_PROGRESS:
        await coordinator.async_config_entry_first_refresh()
    else:
        # During reload, just do a regular refresh
        await coordinator.async_refresh()


def _update_device_registry(hass: HomeAssistant, entry: ConfigEntry, host: str) -> None:
    """Update device registry with detected modem info."""
    from homeassistant.helpers import device_registry as dr

    device_registry = dr.async_get(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"Cable Modem {host}",
    )

    device_registry.async_update_device(
        device.id,
        manufacturer=entry.data.get("detected_manufacturer", "Unknown"),
        model=entry.data.get("detected_modem", "Cable Modem Monitor"),
    )
    _LOGGER.debug(
        "Updated device registry: manufacturer=%s, model=%s",
        entry.data.get("detected_manufacturer"),
        entry.data.get("detected_modem"),
    )


def _create_clear_history_handler(hass: HomeAssistant):
    """Create the clear history service handler."""

    async def handle_clear_history(call: ServiceCall) -> None:
        """Handle the clear_history service call."""
        from homeassistant.helpers import entity_registry as er

        days_to_keep = call.data.get("days_to_keep", 30)
        _LOGGER.info("Clearing cable modem history older than %s days", days_to_keep)

        # Get all cable modem entities
        entity_reg = er.async_get(hass)
        cable_modem_entities = [
            entity_entry.entity_id for entity_entry in entity_reg.entities.values() if entity_entry.platform == DOMAIN
        ]

        if not cable_modem_entities:
            _LOGGER.warning("No cable modem entities found in registry")
            return

        _LOGGER.info("Found %s cable modem entities to purge", len(cable_modem_entities))

        # Clear history in database
        deleted = await hass.async_add_executor_job(_clear_db_history, hass, cable_modem_entities, days_to_keep)

        if deleted > 0:
            _LOGGER.info("Successfully cleared %s historical records", deleted)
        else:
            _LOGGER.warning("No records were deleted")

    return handle_clear_history


def _clear_db_history(hass: HomeAssistant, cable_modem_entities: list, days_to_keep: int) -> int:
    """Clear history from database (runs in executor)."""
    try:
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cutoff_ts = cutoff_date.timestamp()

        db_path = hass.config.path("home-assistant_v2.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Find metadata IDs for entities
        placeholders = ",".join("?" * len(cable_modem_entities))
        query = f"SELECT metadata_id, entity_id FROM states_meta WHERE entity_id IN ({placeholders})"  # nosec B608
        cursor.execute(query, cable_modem_entities)
        metadata_ids = [row[0] for row in cursor.fetchall()]

        if not metadata_ids:
            _LOGGER.warning("No cable modem sensors found in database states")
            conn.close()
            return 0

        # Delete old states
        placeholders = ",".join("?" * len(metadata_ids))
        query = f"DELETE FROM states WHERE metadata_id IN ({placeholders}) AND last_updated_ts < ?"  # nosec B608
        cursor.execute(query, (*metadata_ids, cutoff_ts))
        states_deleted = cursor.rowcount

        # Delete old statistics
        stats_deleted = _delete_statistics(cursor, cable_modem_entities, cutoff_ts)

        conn.commit()
        cursor.execute("VACUUM")
        conn.close()

        _LOGGER.info(
            "Cleared %d state records and %d statistics records older than %d days",
            states_deleted,
            stats_deleted,
            days_to_keep,
        )

        return states_deleted + stats_deleted

    except Exception as e:
        _LOGGER.error("Error clearing history: %s", e)
        return 0


def _delete_statistics(cursor, cable_modem_entities: list, cutoff_ts: float) -> int:
    """Delete statistics records (helper for _clear_db_history)."""
    placeholders = ",".join("?" * len(cable_modem_entities))
    query = f"SELECT id FROM statistics_meta WHERE statistic_id IN ({placeholders})"  # nosec B608
    cursor.execute(query, cable_modem_entities)
    stats_metadata_ids = [row[0] for row in cursor.fetchall()]

    if not stats_metadata_ids:
        return 0

    placeholders = ",".join("?" * len(stats_metadata_ids))

    # Delete from statistics table
    query = f"DELETE FROM statistics WHERE metadata_id IN ({placeholders}) AND start_ts < ?"  # nosec B608
    cursor.execute(query, (*stats_metadata_ids, cutoff_ts))
    stats_deleted: int = cursor.rowcount

    # Delete from statistics_short_term table
    query = f"DELETE FROM statistics_short_term WHERE metadata_id IN ({placeholders}) AND start_ts < ?"  # nosec B608
    cursor.execute(query, (*stats_metadata_ids, cutoff_ts))
    stats_deleted += cursor.rowcount

    return stats_deleted


def _create_cleanup_entities_handler(hass: HomeAssistant):
    """Create the cleanup entities service handler."""

    async def handle_cleanup_entities(call: ServiceCall) -> None:
        """Handle cleanup_entities service call."""
        from homeassistant.helpers import entity_registry as er

        _LOGGER.info("Starting orphaned entity cleanup")

        entity_reg = er.async_get(hass)

        # Find all cable modem entities
        all_cable_modem = [
            entity_entry for entity_entry in entity_reg.entities.values() if entity_entry.platform == DOMAIN
        ]

        # Separate active from orphaned
        active = [e for e in all_cable_modem if e.config_entry_id]
        orphaned = [e for e in all_cable_modem if not e.config_entry_id]

        _LOGGER.info(
            f"Found {len(all_cable_modem)} total cable modem entities: "
            f"{len(active)} active, {len(orphaned)} orphaned"
        )

        if not orphaned:
            _LOGGER.info("No orphaned entities found - cleanup not needed")
            return

        # Remove orphaned entities
        removed_count = 0
        for entity_entry in orphaned:
            try:
                entity_reg.async_remove(entity_entry.entity_id)
                _LOGGER.debug("Removed orphaned entity: %s", entity_entry.entity_id)
                removed_count += 1
            except Exception as e:
                _LOGGER.error("Failed to remove %s: %s", entity_entry.entity_id, e)

        _LOGGER.info("Successfully removed %s orphaned entities", removed_count)

    return handle_cleanup_entities


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cable Modem Monitor from a config entry."""
    _LOGGER.info("Cable Modem Monitor version %s is starting", VERSION)

    # Extract configuration
    host = entry.data[CONF_HOST]
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    modem_choice = entry.data.get(CONF_MODEM_CHOICE, "auto")

    # Optimization: Only do full parser discovery if needed
    if modem_choice and modem_choice != "auto":
        # User selected specific parser - load only that one (fast path)
        from .parsers import get_parser_by_name

        parser_class = await hass.async_add_executor_job(get_parser_by_name, modem_choice)
        if parser_class:
            _LOGGER.info("Loaded specific parser: %s (skipped full discovery)", modem_choice)
            selected_parser = parser_class()
            parser_name_hint = None
        else:
            # Fallback to auto if parser not found
            _LOGGER.warning("Parser '%s' not found, falling back to auto discovery", modem_choice)
            from .parsers import get_parsers

            parsers = await hass.async_add_executor_job(get_parsers)
            selected_parser = parsers
            parser_name_hint = entry.data.get(CONF_PARSER_NAME)
    else:
        # Auto mode - need all parsers for discovery
        from .parsers import get_parsers

        parsers = await hass.async_add_executor_job(get_parsers)
        selected_parser = parsers
        parser_name_hint = entry.data.get(CONF_PARSER_NAME)

    # Create scraper
    scraper = ModemScraper(
        host,
        username,
        password,
        parser=selected_parser,
        cached_url=entry.data.get(CONF_WORKING_URL),
        parser_name=parser_name_hint,
        verify_ssl=VERIFY_SSL,
    )

    # Create health monitor
    health_monitor = await _create_health_monitor(hass)

    # Create coordinator
    async_update_data = _create_update_function(hass, scraper, health_monitor, host)
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Cable Modem {host}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
        config_entry=entry,
    )

    # Perform initial data fetch
    await _perform_initial_refresh(coordinator, entry)

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

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
            _create_clear_history_handler(hass),
            schema=SERVICE_CLEAR_HISTORY_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_CLEANUP_ENTITIES):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEANUP_ENTITIES,
            _create_cleanup_entities_handler(hass),
            schema=SERVICE_CLEANUP_ENTITIES_SCHEMA,
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
            hass.services.async_remove(DOMAIN, SERVICE_CLEANUP_ENTITIES)

    return bool(unload_ok)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
