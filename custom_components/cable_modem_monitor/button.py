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
    async_add_entities(
        [
            ModemRestartButton(coordinator, entry),
            CleanupEntitiesButton(coordinator, entry),
            ResetEntitiesButton(coordinator, entry),
            UpdateModemDataButton(coordinator, entry),
            CaptureHtmlButton(coordinator, entry),
        ]
    )


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
        from .const import (
            CONF_HOST as HOST_KEY,
            CONF_PASSWORD,
            CONF_USERNAME,
            CONF_WORKING_URL,
            VERIFY_SSL,
        )
        from .core.modem_scraper import ModemScraper
        from .parsers import get_parsers

        host = self._entry.data[HOST_KEY]
        username = self._entry.data.get(CONF_USERNAME)
        password = self._entry.data.get(CONF_PASSWORD)
        cached_url = self._entry.data.get(CONF_WORKING_URL)
        modem_choice = self._entry.data.get("modem_choice", "auto")
        # Use hardcoded VERIFY_SSL constant (see const.py for security rationale)
        verify_ssl = VERIFY_SSL

        # Optimization: Only load the specific parser if user selected one
        if modem_choice and modem_choice != "auto":
            from .parsers import get_parser_by_name

            parser_class = await self.hass.async_add_executor_job(get_parser_by_name, modem_choice)
            if parser_class:
                parser = parser_class()
                scraper = ModemScraper(host, username, password, parser, cached_url, verify_ssl=verify_ssl)
            else:
                # Fallback to all parsers
                parsers = await self.hass.async_add_executor_job(get_parsers)
                scraper = ModemScraper(host, username, password, parsers, cached_url, verify_ssl=verify_ssl)
        else:
            # Auto mode - get all parsers (but use cache for speed)
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

    async def _wait_for_modem_response(self, max_wait: int) -> tuple[bool, int]:
        """Phase 1: Wait for modem to respond to HTTP requests.

        Returns:
            Tuple of (modem_responding, elapsed_time)
        """
        import asyncio

        _LOGGER.info("Phase 1: Waiting for modem to respond to HTTP requests...")
        elapsed_time = 0

        while elapsed_time < max_wait:
            try:
                await self.coordinator.async_request_refresh()
                await asyncio.sleep(10)
                elapsed_time += 10

                if self.coordinator.last_update_success and self.coordinator.data:
                    status = self.coordinator.data.get("cable_modem_connection_status")
                    _LOGGER.info("Modem responding after %ss (status: %s)", elapsed_time, status)
                    return True, elapsed_time

                _LOGGER.debug("Modem not responding yet after %ss", elapsed_time)
            except Exception as e:
                _LOGGER.debug("Error during phase 1 monitoring: %s", e)
                await asyncio.sleep(10)
                elapsed_time += 10

        return False, elapsed_time

    async def _wait_for_channel_sync(self, max_wait: int) -> tuple[bool, int]:
        """Phase 2: Wait for channels to synchronize.

        Returns:
            Tuple of (modem_fully_online, phase2_elapsed)
        """
        import asyncio

        _LOGGER.info("Phase 2: Modem responding, waiting for channel sync...")
        phase2_elapsed = 0
        prev_downstream = 0
        prev_upstream = 0
        stable_count = 0
        grace_period_active = False
        grace_period_start = 0

        while phase2_elapsed < max_wait:
            try:
                await self.coordinator.async_request_refresh()
                await asyncio.sleep(10)
                phase2_elapsed += 10

                downstream_count = self.coordinator.data.get("cable_modem_downstream_channel_count", 0)
                upstream_count = self.coordinator.data.get("cable_modem_upstream_channel_count", 0)
                connection_status = self.coordinator.data.get("cable_modem_connection_status")

                # Check if channels are stable
                if downstream_count == prev_downstream and upstream_count == prev_upstream:
                    stable_count += 1
                else:
                    stable_count = 0
                    grace_period_active = False
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

                # Enter grace period after initial stability
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
                        "Phase 2: Channels stable (%s down, %s up), entering 30s grace period",
                        downstream_count,
                        upstream_count,
                    )

                # Check if grace period is complete
                if grace_period_active and (phase2_elapsed - grace_period_start) >= 30:
                    _LOGGER.info(
                        "Modem fully online with stable channels (%s down, %s up)", downstream_count, upstream_count
                    )
                    return True, phase2_elapsed

            except Exception as e:
                _LOGGER.debug("Error during phase 2 monitoring: %s", e)
                await asyncio.sleep(10)
                phase2_elapsed += 10

        return False, phase2_elapsed

    async def _send_restart_notification(
        self, modem_responding: bool, modem_fully_online: bool, total_time: int
    ) -> None:
        """Send final notification about restart status."""
        if not modem_responding:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Modem Restart Timeout",
                    "message": f"Modem did not respond after {total_time} seconds. Check your modem.",
                    "notification_id": "cable_modem_restart",
                },
            )
        elif modem_fully_online:
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

            # Phase 1: Wait for modem to respond (max 2 minutes)
            phase1_max_wait = 120
            modem_responding, elapsed_time = await self._wait_for_modem_response(phase1_max_wait)

            if not modem_responding:
                _LOGGER.error("Phase 1 failed: Modem did not respond after %ss", phase1_max_wait)
                await self._send_restart_notification(False, False, elapsed_time)
                return

            # Send intermediate notification
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Modem Restarting",
                    "message": f"Modem responding after {elapsed_time}s. Waiting for channels to sync...",
                    "notification_id": "cable_modem_restart",
                },
            )

            # Phase 2: Wait for channels to sync (max 5 minutes)
            phase2_max_wait = 300
            modem_fully_online, phase2_elapsed = await self._wait_for_channel_sync(phase2_max_wait)

            # Send final notification
            total_time = elapsed_time + phase2_elapsed
            await self._send_restart_notification(modem_responding, modem_fully_online, total_time)

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
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Handle the button press."""
        from homeassistant.helpers import entity_registry as er

        _LOGGER.info("Cleanup entities button pressed")

        entity_reg = er.async_get(self.hass)

        # Count entities before cleanup
        all_cable_modem = [e for e in entity_reg.entities.values() if e.platform == DOMAIN]
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
                "Entities will be recreated with the same IDs. " "Automations and dashboards will continue to work."
            ),
            "history": "Historical data should be preserved (stored by entity ID in recorder database).",
            "recommendation": "Create a backup before using if you want to be safe.",
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


class UpdateModemDataButton(ModemButtonBase):
    """Button to manually trigger modem data update."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry)
        self._attr_name = "Update Modem Data"
        self._attr_unique_id = f"{entry.entry_id}_update_data_button"
        self._attr_icon = "mdi:update"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Update modem data button pressed")

        # Trigger coordinator refresh
        await self.coordinator.async_request_refresh()

        # Create notification
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Modem Data Update",
                "message": "Modem data update has been triggered.",
                "notification_id": "cable_modem_update",
            },
        )

        _LOGGER.info("Modem data update triggered")


class CaptureHtmlButton(ModemButtonBase):
    """Button to capture raw HTML for diagnostics."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry)
        self._attr_name = "Capture HTML"
        self._attr_unique_id = f"{entry.entry_id}_capture_html_button"
        self._attr_icon = "mdi:file-code"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Handle the button press - capture raw HTML for diagnostics."""
        _LOGGER.info("Capture HTML button pressed")

        # Get the scraper components from coordinator
        from .const import (
            CONF_HOST as HOST_KEY,
            CONF_PASSWORD,
            CONF_USERNAME,
            CONF_WORKING_URL,
            VERIFY_SSL,
        )
        from .core.modem_scraper import ModemScraper
        from .parsers import get_parsers

        host = self._entry.data[HOST_KEY]
        username = self._entry.data.get(CONF_USERNAME)
        password = self._entry.data.get(CONF_PASSWORD)
        cached_url = self._entry.data.get(CONF_WORKING_URL)
        modem_choice = self._entry.data.get("modem_choice", "auto")
        verify_ssl = VERIFY_SSL

        # Load parser (same logic as restart button)
        if modem_choice and modem_choice != "auto":
            from .parsers import get_parser_by_name

            parser_class = await self.hass.async_add_executor_job(get_parser_by_name, modem_choice)
            if parser_class:
                parser = parser_class()
                scraper = ModemScraper(host, username, password, parser, cached_url, verify_ssl=verify_ssl)
            else:
                parsers = await self.hass.async_add_executor_job(get_parsers)
                scraper = ModemScraper(host, username, password, parsers, cached_url, verify_ssl=verify_ssl)
        else:
            parsers = await self.hass.async_add_executor_job(get_parsers)
            scraper = ModemScraper(host, username, password, parsers, cached_url, verify_ssl=verify_ssl)

        # Fetch data with HTML capture enabled
        try:
            data = await self.hass.async_add_executor_job(scraper.get_modem_data, True)

            # Check if capture was successful
            if "_raw_html_capture" in data:
                capture = data["_raw_html_capture"]
                url_count = len(capture.get("urls", []))
                total_size = sum(url.get("size_bytes", 0) for url in capture.get("urls", []))
                size_kb = total_size / 1024

                # Update coordinator data with the capture
                # This makes it available to diagnostics for the next 5 minutes
                if self.coordinator.data:
                    self.coordinator.data["_raw_html_capture"] = capture

                _LOGGER.info("HTML capture successful: %d URLs, %.1f KB total", url_count, size_kb)

                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "HTML Capture Complete",
                        "message": (
                            f"Captured {url_count} page(s) ({size_kb:.1f} KB). "
                            "Download diagnostics within 5 minutes to retrieve the data. "
                            "Go to: Settings → Devices → Cable Modem → Download Diagnostics."
                        ),
                        "notification_id": "cable_modem_html_capture",
                    },
                )
            else:
                _LOGGER.warning("HTML capture failed - no data captured")
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "HTML Capture Failed",
                        "message": "Failed to capture HTML data. Check logs for details.",
                        "notification_id": "cable_modem_html_capture",
                    },
                )

        except Exception as e:
            _LOGGER.error("Error during HTML capture: %s", e, exc_info=True)
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "HTML Capture Error",
                    "message": f"Error capturing HTML: {str(e)}",
                    "notification_id": "cable_modem_html_capture",
                },
            )
