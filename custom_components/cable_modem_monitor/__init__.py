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
    CONF_MODEM_CHOICE,
    CONF_PARSER_NAME,
    CONF_WORKING_URL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
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


async def async_migrate_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate entity IDs to include cable_modem_ prefix for v2.0."""
    from homeassistant.helpers import entity_registry as er

    entity_reg = er.async_get(hass)

    # Mapping of old entity ID patterns to new ones
    # This handles migration from pre-v2.0 versions to v2.0 entity naming
    # Simplified patterns - we only support migrating from no-prefix to cable_modem_ prefix
    old_patterns_to_new = {
        # Note: Custom/IP prefixes were never released, so we only handle no-prefix entities
        # Downstream channels (full names)
        r'^sensor\.downstream_ch_(\d+)_(power|snr|frequency|corrected|uncorrected)$':
            'sensor.cable_modem_downstream_ch_{}_{}',
        # Downstream channels (short names - ds_ch)
        r'^sensor\.ds_ch_(\d+)_(power|snr|frequency|corrected|uncorrected)$':
            'sensor.cable_modem_ds_ch_{}_{}',
        # Upstream channels (full names)
        r'^sensor\.upstream_ch_(\d+)_(power|frequency)$':
            'sensor.cable_modem_upstream_ch_{}_{}',
        # Upstream channels (short names - us_ch)
        r'^sensor\.us_ch_(\d+)_(power|frequency)$':
            'sensor.cable_modem_us_ch_{}_{}',
        # Summary sensors (match with or without _errors suffix)
        r'^sensor\.total_(corrected|uncorrected)(?:_errors)?$':
            'sensor.cable_modem_total_{}_errors',
        # Channel counts
        r'^sensor\.downstream_channel_count$':
            'sensor.cable_modem_downstream_channel_count',
        r'^sensor\.upstream_channel_count$':
            'sensor.cable_modem_upstream_channel_count',
        r'^sensor\.ds_channel_count$':
            'sensor.cable_modem_ds_channel_count',
        r'^sensor\.us_channel_count$':
            'sensor.cable_modem_us_channel_count',
        # Status and info (with and without modem_ prefix)
        r'^sensor\.modem_connection_status$':
            'sensor.cable_modem_connection_status',
        r'^sensor\.connection_status$':
            'sensor.cable_modem_connection_status',
        r'^sensor\.software_version$':
            'sensor.cable_modem_software_version',
        r'^sensor\.system_uptime$':
            'sensor.cable_modem_system_uptime',
        r'^sensor\.last_boot_time$':
            'sensor.cable_modem_last_boot_time',
        # Button
        r'^button\.restart_modem$':
            'button.cable_modem_restart_modem',
        r'^button\.cleanup_entities$':
            'button.cable_modem_cleanup_entities',
    }

    import re

    migrations = []

    # Find all entities belonging to this integration
    for entity_entry in entity_reg.entities.values():
        if entity_entry.platform != DOMAIN:
            continue

        if entity_entry.config_entry_id != entry.entry_id:
            continue

        old_entity_id = entity_entry.entity_id

        # Skip if already has cable_modem_ prefix
        if 'cable_modem_' in old_entity_id:
            continue

        # Try to match against patterns and generate new entity ID
        for pattern, template in old_patterns_to_new.items():
            match = re.match(pattern, old_entity_id)
            if match:
                # Extract all captured groups
                groups = match.groups()

                # Generate new entity ID
                if '{}' in template:
                    new_entity_id = template.format(*groups)
                else:
                    new_entity_id = template

                migrations.append((entity_entry, old_entity_id, new_entity_id))
                break

    # Perform migrations
    if migrations:
        _LOGGER.info("Migrating %d entity IDs to v2.0 naming scheme", len(migrations))

        for entity_entry, old_entity_id, new_entity_id in migrations:
            try:
                # Check if target entity ID already exists (from another integration)
                existing_entity = entity_reg.async_get(new_entity_id)
                if existing_entity and existing_entity.platform != DOMAIN:
                    _LOGGER.warning(
                        "Cannot migrate %s -> %s: "
                        "Target entity ID already exists (platform: %s). "
                        "Skipping migration for this entity.",
                        old_entity_id, new_entity_id, existing_entity.platform
                    )
                    continue

                entity_reg.async_update_entity(
                    entity_entry.entity_id,
                    new_entity_id=new_entity_id
                )
                _LOGGER.info("Migrated %s -> %s", old_entity_id, new_entity_id)
            except Exception as e:
                _LOGGER.error("Failed to migrate %s: %s", old_entity_id, e)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cable Modem Monitor from a config entry."""
    # Migrate config entry data to remove old entity prefix settings
    new_data = dict(entry.data)
    removed_keys = []

    # Remove v1.x entity prefix configuration keys
    old_config_keys = ["entity_prefix", "custom_prefix"]
    for key in old_config_keys:
        if key in new_data:
            removed_keys.append(key)
            new_data.pop(key)

    if removed_keys:
        hass.config_entries.async_update_entry(entry, data=new_data)
        _LOGGER.info("Removed deprecated config keys: %s", removed_keys)

    # Migrate entity IDs to v2.0 naming scheme
    await async_migrate_entity_ids(hass, entry)

    host = entry.data[CONF_HOST]
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    cached_url = entry.data.get(CONF_WORKING_URL)  # Get cached URL if available
    parser_name = entry.data.get(CONF_PARSER_NAME)  # Get cached parser name if available
    modem_choice = entry.data.get(CONF_MODEM_CHOICE, "auto")  # Get user's modem selection
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, False)  # Get SSL verification setting

    from .parsers import get_parsers

    # Get parsers in executor to avoid blocking I/O in async context
    parsers = await hass.async_add_executor_job(get_parsers)

    # Respect user's explicit parser selection (Tier 1)
    selected_parser = None
    parser_name_for_tier2 = None

    if modem_choice and modem_choice != "auto":
        # Tier 1: User explicitly selected a parser - use only that one
        for parser_class in parsers:
            if parser_class.name == modem_choice:
                selected_parser = parser_class()  # Instantiate the selected parser
                _LOGGER.info("Using user-selected parser: %s", selected_parser.name)
                break
        if not selected_parser:
            _LOGGER.warning("User selected parser '%s' not found, falling back to auto", modem_choice)
    else:
        # Tier 2/3: Auto mode - use cached parser name if available
        parser_name_for_tier2 = parser_name

    scraper = ModemScraper(
        host,
        username,
        password,
        parser=selected_parser if selected_parser else parsers,
        cached_url=cached_url,
        parser_name=parser_name_for_tier2,
        verify_ssl=verify_ssl,
    )

    # Initialize health monitor for dual-layer diagnostics
    from .core.health_monitor import ModemHealthMonitor
    health_monitor = ModemHealthMonitor(max_history=100)

    async def async_update_data():
        """Fetch data from the modem."""
        try:
            # Run health check first (async, non-blocking)
            base_url = f"http://{host}"
            health_result = await health_monitor.check_health(base_url)

            # Run the scraper in an executor since it uses requests (blocking I/O)
            data = await hass.async_add_executor_job(scraper.get_modem_data)

            # Add health monitoring data to coordinator data
            data["health_status"] = health_result.status
            data["health_diagnosis"] = health_result.diagnosis
            data["ping_success"] = health_result.ping_success
            data["ping_latency_ms"] = health_result.ping_latency_ms
            data["http_success"] = health_result.http_success
            data["http_latency_ms"] = health_result.http_latency_ms
            data["consecutive_failures"] = health_monitor.consecutive_failures

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

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Update device registry with detected modem info
    from homeassistant.helpers import device_registry as dr
    device_registry = dr.async_get(hass)

    # Get or create the device
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"Cable Modem {host}",
    )

    # Update manufacturer and model (these fields require async_update_device)
    device_registry.async_update_device(
        device.id,
        manufacturer=entry.data.get("detected_manufacturer", "Unknown"),
        model=entry.data.get("detected_modem", "Cable Modem Monitor"),
    )
    _LOGGER.debug("Updated device registry: manufacturer=%s, model=%s",
                  entry.data.get('detected_manufacturer'), entry.data.get('detected_modem'))

    # Register update listener to handle options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register services
    async def handle_clear_history(call: ServiceCall) -> None:
        """Handle the clear_history service call."""
        from homeassistant.helpers import entity_registry as er

        days_to_keep = call.data.get("days_to_keep", 30)
        _LOGGER.info("Clearing cable modem history older than %s days", days_to_keep)

        # Get entity registry
        entity_reg = er.async_get(hass)

        # Find all entities belonging to this integration
        cable_modem_entities = []
        for entity_entry in entity_reg.entities.values():
            if entity_entry.platform == DOMAIN:
                cable_modem_entities.append(entity_entry.entity_id)

        if not cable_modem_entities:
            _LOGGER.warning("No cable modem entities found in registry")
            return

        _LOGGER.info("Found %s cable modem entities to purge", len(cable_modem_entities))

        # Use Home Assistant's official recorder purge service
        def clear_db_history():
            """Clear history from database (runs in executor)."""
            try:
                # Calculate cutoff timestamp
                cutoff_date = datetime.now() - timedelta(days=days_to_keep)
                cutoff_ts = cutoff_date.timestamp()

                # Connect to Home Assistant database
                db_path = hass.config.path("home-assistant_v2.db")
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # Find metadata IDs for our entities
                # Security: Using parameterized query with ? placeholders (not user input)
                # The placeholders string only contains "?" characters, values are passed separately
                placeholders = ",".join("?" * len(cable_modem_entities))
                query = "SELECT metadata_id, entity_id FROM states_meta WHERE entity_id IN (" + placeholders + ")"  # nosec B608
                cursor.execute(query, cable_modem_entities)

                metadata_ids = [row[0] for row in cursor.fetchall()]

                if not metadata_ids:
                    _LOGGER.warning("No cable modem sensors found in database states")
                    conn.close()
                    return 0

                # Delete old states
                # Security: Using parameterized query with ? placeholders (not user input)
                # The placeholders string only contains "?" characters, values are passed separately
                placeholders = ",".join("?" * len(metadata_ids))
                query = (
                    "DELETE FROM states WHERE metadata_id IN (" + placeholders + ") "  # nosec B608
                    "AND last_updated_ts < ?"
                )
                cursor.execute(query, (*metadata_ids, cutoff_ts))
                states_deleted = cursor.rowcount

                # Find statistics metadata IDs using entity_id list from registry
                # Security: Using parameterized query with ? placeholders (not user input)
                # The placeholders string only contains "?" characters, values are passed separately
                placeholders = ",".join("?" * len(cable_modem_entities))
                stats_query = "SELECT id FROM statistics_meta WHERE statistic_id IN (" + placeholders + ")"  # nosec B608
                cursor.execute(stats_query, cable_modem_entities)

                stats_metadata_ids = [row[0] for row in cursor.fetchall()]

                # Delete old statistics
                # Security: Using parameterized queries with ? placeholders (not user input)
                # The placeholders string only contains "?" characters, values are passed separately
                stats_deleted = 0
                if stats_metadata_ids:
                    placeholders = ",".join("?" * len(stats_metadata_ids))

                    query = (
                        "DELETE FROM statistics WHERE metadata_id IN (" + placeholders + ") "  # nosec B608
                        "AND start_ts < ?"
                    )
                    cursor.execute(query, (*stats_metadata_ids, cutoff_ts))
                    stats_deleted = cursor.rowcount

                    query_short = (
                        "DELETE FROM statistics_short_term "  # nosec B608
                        "WHERE metadata_id IN (" + placeholders + ") AND start_ts < ?"
                    )
                    cursor.execute(query_short, (*stats_metadata_ids, cutoff_ts))
                    stats_deleted += cursor.rowcount

                conn.commit()

                # Vacuum to reclaim space
                cursor.execute("VACUUM")

                conn.close()

                _LOGGER.info(
                    "Cleared %d state records and %d statistics records older than %d days",
                    states_deleted, stats_deleted, days_to_keep
                )

                return states_deleted + stats_deleted

            except Exception as e:
                _LOGGER.error("Error clearing history: %s", e)
                return 0

        # Run in executor since it's blocking I/O
        deleted = await hass.async_add_executor_job(clear_db_history)

        if deleted > 0:
            _LOGGER.info("Successfully cleared %s historical records", deleted)
        else:
            _LOGGER.warning("No records were deleted")

    async def handle_cleanup_entities(call: ServiceCall) -> None:
        """Handle cleanup_entities service call."""
        from homeassistant.helpers import entity_registry as er

        _LOGGER.info("Starting orphaned entity cleanup")

        entity_reg = er.async_get(hass)

        # Find all cable modem entities
        all_cable_modem = [
            entity_entry
            for entity_entry in entity_reg.entities.values()
            if entity_entry.platform == DOMAIN
        ]

        # Separate active from orphaned
        # An entity is orphaned if it has no config_entry_id
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

    # Register the services only once (check if they're already registered)
    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_HISTORY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_HISTORY,
            handle_clear_history,
            schema=SERVICE_CLEAR_HISTORY_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_CLEANUP_ENTITIES):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEANUP_ENTITIES,
            handle_cleanup_entities,
            schema=SERVICE_CLEANUP_ENTITIES_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

        # Unregister services if this is the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_CLEAR_HISTORY)
            hass.services.async_remove(DOMAIN, SERVICE_CLEANUP_ENTITIES)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
