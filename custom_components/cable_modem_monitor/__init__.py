"""The Cable Modem Monitor integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD, DEFAULT_SCAN_INTERVAL, DOMAIN
from .modem_scraper import ModemScraper

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cable Modem Monitor from a config entry."""
    host = entry.data[CONF_HOST]
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

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
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    ***REMOVED*** Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
