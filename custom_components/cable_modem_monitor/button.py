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
        self._attr_name = "Cable Modem Restart Modem"
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
        _LOGGER.info("Modem restart button pressed")

        ***REMOVED*** Get the scraper from the coordinator
        ***REMOVED*** We need to access it from the coordinator's update method
        ***REMOVED*** For now, we'll create a new scraper instance
        from .const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
        from .modem_scraper import ModemScraper

        host = self._entry.data[CONF_HOST]
        username = self._entry.data.get(CONF_USERNAME)
        password = self._entry.data.get(CONF_PASSWORD)

        scraper = ModemScraper(host, username, password)

        ***REMOVED*** Run the restart in an executor since it uses requests (blocking I/O)
        success = await self.hass.async_add_executor_job(scraper.restart_modem)

        if success:
            _LOGGER.info("Modem restart initiated successfully")
        else:
            _LOGGER.error("Failed to restart modem")


class CleanupEntitiesButton(CoordinatorEntity, ButtonEntity):
    """Button to clean up orphaned entities."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Cable Modem Cleanup Entities"
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
