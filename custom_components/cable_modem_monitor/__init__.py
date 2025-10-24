"""The Cable Modem Monitor integration."""
from __future__ import annotations

from datetime import timedelta, datetime
import logging
import sqlite3

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import (
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .modem_scraper import ModemScraper

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

SERVICE_CLEAR_HISTORY = "clear_history"
SERVICE_CLEAR_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required("days_to_keep"): cv.positive_int,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cable Modem Monitor from a config entry."""
    host = entry.data[CONF_HOST]
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    scraper = ModemScraper(host, username, password)

    async def async_update_data():
        """Fetch data from the modem."""
        try:
            ***REMOVED*** Run the scraper in an executor since it uses requests (blocking I/O)
            data = await hass.async_add_executor_job(scraper.get_modem_data)
            return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with modem: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Cable Modem {host}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    ***REMOVED*** Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    ***REMOVED*** Register update listener to handle options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    ***REMOVED*** Register services
    async def handle_clear_history(call: ServiceCall) -> None:
        """Handle the clear_history service call."""
        from homeassistant.components import recorder
        from homeassistant.helpers import entity_registry as er

        days_to_keep = call.data.get("days_to_keep", 30)
        _LOGGER.info(f"Clearing cable modem history older than {days_to_keep} days")

        ***REMOVED*** Get entity registry
        entity_reg = er.async_get(hass)

        ***REMOVED*** Find all entities belonging to this integration
        cable_modem_entities = []
        for entity_entry in entity_reg.entities.values():
            if entity_entry.platform == DOMAIN:
                cable_modem_entities.append(entity_entry.entity_id)

        if not cable_modem_entities:
            _LOGGER.warning("No cable modem entities found in registry")
            return

        _LOGGER.info(f"Found {len(cable_modem_entities)} cable modem entities to purge")

        ***REMOVED*** Use Home Assistant's official recorder purge service
        def clear_db_history():
            """Clear history from database (runs in executor)."""
            try:
                ***REMOVED*** Calculate cutoff timestamp
                cutoff_date = datetime.now() - timedelta(days=days_to_keep)
                cutoff_ts = cutoff_date.timestamp()

                ***REMOVED*** Connect to Home Assistant database
                db_path = hass.config.path("home-assistant_v2.db")
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                ***REMOVED*** Find metadata IDs for our entities
                placeholders = ",".join("?" * len(cable_modem_entities))
                cursor.execute(
                    f"SELECT metadata_id, entity_id FROM states_meta WHERE entity_id IN ({placeholders})",
                    cable_modem_entities
                )

                metadata_ids = [row[0] for row in cursor.fetchall()]

                if not metadata_ids:
                    _LOGGER.warning("No cable modem sensors found in database states")
                    conn.close()
                    return 0

                ***REMOVED*** Delete old states
                placeholders = ",".join("?" * len(metadata_ids))
                query = (
                    f"DELETE FROM states WHERE metadata_id IN ({placeholders}) "
                    f"AND last_updated_ts < ?"
                )
                cursor.execute(query, (*metadata_ids, cutoff_ts))
                states_deleted = cursor.rowcount

                ***REMOVED*** Find statistics metadata IDs using entity_id list from registry
                ***REMOVED*** Build dynamic query to match any of our entities
                stats_patterns = []
                for entity_id in cable_modem_entities:
                    stats_patterns.append(f"statistic_id = '{entity_id}'")

                stats_query = "SELECT id FROM statistics_meta WHERE " + " OR ".join(stats_patterns)
                cursor.execute(stats_query)

                stats_metadata_ids = [row[0] for row in cursor.fetchall()]

                ***REMOVED*** Delete old statistics
                stats_deleted = 0
                if stats_metadata_ids:
                    placeholders = ",".join("?" * len(stats_metadata_ids))

                    query = (
                        f"DELETE FROM statistics WHERE metadata_id IN ({placeholders}) "
                        f"AND start_ts < ?"
                    )
                    cursor.execute(query, (*stats_metadata_ids, cutoff_ts))
                    stats_deleted = cursor.rowcount

                    query_short = (
                        f"DELETE FROM statistics_short_term "
                        f"WHERE metadata_id IN ({placeholders}) AND start_ts < ?"
                    )
                    cursor.execute(query_short, (*stats_metadata_ids, cutoff_ts))
                    stats_deleted += cursor.rowcount

                conn.commit()

                ***REMOVED*** Vacuum to reclaim space
                cursor.execute("VACUUM")

                conn.close()

                _LOGGER.info(
                    f"Cleared {states_deleted} state records and "
                    f"{stats_deleted} statistics records "
                    f"older than {days_to_keep} days"
                )

                return states_deleted + stats_deleted

            except Exception as e:
                _LOGGER.error(f"Error clearing history: {e}")
                return 0

        ***REMOVED*** Run in executor since it's blocking I/O
        deleted = await hass.async_add_executor_job(clear_db_history)

        if deleted > 0:
            _LOGGER.info(f"Successfully cleared {deleted} historical records")
        else:
            _LOGGER.warning("No records were deleted")

    ***REMOVED*** Register the service only once (check if it's already registered)
    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_HISTORY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_HISTORY,
            handle_clear_history,
            schema=SERVICE_CLEAR_HISTORY_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

        ***REMOVED*** Unregister service if this is the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_CLEAR_HISTORY)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
