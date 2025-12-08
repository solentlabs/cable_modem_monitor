"""The Cable Modem Monitor integration."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any

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


def _select_parser(parsers: list, modem_choice: str):
    """Select appropriate parser based on user choice.

    Returns either a single parser instance or list of all parsers.
    """
    if not modem_choice or modem_choice == "auto":
        ***REMOVED*** Auto mode - return all parsers
        return parsers

    ***REMOVED*** Strip " *" suffix used to mark unverified parsers in the UI
    modem_choice_clean = modem_choice.rstrip(" *")

    ***REMOVED*** User selected specific parser - find and instantiate it
    for parser_class in parsers:
        if parser_class.name == modem_choice_clean:
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

            ***REMOVED*** Add health monitoring data
            data["health_status"] = health_result.status
            data["health_diagnosis"] = health_result.diagnosis
            data["ping_success"] = health_result.ping_success
            data["ping_latency_ms"] = health_result.ping_latency_ms
            data["http_success"] = health_result.http_success
            data["http_latency_ms"] = health_result.http_latency_ms
            data["consecutive_failures"] = health_monitor.consecutive_failures

            ***REMOVED*** Create indexed lookups for O(1) channel access (performance optimization)
            ***REMOVED*** This prevents O(n) linear searches in each sensor's native_value property
            if "cable_modem_downstream" in data:
                data["_downstream_by_id"] = {
                    int(ch.get("channel_id", ch.get("channel", idx + 1))): ch
                    for idx, ch in enumerate(data["cable_modem_downstream"])
                }
            if "cable_modem_upstream" in data:
                data["_upstream_by_id"] = {
                    int(ch.get("channel_id", ch.get("channel", idx + 1))): ch
                    for idx, ch in enumerate(data["cable_modem_upstream"])
                }

            ***REMOVED*** Add parser metadata for sensor attributes (works without re-adding integration)
            detection_info = scraper.get_detection_info()
            if detection_info:
                data["_parser_release_date"] = detection_info.get("release_date")
                data["_parser_docsis_version"] = detection_info.get("docsis_version")
                data["_parser_fixtures_url"] = detection_info.get("fixtures_url")
                data["_parser_verified"] = detection_info.get("verified", False)

            return data
        except Exception as err:
            ***REMOVED*** If scraper fails but health check succeeded, return partial data
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
        ***REMOVED*** During reload, just do a regular refresh
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

        ***REMOVED*** Get all cable modem entities
        entity_reg = er.async_get(hass)
        cable_modem_entities = [
            entity_entry.entity_id for entity_entry in entity_reg.entities.values() if entity_entry.platform == DOMAIN
        ]

        if not cable_modem_entities:
            _LOGGER.warning("No cable modem entities found in registry")
            return

        _LOGGER.info("Found %s cable modem entities to purge", len(cable_modem_entities))

        ***REMOVED*** Clear history in database
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

        ***REMOVED*** Find metadata IDs for entities
        placeholders = ",".join("?" * len(cable_modem_entities))
        query = f"SELECT metadata_id, entity_id FROM states_meta WHERE entity_id IN ({placeholders})"  ***REMOVED*** nosec B608
        cursor.execute(query, cable_modem_entities)
        metadata_ids = [row[0] for row in cursor.fetchall()]

        if not metadata_ids:
            _LOGGER.warning("No cable modem sensors found in database states")
            conn.close()
            return 0

        ***REMOVED*** Delete old states
        placeholders = ",".join("?" * len(metadata_ids))
        query = f"DELETE FROM states WHERE metadata_id IN ({placeholders}) AND last_updated_ts < ?"  ***REMOVED*** nosec B608
        cursor.execute(query, (*metadata_ids, cutoff_ts))
        states_deleted = cursor.rowcount

        ***REMOVED*** Delete old statistics
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
    query = f"SELECT id FROM statistics_meta WHERE statistic_id IN ({placeholders})"  ***REMOVED*** nosec B608
    cursor.execute(query, cable_modem_entities)
    stats_metadata_ids = [row[0] for row in cursor.fetchall()]

    if not stats_metadata_ids:
        return 0

    placeholders = ",".join("?" * len(stats_metadata_ids))

    ***REMOVED*** Delete from statistics table
    query = f"DELETE FROM statistics WHERE metadata_id IN ({placeholders}) AND start_ts < ?"  ***REMOVED*** nosec B608
    cursor.execute(query, (*stats_metadata_ids, cutoff_ts))
    stats_deleted: int = cursor.rowcount

    ***REMOVED*** Delete from statistics_short_term table
    query = f"DELETE FROM statistics_short_term WHERE metadata_id IN ({placeholders}) AND start_ts < ?"  ***REMOVED*** nosec B608
    cursor.execute(query, (*stats_metadata_ids, cutoff_ts))
    stats_deleted += cursor.rowcount

    return stats_deleted


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cable Modem Monitor from a config entry."""
    _LOGGER.info("Cable Modem Monitor version %s is starting", VERSION)

    ***REMOVED*** Extract configuration
    host = entry.data[CONF_HOST]
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    modem_choice = entry.data.get(CONF_MODEM_CHOICE, "auto")

    ***REMOVED*** Optimization: Only do full parser discovery if needed
    if modem_choice and modem_choice != "auto":
        ***REMOVED*** User selected specific parser - load only that one (fast path)
        from .parsers import get_parser_by_name

        parser_class = await hass.async_add_executor_job(get_parser_by_name, modem_choice)
        if parser_class:
            _LOGGER.info("Loaded specific parser: %s (skipped full discovery)", modem_choice)
            selected_parser = parser_class()
            parser_name_hint = None
        else:
            ***REMOVED*** Fallback to auto if parser not found
            _LOGGER.warning("Parser '%s' not found, falling back to auto discovery", modem_choice)
            from .parsers import get_parsers

            parsers = await hass.async_add_executor_job(get_parsers)
            selected_parser = parsers
            parser_name_hint = entry.data.get(CONF_PARSER_NAME)
    else:
        ***REMOVED*** Auto mode - need all parsers for discovery
        from .parsers import get_parsers

        parsers = await hass.async_add_executor_job(get_parsers)
        selected_parser = parsers
        parser_name_hint = entry.data.get(CONF_PARSER_NAME)

    ***REMOVED*** Create scraper
    scraper = ModemScraper(
        host,
        username,
        password,
        parser=selected_parser,
        cached_url=entry.data.get(CONF_WORKING_URL),
        parser_name=parser_name_hint,
        verify_ssl=VERIFY_SSL,
    )

    ***REMOVED*** Create health monitor
    health_monitor = await _create_health_monitor(hass)

    ***REMOVED*** Create coordinator
    async_update_data = _create_update_function(hass, scraper, health_monitor, host)
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Cable Modem {host}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
        config_entry=entry,
    )

    ***REMOVED*** Store scraper reference for cache invalidation after modem restart
    coordinator.scraper = scraper  ***REMOVED*** type: ignore[attr-defined]

    ***REMOVED*** Perform initial data fetch
    await _perform_initial_refresh(coordinator, entry)

    ***REMOVED*** Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    ***REMOVED*** Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    ***REMOVED*** Update device registry
    _update_device_registry(hass, entry, host)

    ***REMOVED*** Register update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    ***REMOVED*** Register services (only once)
    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_HISTORY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_HISTORY,
            _create_clear_history_handler(hass),
            schema=SERVICE_CLEAR_HISTORY_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    ***REMOVED*** Try to unload platforms, but handle case where they were never loaded
    try:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    except ValueError as err:
        ***REMOVED*** Platforms were never loaded (setup failed before platforms were added)
        _LOGGER.debug("Platforms were never loaded for entry %s: %s", entry.entry_id, err)
        unload_ok = True  ***REMOVED*** Consider it successful since there's nothing to unload

    if unload_ok:
        ***REMOVED*** Clean up coordinator data
        hass.data[DOMAIN].pop(entry.entry_id, None)

        ***REMOVED*** Unregister services if this is the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_CLEAR_HISTORY)

    return bool(unload_ok)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
