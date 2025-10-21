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

    # Add restart button and clear history button
    async_add_entities([
        ModemRestartButton(coordinator, entry),
        ClearHistoryButton(coordinator, entry),
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
        _LOGGER.info("Modem restart button pressed")

        # Get the scraper from the coordinator
        # We need to access it from the coordinator's update method
        # For now, we'll create a new scraper instance
        from .const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
        from .modem_scraper import ModemScraper

        host = self._entry.data[CONF_HOST]
        username = self._entry.data.get(CONF_USERNAME)
        password = self._entry.data.get(CONF_PASSWORD)

        scraper = ModemScraper(host, username, password)

        # Run the restart in an executor since it uses requests (blocking I/O)
        success = await self.hass.async_add_executor_job(scraper.restart_modem)

        if success:
            _LOGGER.info("Modem restart initiated successfully")
        else:
            _LOGGER.error("Failed to restart modem")


class ClearHistoryButton(CoordinatorEntity, ButtonEntity):
    """Button to clear old historical data."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Clear History"
        self._attr_unique_id = f"{entry.entry_id}_clear_history_button"
        self._attr_icon = "mdi:delete-clock"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Cable Modem {entry.data['host']}",
            "manufacturer": "Cable Modem",
            "model": "Monitor",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Clear history button pressed")

        # Get configured retention days from config entry
        from .const import CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS
        days_to_keep = self._entry.data.get(CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS)

        # Call the clear_history service
        await self.hass.services.async_call(
            DOMAIN,
            "clear_history",
            {"days_to_keep": days_to_keep},
            blocking=True,
        )

        _LOGGER.info(f"History cleared, kept last {days_to_keep} days")
