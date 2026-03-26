"""Button platform for Cable Modem Monitor.

Provides action buttons for modem management:

    RestartModemButton     Restart modem with post-restart monitoring
    UpdateModemDataButton  Trigger immediate data + health refresh
    ResetEntitiesButton    Clear entity registry and reload

Buttons use plain ButtonEntity (not CoordinatorEntity) — they trigger
actions rather than consuming coordinator data.

See ENTITY_MODEL_SPEC.md § Buttons and HA_ADAPTER_SPEC.md § Restart
Lifecycle.
"""

from __future__ import annotations

import logging
import threading

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from solentlabs.cable_modem_monitor_core.orchestration.models import (
    RestartResult,
)

from .const import DOMAIN
from .coordinator import CableModemConfigEntry

_LOGGER = logging.getLogger(__name__)

# Notification IDs (single ID per action so updates replace previous)
_NOTIFY_RESTART = "cable_modem_restart"
_NOTIFY_RESET = "cable_modem_reset"
_NOTIFY_UPDATE = "cable_modem_update"


# ------------------------------------------------------------------
# Base class
# ------------------------------------------------------------------


class _ButtonBase(ButtonEntity):
    """Base class for modem buttons.

    Uses plain ButtonEntity — buttons trigger actions, they don't
    consume coordinator data.  Device linkage via identifiers.
    """

    _attr_has_entity_name = True

    def __init__(self, entry: CableModemConfigEntry) -> None:
        """Initialize the button with config entry."""
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )

    async def _notify(
        self,
        title: str,
        message: str,
        notification_id: str,
    ) -> None:
        """Send a persistent notification."""
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": title,
                "message": message,
                "notification_id": notification_id,
            },
        )


# ------------------------------------------------------------------
# Platform setup
# ------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CableModemConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cable Modem Monitor button entities."""
    orchestrator = entry.runtime_data.orchestrator

    entities: list[ButtonEntity] = [
        UpdateModemDataButton(entry),
        ResetEntitiesButton(entry),
    ]

    if orchestrator.supports_restart:
        entities.append(RestartModemButton(entry))

    async_add_entities(entities)


# ------------------------------------------------------------------
# Button entities
# ------------------------------------------------------------------


class RestartModemButton(_ButtonBase):
    """Button to restart the cable modem.

    Only created when modem.yaml declares actions.restart.  Runs
    orchestrator.restart() in an executor thread with cooperative
    cancellation via cancel_event.

    See HA_ADAPTER_SPEC.md § Restart Lifecycle.
    """

    def __init__(self, entry: CableModemConfigEntry) -> None:
        """Initialize the restart button."""
        super().__init__(entry)
        self._attr_name = "Restart Modem"
        self._attr_unique_id = f"{entry.entry_id}_restart_button"
        self._attr_icon = "mdi:restart"

    @property
    def available(self) -> bool:
        """Unavailable while a restart is already in progress."""
        return not self._entry.runtime_data.orchestrator.is_restarting

    async def async_press(self) -> None:
        """Handle the button press — restart modem and monitor recovery."""
        runtime = self._entry.runtime_data
        orchestrator = runtime.orchestrator

        if orchestrator.is_restarting:
            _LOGGER.warning("Restart already in progress — ignoring press")
            return

        _LOGGER.info("Modem restart initiated")

        # Create cancel_event for cooperative cancellation
        cancel_event = threading.Event()
        runtime.cancel_event = cancel_event

        try:
            result: RestartResult = await self.hass.async_add_executor_job(orchestrator.restart, cancel_event)
        finally:
            runtime.cancel_event = None

        # Notify user of outcome
        if result.success:
            _LOGGER.info("Modem restart completed in %.0fs", result.elapsed_seconds)
            await self._notify(
                "Modem Restart Complete",
                f"Modem restarted successfully in {result.elapsed_seconds:.0f} seconds.",
                _NOTIFY_RESTART,
            )
        else:
            _LOGGER.warning("Modem restart failed: %s", result.error)
            await self._notify(
                "Modem Restart Failed",
                f"Restart did not complete: {result.error}",
                _NOTIFY_RESTART,
            )

        # Trigger immediate data refresh regardless of outcome
        await runtime.data_coordinator.async_request_refresh()


class UpdateModemDataButton(_ButtonBase):
    """Button to manually trigger modem data update.

    Triggers health probe first, then data collection — so the
    snapshot includes fresh health info.
    """

    def __init__(self, entry: CableModemConfigEntry) -> None:
        """Initialize the update data button."""
        super().__init__(entry)
        self._attr_name = "Update Modem Data"
        self._attr_unique_id = f"{entry.entry_id}_update_data_button"
        self._attr_icon = "mdi:update"

    async def async_press(self) -> None:
        """Handle the button press — refresh health then data."""
        runtime = self._entry.runtime_data

        # Health first so data snapshot includes fresh health info
        if runtime.health_coordinator is not None:
            await runtime.health_coordinator.async_request_refresh()

        await runtime.data_coordinator.async_request_refresh()

        _LOGGER.info("Manual data update triggered")


class ResetEntitiesButton(_ButtonBase):
    """Button to reset all entities and reload integration.

    Removes entities from the registry, then reloads the integration
    to recreate them.  Unique IDs are preserved so entity_ids, history,
    and automations survive the reset.
    """

    def __init__(self, entry: CableModemConfigEntry) -> None:
        """Initialize the reset entities button."""
        super().__init__(entry)
        self._attr_name = "Reset Entities"
        self._attr_unique_id = f"{entry.entry_id}_reset_entities_button"
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Handle button press — remove all entities and reload."""
        entity_reg = er.async_get(self.hass)

        entities_to_remove = [
            entity_entry.entity_id
            for entity_entry in entity_reg.entities.values()
            if (entity_entry.platform == DOMAIN and entity_entry.config_entry_id == self._entry.entry_id)
        ]

        _LOGGER.info("Removing %d entities for reset", len(entities_to_remove))
        for entity_id in entities_to_remove:
            entity_reg.async_remove(entity_id)

        await self.hass.config_entries.async_reload(self._entry.entry_id)

        await self._notify(
            "Entity Reset Complete",
            f"Removed {len(entities_to_remove)} entities and reloaded the integration.",
            _NOTIFY_RESET,
        )
