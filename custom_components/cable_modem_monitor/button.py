"""Button platform for Cable Modem Monitor.

Provides control buttons for modem management:

    ModemRestartButton       Restart modem with post-restart monitoring
    ResetEntitiesButton      Clear entity registry and reload
    UpdateModemDataButton    Trigger immediate data refresh
    CaptureModemDataButton   Capture raw modem data for diagnostics

Architecture:
    Buttons inherit ModemButtonBase which provides device linking and
    a _notify() helper for persistent notifications.

    Restart uses coordinator.scraper (never creates new scrapers) to
    ensure proper auth config. Monitoring is delegated to RestartMonitor.

    Capability checking is in modem_config/capabilities.py.
"""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_ACTUAL_MODEL, CONF_DETECTED_MODEM, CONF_HOST, DOMAIN
from .core.restart_monitor import RestartMonitor
from .modem_config.capabilities import check_restart_support

_LOGGER = logging.getLogger(__name__)

# Notification IDs (single ID per action so updates replace previous)
_NOTIFY_RESTART = "cable_modem_restart"
_NOTIFY_RESET = "cable_modem_reset"
_NOTIFY_UPDATE = "cable_modem_update"
_NOTIFY_CAPTURE = "cable_modem_capture"


class ModemButtonBase(CoordinatorEntity, ButtonEntity):
    """Base class for modem buttons with device linking and notifications."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button with coordinator and config entry."""
        super().__init__(coordinator)
        self._entry = entry

        # Get modem info from config entry
        # NOTE: Device name is kept as "Cable Modem" for entity ID stability.
        # With has_entity_name=True, entity IDs are generated from device name.
        manufacturer = entry.data.get("detected_manufacturer", "Unknown")
        actual_model = entry.data.get(CONF_ACTUAL_MODEL)
        detected_modem = entry.data.get(CONF_DETECTED_MODEM, "Cable Modem")

        # Use actual_model if available, otherwise fall back to detected_modem
        # Strip manufacturer prefix to avoid redundancy (e.g., "Motorola MB7621" -> "MB7621")
        model = actual_model or detected_modem
        if model and manufacturer and model.lower().startswith(manufacturer.lower()):
            model = model[len(manufacturer) :].strip()

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Cable Modem",
            "manufacturer": manufacturer,
            "model": model,
            "configuration_url": f"http://{entry.data[CONF_HOST]}",
        }

    async def _notify(self, title: str, message: str, notification_id: str) -> None:
        """Send a persistent notification.

        Args:
            title: Notification title
            message: Notification body text
            notification_id: ID for updates/dismissal (use _NOTIFY_* constants)
        """
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {"title": title, "message": message, "notification_id": notification_id},
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cable Modem Monitor button."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Check restart availability once during setup (avoid blocking in property)
    restart_available = await check_restart_support(hass, entry)

    # Add control buttons
    # Note: Restart button will show error if modem doesn't support restart
    async_add_entities(
        [
            ModemRestartButton(coordinator, entry, restart_available),
            ResetEntitiesButton(coordinator, entry),
            UpdateModemDataButton(coordinator, entry),
            CaptureModemDataButton(coordinator, entry),
        ]
    )


class ModemRestartButton(ModemButtonBase):
    """Button to restart the cable modem."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, is_available: bool) -> None:
        """Initialize the restart button.

        Args:
            coordinator: Data update coordinator
            entry: Config entry
            is_available: Whether modem supports restart
        """
        super().__init__(coordinator, entry)
        self._attr_name = "Restart Modem"
        self._attr_unique_id = f"{entry.entry_id}_restart_button"
        self._attr_icon = "mdi:restart"
        self._is_available = is_available

    @property
    def available(self) -> bool:
        """Return if button is available (modem supports restart)."""
        return self._is_available

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return additional state attributes."""
        parser_name = self._entry.data.get("parser_name", "Unknown")
        return {
            "parser": parser_name,
            "reason": "Modem does not support remote restart" if not self.available else "Ready",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Modem restart button pressed")

        # Use coordinator's scraper (already has full auth config)
        scraper = getattr(self.coordinator, "scraper", None)
        if not scraper:
            _LOGGER.error("No scraper available - cannot restart modem")
            await self._notify(
                "Modem Restart Failed",
                "Internal error: scraper not available. Try reloading the integration.",
                _NOTIFY_RESTART,
            )
            return

        # Run the restart in an executor since it uses requests (blocking I/O)
        success = await self.hass.async_add_executor_job(scraper.restart_modem)

        if success:
            _LOGGER.info("Modem restart initiated successfully")
            await self._notify(
                "Modem Restart",
                "Modem restart command sent. Monitoring modem status...",
                _NOTIFY_RESTART,
            )

            # Delegate monitoring to RestartMonitor
            monitor = RestartMonitor(
                self.hass,
                self.coordinator,
                lambda title, msg: self._notify(title, msg, _NOTIFY_RESTART),
            )
            self.hass.async_create_task(monitor.start())
        else:
            _LOGGER.warning("Failed to restart modem - may not be supported by this modem model")
            detected_modem = self._entry.data.get("detected_modem", "Unknown")
            await self._notify(
                "Modem Restart Failed",
                f"Failed to restart modem. Your modem ({detected_modem}) may not support "
                "remote restart. Check logs for details.",
                _NOTIFY_RESTART,
            )


class ResetEntitiesButton(ModemButtonBase):
    """Button to reset all entities and reload integration.

    Use cases:
    - After modem replacement (entity names/counts changed)
    - Fixing entity registry issues
    - Starting fresh without deleting integration

    How it works:
    1. Deletes entities from registry (.storage/core.entity_registry)
    2. Reloads integration (triggers async_setup_entry)
    3. Entities recreated with SAME unique_id → SAME entity_id
    4. Historical data preserved (recorder indexes by entity_id)

    Result: Fresh entities, automations work, history intact.
    """

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the reset entities button."""
        super().__init__(coordinator, entry)
        self._attr_name = "Reset Entities"
        self._attr_unique_id = f"{entry.entry_id}_reset_entities_button"
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_entity_registry_enabled_default = True
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
        """Handle button press - remove all entities and reload integration."""
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

        await self._notify(
            "Entity Reset Complete",
            f"Successfully removed {len(entities_to_remove)} entities and reloaded the integration. "
            "New entities have been created.",
            _NOTIFY_RESET,
        )

        _LOGGER.info("Entity reset completed")


class UpdateModemDataButton(ModemButtonBase):
    """Button to manually trigger modem data update."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the update data button."""
        super().__init__(coordinator, entry)
        self._attr_name = "Update Modem Data"
        self._attr_unique_id = f"{entry.entry_id}_update_data_button"
        self._attr_icon = "mdi:update"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Update modem data button pressed")

        # Trigger coordinator refresh
        await self.coordinator.async_request_refresh()

        await self._notify(
            "Modem Data Update",
            "Modem data update has been triggered.",
            _NOTIFY_UPDATE,
        )

        _LOGGER.info("Modem data update triggered")


class CaptureModemDataButton(ModemButtonBase):
    """Button to capture raw modem data for diagnostics."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the capture modem data button."""
        super().__init__(coordinator, entry)
        self._attr_name = "Capture Modem Data"
        self._attr_unique_id = f"{entry.entry_id}_capture_modem_data_button"
        self._attr_icon = "mdi:file-code"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Handle the button press - capture raw modem data for diagnostics."""
        _LOGGER.info("Capture modem data button pressed")

        # Use coordinator's scraper (already has full auth config)
        scraper = getattr(self.coordinator, "scraper", None)
        if not scraper:
            _LOGGER.error("No scraper available - cannot capture modem data")
            await self._notify(
                "Capture Failed",
                "Internal error: scraper not available. Try reloading the integration.",
                _NOTIFY_CAPTURE,
            )
            return

        # Fetch data with capture enabled
        try:
            data = await self.hass.async_add_executor_job(scraper.get_modem_data, True)  # capture_html=True

            # Check if capture was successful
            if "_raw_html_capture" in data:
                capture = data["_raw_html_capture"]
                url_count = len(capture.get("urls", []))
                total_size = sum(url.get("size_bytes", 0) for url in capture.get("urls", []))
                size_kb = total_size / 1024

                # Store capture in coordinator.data for diagnostics download.
                # This is intentional mutation - capture is ephemeral user-triggered
                # data that must survive until the user downloads diagnostics (5 min TTL).
                if self.coordinator.data:
                    self.coordinator.data["_raw_html_capture"] = capture

                _LOGGER.info("Modem data capture successful: %d URLs, %.1f KB total", url_count, size_kb)

                await self._notify(
                    "Capture Complete",
                    f"Captured {url_count} page(s) ({size_kb:.1f} KB). "
                    "Download diagnostics within 5 minutes to retrieve the data. "
                    "Go to: Settings → Devices → Cable Modem → Download Diagnostics.",
                    _NOTIFY_CAPTURE,
                )
            else:
                _LOGGER.warning("Modem data capture failed - no data captured")
                await self._notify(
                    "Capture Failed",
                    "Failed to capture modem data. Check logs for details.",
                    _NOTIFY_CAPTURE,
                )

        except Exception as e:
            _LOGGER.error("Error during modem data capture: %s", e, exc_info=True)
            await self._notify(
                "Capture Error",
                f"Error capturing modem data: {e!s}",
                _NOTIFY_CAPTURE,
            )
