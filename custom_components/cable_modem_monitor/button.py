"""Button platform for Cable Modem Monitor."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_HOST, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ModemButtonBase(CoordinatorEntity, ButtonEntity):
    """Base class for modem buttons."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._entry = entry

        # Get detected modem info from config entry, with fallback to generic values
        manufacturer = entry.data.get("detected_manufacturer", "Unknown")
        model = entry.data.get("detected_modem", "Cable Modem Monitor")

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Cable Modem",
            "manufacturer": manufacturer,
            "model": model,
            "configuration_url": f"http://{entry.data[CONF_HOST]}",
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cable Modem Monitor button."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Add control buttons
    # Note: Restart button will show error if modem doesn't support restart
    async_add_entities([
        ModemRestartButton(coordinator, entry),
        CleanupEntitiesButton(coordinator, entry),
        ResetEntitiesButton(coordinator, entry),
    ])


class ModemRestartButton(ModemButtonBase):
    """Button to restart the cable modem."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry)
        self._attr_name = "Restart Modem"
        self._attr_unique_id = f"{entry.entry_id}_restart_button"
        self._attr_icon = "mdi:restart"

    async def async_press(self) -> None:
        """Handle the button press."""
        import asyncio

        _LOGGER.info("Modem restart button pressed")

        # Get the scraper from the coordinator
        # We need to access it from the coordinator's update method
        # For now, we'll create a new scraper instance
        from .const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_WORKING_URL, VERIFY_SSL
        from .core.modem_scraper import ModemScraper
        from .parsers import get_parsers

        host = self._entry.data[CONF_HOST]
        username = self._entry.data.get(CONF_USERNAME)
        password = self._entry.data.get(CONF_PASSWORD)
        cached_url = self._entry.data.get(CONF_WORKING_URL)
        # Use hardcoded VERIFY_SSL constant (see const.py for security rationale)
        verify_ssl = VERIFY_SSL

        # Get parsers in executor to avoid blocking I/O in async context
        parsers = await self.hass.async_add_executor_job(get_parsers)
        scraper = ModemScraper(host, username, password, parsers, cached_url, verify_ssl=verify_ssl)

        # Run the restart in an executor since it uses requests (blocking I/O)
        success = await self.hass.async_add_executor_job(scraper.restart_modem)

        if success:
            _LOGGER.info("Modem restart initiated successfully")
            # Create a user notification
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Modem Restart",
                    "message": "Modem restart command sent. Monitoring modem status...",
                    "notification_id": "cable_modem_restart",
                },
            )

            # Start monitoring task
            asyncio.create_task(self._monitor_restart())
        else:
            _LOGGER.error("Failed to restart modem")
            # Check if it's an unsupported modem
            detected_modem = self._entry.data.get("detected_modem", "Unknown")
            # Create an error notification with helpful message
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Modem Restart Failed",
                    "message": (
                        f"Failed to restart modem. Your modem ({detected_modem}) may not support "
                        "remote restart. Check logs for details."
                    ),
                    "notification_id": "cable_modem_restart_error",
                },
            )

    async def _monitor_restart(self) -> None:
        """Monitor modem restart and provide status updates."""
        import asyncio
        from datetime import timedelta

        _LOGGER.info("Starting modem restart monitoring")

        # Save original update interval
        original_interval = self.coordinator.update_interval

        try:
            # Set fast polling (10 seconds)
            self.coordinator.update_interval = timedelta(seconds=10)
            _LOGGER.debug("Set polling interval to 10s (original: %s)", original_interval)

            # Wait 5 seconds for modem to go offline
            await asyncio.sleep(5)

            # Phase 1: Wait for modem to respond (even with 0 channels) - max 2 minutes
            # Phase 2: Wait for channels to sync - max 5 additional minutes
            # (cable modems can take 4-5 minutes to acquire all channels)
            phase1_max_wait = 120  # 2 minutes
            phase2_max_wait = 300  # 5 minutes
            elapsed_time = 0
            modem_responding = False
            modem_fully_online = False

            # Phase 1: Wait for HTTP response
            _LOGGER.info("Phase 1: Waiting for modem to respond to HTTP requests...")
            while elapsed_time < phase1_max_wait:
                try:
                    await self.coordinator.async_request_refresh()
                    await asyncio.sleep(10)
                    elapsed_time += 10

                    # Check if modem is responding (even if status is "offline" due to 0 channels)
                    # If we have valid data and last_update_success is True, modem is responding
                    if self.coordinator.last_update_success and self.coordinator.data:
                        status = self.coordinator.data.get("cable_modem_connection_status")
                        _LOGGER.info("Modem responding after %ss (status: %s)", elapsed_time, status)
                        modem_responding = True
                        break
                    else:
                        _LOGGER.debug("Modem not responding yet after %ss", elapsed_time)
                except Exception as e:
                    _LOGGER.debug("Error during phase 1 monitoring: %s", e)
                    await asyncio.sleep(10)
                    elapsed_time += 10

            if not modem_responding:
                _LOGGER.error("Phase 1 failed: Modem did not respond after %ss", phase1_max_wait)
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "Modem Restart Timeout",
                        "message": f"Modem did not respond after {phase1_max_wait} seconds. Check your modem.",
                        "notification_id": "cable_modem_restart",
                    },
                )
                return

            # Phase 2: Wait for channels to sync
            _LOGGER.info("Phase 2: Modem responding, waiting for channel sync...")
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Modem Restarting",
                    "message": f"Modem responding after {elapsed_time}s. Waiting for channels to sync...",
                    "notification_id": "cable_modem_restart",
                },
            )

            phase2_elapsed = 0
            prev_downstream = 0
            prev_upstream = 0
            stable_count = 0  # Track how many times channels have been stable
            grace_period_active = False  # Track if we're in grace period
            grace_period_start = 0  # When grace period started

            while phase2_elapsed < phase2_max_wait:
                try:
                    await self.coordinator.async_request_refresh()
                    await asyncio.sleep(10)
                    phase2_elapsed += 10
                    total_elapsed = elapsed_time + phase2_elapsed

                    downstream_count = self.coordinator.data.get("cable_modem_downstream_channel_count", 0)
                    upstream_count = self.coordinator.data.get("cable_modem_upstream_channel_count", 0)
                    connection_status = self.coordinator.data.get("cable_modem_connection_status")

                    # Check if channels are stable (same count as previous poll)
                    if downstream_count == prev_downstream and upstream_count == prev_upstream:
                        stable_count += 1
                    else:
                        stable_count = 0  # Reset if channels changed
                        grace_period_active = False  # Exit grace period if channels still changing
                        _LOGGER.info(
                            "Phase 2: %ss - Channels still synchronizing: %s→%s down, %s→%s up",
                            phase2_elapsed,
                            prev_downstream,
                            downstream_count,
                            prev_upstream,
                            upstream_count,
                        )

                    prev_downstream = downstream_count
                    prev_upstream = upstream_count

                    # Enter grace period after initial stability (3 polls = 30s)
                    if (
                        connection_status == "online"
                        and downstream_count > 0
                        and upstream_count > 0
                        and stable_count >= 3
                        and not grace_period_active
                    ):
                        grace_period_active = True
                        grace_period_start = phase2_elapsed
                        _LOGGER.info(
                            "Phase 2: %ss - Channels stable (%s down, %s up), "
                            "entering 30s grace period to catch stragglers",
                            total_elapsed,
                            downstream_count,
                            upstream_count,
                        )

                    # Check if grace period is complete (30 more seconds = 3 polls)
                    if grace_period_active and (phase2_elapsed - grace_period_start) >= 30:
                        modem_fully_online = True
                        _LOGGER.info(
                            "Modem fully online with stable channels after %ss total (%s down, %s up)",
                            total_elapsed,
                            downstream_count,
                            upstream_count,
                        )
                        break
                    else:
                        if grace_period_active:
                            grace_elapsed = phase2_elapsed - grace_period_start
                            _LOGGER.debug(
                                "Phase 2: %ss - Grace period: %ss/%ss, Channels: %s down, %s up",
                                phase2_elapsed,
                                grace_elapsed,
                                30,
                                downstream_count,
                                upstream_count,
                            )
                        else:
                            _LOGGER.debug(
                                "Phase 2: %ss - Status: %s, Channels: %s down, %s up (stable: %s polls)",
                                phase2_elapsed,
                                connection_status,
                                downstream_count,
                                upstream_count,
                                stable_count,
                            )
                except Exception as e:
                    _LOGGER.debug("Error during phase 2 monitoring: %s", e)
                    await asyncio.sleep(10)
                    phase2_elapsed += 10

            # Send final notification
            total_time = elapsed_time + phase2_elapsed
            if modem_fully_online:
                downstream_count = self.coordinator.data.get("cable_modem_downstream_channel_count", 0)
                upstream_count = self.coordinator.data.get("cable_modem_upstream_channel_count", 0)
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "Modem Restart Complete",
                        "message": (
                            f"Modem fully online after {total_time}s with {downstream_count} downstream "
                            f"and {upstream_count} upstream channels."
                        ),
                        "notification_id": "cable_modem_restart",
                    },
                )
            else:
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "Modem Restart Warning",
                        "message": (
                            f"Modem responding but channels not fully synced after {total_time}s. "
                            "This may be normal - check modem status."
                        ),
                        "notification_id": "cable_modem_restart",
                    },
                )

        except Exception as e:
            _LOGGER.error("Critical error in restart monitoring: %s", e)
        finally:
            # ALWAYS restore original polling interval, even if there's an error
            self.coordinator.update_interval = original_interval
            _LOGGER.info("Restored polling interval to %s", original_interval)
            # Force one final refresh with restored interval
            await self.coordinator.async_request_refresh()


class CleanupEntitiesButton(ModemButtonBase):
    """Button to clean up orphaned entities."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry)
        self._attr_name = "Cleanup Entities"
        self._attr_unique_id = f"{entry.entry_id}_cleanup_entities_button"
        self._attr_icon = "mdi:broom"

    async def async_press(self) -> None:
        """Handle the button press."""
        from homeassistant.helpers import entity_registry as er

        _LOGGER.info("Cleanup entities button pressed")

        entity_reg = er.async_get(self.hass)

        # Count entities before cleanup
        all_cable_modem = [
            e for e in entity_reg.entities.values()
            if e.platform == DOMAIN
        ]
        orphaned_before = [e for e in all_cable_modem if not e.config_entry_id]

        # Call the cleanup_entities service
        await self.hass.services.async_call(
            DOMAIN,
            "cleanup_entities",
            {},
            blocking=True,
        )

        # Show user notification
        if orphaned_before:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Entity Cleanup Complete",
                    "message": f"Successfully removed {len(orphaned_before)} orphaned cable modem entities.",
                    "notification_id": "cable_modem_cleanup_success",
                },
            )
        else:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Entity Cleanup Complete",
                    "message": "No orphaned entities found. Your entity registry is clean!",
                    "notification_id": "cable_modem_cleanup_success",
                },
            )

        _LOGGER.info("Entity cleanup completed")


class ResetEntitiesButton(ModemButtonBase):
    """Button to reset all entities and reload integration.

    This button is useful for:
    - Cleaning up after modem replacement (when entity names/counts change)
    - Fixing entity registry issues or corruption
    - Starting fresh without deleting the entire integration

    Home Assistant Data Storage Architecture:
    =========================================

    HA stores entity data in TWO separate locations:

    1. Entity Registry (.storage/core.entity_registry)
       - Metadata: entity names, unique_id, entity_id, enabled state, settings
       - What this button DELETES

    2. Recorder Database (home-assistant_v2.db)
       - Historical states, statistics, history graphs
       - Data indexed by entity_id
       - What this button DOES NOT touch

    How Reset Works:
    ================
    1. Delete all entities from registry (removes metadata)
    2. Reload integration (triggers async_setup_entry)
    3. Integration recreates entities with SAME unique_id
       - unique_id = f"{entry.entry_id}_cable_modem_ping_latency"
       - entry.entry_id is STABLE (doesn't change unless integration deleted)
    4. HA generates SAME entity_id from unique_id
       - entity_id = "sensor.cable_modem_ping_latency"
    5. Recorder automatically links new entity to existing historical data
       - Lookup by entity_id matches old data

    Result: Entities reset, automations work, history preserved
    """

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry)
        self._attr_name = "Reset Entities"
        self._attr_unique_id = f"{entry.entry_id}_reset_entities_button"
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_entity_registry_enabled_default = True
        # Add description to explain what this button does
        self._attr_extra_state_attributes = {
            "description": (
                "Removes all cable modem entities from the registry and reloads the integration. "
                "Use this after replacing your modem or to fix entity issues."
            ),
            "entities": (
                "Entities will be recreated with the same IDs. "
                "Automations and dashboards will continue to work."
            ),
            "history": "Historical data should be preserved (stored by entity ID in recorder database).",
            "recommendation": "Create a backup before using if you want to be safe."
        }

    async def async_press(self) -> None:
        """Handle button press - remove all entities and reload integration.

        Process:
        1. Find all entities for this integration (by platform + config_entry_id)
        2. Remove from entity registry (entity_reg.async_remove)
        3. Reload integration (async_reload triggers async_setup_entry)
        4. Integration recreates entities with same unique_id/entity_id
        5. Historical data automatically links by entity_id
        """
        from homeassistant.helpers import entity_registry as er

        _LOGGER.info("Reset entities button pressed")

        entity_reg = er.async_get(self.hass)

        # Find all cable modem entities for this integration
        entities_to_remove = [
            entity_entry.entity_id
            for entity_entry in entity_reg.entities.values()
            if entity_entry.platform == DOMAIN and entity_entry.config_entry_id == self._entry.entry_id
        ]

        _LOGGER.info("Found %s entities to remove", len(entities_to_remove))

        # Remove all entities
        for entity_id in entities_to_remove:
            entity_reg.async_remove(entity_id)
            _LOGGER.debug("Removed entity: %s", entity_id)

        # Reload integration (recreates entities)
        _LOGGER.info("Reloading integration to recreate entities")
        await self.hass.config_entries.async_reload(self._entry.entry_id)

        # Create notification
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Entity Reset Complete",
                "message": (
                    f"Successfully removed {len(entities_to_remove)} entities and reloaded the integration. "
                    "New entities have been created."
                ),
                "notification_id": "cable_modem_reset",
            },
        )

        _LOGGER.info("Entity reset completed")
