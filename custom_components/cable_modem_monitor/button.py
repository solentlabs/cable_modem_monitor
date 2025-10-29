"""Button platform for Cable Modem Monitor."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cable Modem Monitor button."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    ***REMOVED*** Add control buttons
    ***REMOVED*** Note: Restart button will show error if modem doesn't support restart
    async_add_entities([
        ModemRestartButton(coordinator, entry),
        CleanupEntitiesButton(coordinator, entry),
    ])


class ModemRestartButton(CoordinatorEntity, ButtonEntity):
    """Button to restart the cable modem."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Restart Modem"
        self._attr_unique_id = f"{entry.entry_id}_restart_button"
        self._attr_icon = "mdi:restart"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Cable Modem {entry.data['host']}",
            "manufacturer": "Cable Modem",
            "model": "Monitor",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        import asyncio
        from datetime import timedelta

        _LOGGER.info("Modem restart button pressed")

        ***REMOVED*** Get the scraper from the coordinator
        ***REMOVED*** We need to access it from the coordinator's update method
        ***REMOVED*** For now, we'll create a new scraper instance
        from .const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_WORKING_URL
        from .modem_scraper import ModemScraper
        from .parsers import get_parsers

        host = self._entry.data[CONF_HOST]
        username = self._entry.data.get(CONF_USERNAME)
        password = self._entry.data.get(CONF_PASSWORD)
        cached_url = self._entry.data.get(CONF_WORKING_URL)

        ***REMOVED*** Get parsers in executor to avoid blocking I/O in async context
        parsers = await self.hass.async_add_executor_job(get_parsers)
        scraper = ModemScraper(host, username, password, parsers, cached_url)

        ***REMOVED*** Run the restart in an executor since it uses requests (blocking I/O)
        success = await self.hass.async_add_executor_job(scraper.restart_modem)

        if success:
            _LOGGER.info("Modem restart initiated successfully")
            ***REMOVED*** Create a user notification
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Modem Restart",
                    "message": "Modem restart command sent. Monitoring modem status...",
                    "notification_id": "cable_modem_restart",
                },
            )

            ***REMOVED*** Start monitoring task
            asyncio.create_task(self._monitor_restart())
        else:
            _LOGGER.error("Failed to restart modem")
            ***REMOVED*** Check if it's an unsupported modem
            detected_modem = self._entry.data.get("detected_modem", "Unknown")
            ***REMOVED*** Create an error notification with helpful message
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Modem Restart Failed",
                    "message": f"Failed to restart modem. Your modem ({detected_modem}) may not support remote restart. Check logs for details.",
                    "notification_id": "cable_modem_restart_error",
                },
            )

    async def _monitor_restart(self) -> None:
        """Monitor modem restart and provide status updates."""
        import asyncio
        from datetime import timedelta

        _LOGGER.info("Starting modem restart monitoring")

        ***REMOVED*** Save original update interval
        original_interval = self.coordinator.update_interval

        try:
            ***REMOVED*** Set fast polling (10 seconds)
            self.coordinator.update_interval = timedelta(seconds=10)
            _LOGGER.debug(f"Set polling interval to 10s (original: {original_interval})")

            ***REMOVED*** Wait 5 seconds for modem to go offline
            await asyncio.sleep(5)

            ***REMOVED*** Phase 1: Wait for modem to respond (even with 0 channels) - max 2 minutes
            ***REMOVED*** Phase 2: Wait for channels to sync - max 5 additional minutes
            ***REMOVED*** (cable modems can take 4-5 minutes to acquire all channels)
            phase1_max_wait = 120  ***REMOVED*** 2 minutes
            phase2_max_wait = 300  ***REMOVED*** 5 minutes
            elapsed_time = 0
            modem_responding = False
            modem_fully_online = False

            ***REMOVED*** Phase 1: Wait for HTTP response
            _LOGGER.info("Phase 1: Waiting for modem to respond to HTTP requests...")
            while elapsed_time < phase1_max_wait:
                try:
                    await self.coordinator.async_request_refresh()
                    await asyncio.sleep(10)
                    elapsed_time += 10

                    ***REMOVED*** Check if modem is responding (even if status is "offline" due to 0 channels)
                    ***REMOVED*** If we have valid data and last_update_success is True, modem is responding
                    if self.coordinator.last_update_success and self.coordinator.data:
                        status = self.coordinator.data.get("cable_modem_connection_status")
                        _LOGGER.info(f"Modem responding after {elapsed_time}s (status: {status})")
                        modem_responding = True
                        break
                    else:
                        _LOGGER.debug(f"Modem not responding yet after {elapsed_time}s")
                except Exception as e:
                    _LOGGER.debug(f"Error during phase 1 monitoring: {e}")
                    await asyncio.sleep(10)
                    elapsed_time += 10

            if not modem_responding:
                _LOGGER.error(f"Phase 1 failed: Modem did not respond after {phase1_max_wait}s")
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

            ***REMOVED*** Phase 2: Wait for channels to sync
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
            while phase2_elapsed < phase2_max_wait:
                try:
                    await self.coordinator.async_request_refresh()
                    await asyncio.sleep(10)
                    phase2_elapsed += 10
                    total_elapsed = elapsed_time + phase2_elapsed

                    ***REMOVED*** Check if modem has channels (fully online)
                    if self.coordinator.data.get("cable_modem_connection_status") == "online":
                        modem_fully_online = True
                        _LOGGER.info(f"Modem fully online with channels after {total_elapsed}s total")
                        break
                    else:
                        downstream_count = self.coordinator.data.get("cable_modem_downstream_channel_count", 0)
                        upstream_count = self.coordinator.data.get("cable_modem_upstream_channel_count", 0)
                        _LOGGER.debug(f"Phase 2: {phase2_elapsed}s - Channels: {downstream_count} down, {upstream_count} up")
                except Exception as e:
                    _LOGGER.debug(f"Error during phase 2 monitoring: {e}")
                    await asyncio.sleep(10)
                    phase2_elapsed += 10

            ***REMOVED*** Send final notification
            total_time = elapsed_time + phase2_elapsed
            if modem_fully_online:
                downstream_count = self.coordinator.data.get("cable_modem_downstream_channel_count", 0)
                upstream_count = self.coordinator.data.get("cable_modem_upstream_channel_count", 0)
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "Modem Restart Complete",
                        "message": f"Modem fully online after {total_time}s with {downstream_count} downstream and {upstream_count} upstream channels.",
                        "notification_id": "cable_modem_restart",
                    },
                )
            else:
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "Modem Restart Warning",
                        "message": f"Modem responding but channels not fully synced after {total_time}s. This may be normal - check modem status.",
                        "notification_id": "cable_modem_restart",
                    },
                )

        except Exception as e:
            _LOGGER.error(f"Critical error in restart monitoring: {e}")
        finally:
            ***REMOVED*** ALWAYS restore original polling interval, even if there's an error
            self.coordinator.update_interval = original_interval
            _LOGGER.info(f"Restored polling interval to {original_interval}")
            ***REMOVED*** Force one final refresh with restored interval
            await self.coordinator.async_request_refresh()


class CleanupEntitiesButton(CoordinatorEntity, ButtonEntity):
    """Button to clean up orphaned entities."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Cleanup Entities"
        self._attr_unique_id = f"{entry.entry_id}_cleanup_entities_button"
        self._attr_icon = "mdi:broom"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Cable Modem {entry.data['host']}",
            "manufacturer": "Cable Modem",
            "model": "Monitor",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        from homeassistant.helpers import entity_registry as er

        _LOGGER.info("Cleanup entities button pressed")

        entity_reg = er.async_get(self.hass)

        ***REMOVED*** Count entities before cleanup
        all_cable_modem = [
            e for e in entity_reg.entities.values()
            if e.platform == DOMAIN
        ]
        orphaned_before = [e for e in all_cable_modem if not e.config_entry_id]

        ***REMOVED*** Call the cleanup_entities service
        await self.hass.services.async_call(
            DOMAIN,
            "cleanup_entities",
            {},
            blocking=True,
        )

        ***REMOVED*** Show user notification
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
