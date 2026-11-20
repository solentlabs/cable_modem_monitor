"""Base entity shared by every Cable Modem Monitor sensor and button.

Links the entity to the modem's device and turns on ``has_entity_name``
(HA quality scale common-modules). Data sensors, health sensors and
buttons read from different sources (data coordinator, health
coordinator, none), so this base holds only what they share and the
platform bases add their own coordinator.
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_ENTITY_PREFIX, DOMAIN
from .coordinator import CableModemConfigEntry
from .lib.utils import get_device_name


class CableModemEntity:
    """An entity attached to the config entry's modem device.

    Listed after the platform class (SensorEntity, ButtonEntity), which
    already supplies Entity; inheriting Entity here as well would pit
    Entity's attributes against the platform's overrides.
    """

    _attr_has_entity_name: bool
    _attr_device_info: DeviceInfo | None
    _entry: CableModemConfigEntry

    def __init__(self, entry: CableModemConfigEntry) -> None:
        """Attach to the modem device; must match _update_device_registry's name."""
        # Sensor bases call this after super().__init__(coordinator):
        # CoordinatorEntity.__init__ does not chain to its parents.
        self._entry = entry
        # Instance attribute: Entity's class default, earlier in the MRO,
        # would shadow a class attribute here.
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=get_device_name(
                entry.data.get(CONF_ENTITY_PREFIX, "default"),
                model=entry.runtime_data.modem_identity.model,
                host=entry.data.get("host", ""),
            ),
        )
