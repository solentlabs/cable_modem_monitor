"""Sensor platform for Cable Modem Monitor."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cable Modem Monitor sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    ***REMOVED*** Add connection status sensor
    entities.append(ModemConnectionStatusSensor(coordinator, entry))

    ***REMOVED*** Add total error sensors
    entities.append(ModemTotalCorrectedSensor(coordinator, entry))
    entities.append(ModemTotalUncorrectedSensor(coordinator, entry))

    ***REMOVED*** Add per-channel downstream sensors
    if coordinator.data.get("downstream"):
        for idx, channel in enumerate(coordinator.data["downstream"]):
            channel_num = channel.get("channel", idx + 1)
            entities.extend(
                [
                    ModemDownstreamPowerSensor(coordinator, entry, channel_num),
                    ModemDownstreamSNRSensor(coordinator, entry, channel_num),
                    ModemDownstreamFrequencySensor(coordinator, entry, channel_num),
                ]
            )
            ***REMOVED*** Only add error sensors if the data includes them
            if "corrected" in channel:
                entities.append(
                    ModemDownstreamCorrectedSensor(coordinator, entry, channel_num)
                )
            if "uncorrected" in channel:
                entities.append(
                    ModemDownstreamUncorrectedSensor(coordinator, entry, channel_num)
                )

    ***REMOVED*** Add per-channel upstream sensors
    if coordinator.data.get("upstream"):
        for idx, channel in enumerate(coordinator.data["upstream"]):
            channel_num = channel.get("channel", idx + 1)
            entities.extend(
                [
                    ModemUpstreamPowerSensor(coordinator, entry, channel_num),
                    ModemUpstreamFrequencySensor(coordinator, entry, channel_num),
                ]
            )

    async_add_entities(entities)


class ModemSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for modem sensors."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Cable Modem {entry.data['host']}",
            "manufacturer": "Cable Modem",
            "model": "Monitor",
        }


class ModemConnectionStatusSensor(ModemSensorBase):
    """Sensor for modem connection status."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Modem Connection Status"
        self._attr_unique_id = f"{entry.entry_id}_connection_status"
        self._attr_icon = "mdi:router-network"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.coordinator.data.get("connection_status", "unknown")


class ModemTotalCorrectedSensor(ModemSensorBase):
    """Sensor for total corrected errors."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Total Corrected Errors"
        self._attr_unique_id = f"{entry.entry_id}_total_corrected"
        self._attr_icon = "mdi:alert-circle-check"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.get("total_corrected", 0)


class ModemTotalUncorrectedSensor(ModemSensorBase):
    """Sensor for total uncorrected errors."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Total Uncorrected Errors"
        self._attr_unique_id = f"{entry.entry_id}_total_uncorrected"
        self._attr_icon = "mdi:alert-circle"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.get("total_uncorrected", 0)


class ModemDownstreamPowerSensor(ModemSensorBase):
    """Sensor for downstream channel power."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, channel: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._channel = channel
        self._attr_name = f"Downstream Ch {channel} Power"
        self._attr_unique_id = f"{entry.entry_id}_downstream_{channel}_power"
        self._attr_native_unit_of_measurement = "dBmV"
        self._attr_icon = "mdi:signal"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("downstream", []):
            if ch.get("channel") == self._channel:
                return ch.get("power")
        return None


class ModemDownstreamSNRSensor(ModemSensorBase):
    """Sensor for downstream channel SNR."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, channel: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._channel = channel
        self._attr_name = f"Downstream Ch {channel} SNR"
        self._attr_unique_id = f"{entry.entry_id}_downstream_{channel}_snr"
        self._attr_native_unit_of_measurement = "dB"
        self._attr_icon = "mdi:signal-variant"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("downstream", []):
            if ch.get("channel") == self._channel:
                return ch.get("snr")
        return None


class ModemDownstreamFrequencySensor(ModemSensorBase):
    """Sensor for downstream channel frequency."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, channel: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._channel = channel
        self._attr_name = f"Downstream Ch {channel} Frequency"
        self._attr_unique_id = f"{entry.entry_id}_downstream_{channel}_frequency"
        self._attr_native_unit_of_measurement = "Hz"
        self._attr_icon = "mdi:sine-wave"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.FREQUENCY

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("downstream", []):
            if ch.get("channel") == self._channel:
                return ch.get("frequency")
        return None


class ModemDownstreamCorrectedSensor(ModemSensorBase):
    """Sensor for downstream channel corrected errors."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, channel: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._channel = channel
        self._attr_name = f"Downstream Ch {channel} Corrected"
        self._attr_unique_id = f"{entry.entry_id}_downstream_{channel}_corrected"
        self._attr_icon = "mdi:check-circle"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("downstream", []):
            if ch.get("channel") == self._channel:
                return ch.get("corrected")
        return None


class ModemDownstreamUncorrectedSensor(ModemSensorBase):
    """Sensor for downstream channel uncorrected errors."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, channel: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._channel = channel
        self._attr_name = f"Downstream Ch {channel} Uncorrected"
        self._attr_unique_id = f"{entry.entry_id}_downstream_{channel}_uncorrected"
        self._attr_icon = "mdi:alert-circle"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("downstream", []):
            if ch.get("channel") == self._channel:
                return ch.get("uncorrected")
        return None


class ModemUpstreamPowerSensor(ModemSensorBase):
    """Sensor for upstream channel power."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, channel: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._channel = channel
        self._attr_name = f"Upstream Ch {channel} Power"
        self._attr_unique_id = f"{entry.entry_id}_upstream_{channel}_power"
        self._attr_native_unit_of_measurement = "dBmV"
        self._attr_icon = "mdi:signal"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("upstream", []):
            if ch.get("channel") == self._channel:
                return ch.get("power")
        return None


class ModemUpstreamFrequencySensor(ModemSensorBase):
    """Sensor for upstream channel frequency."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, channel: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._channel = channel
        self._attr_name = f"Upstream Ch {channel} Frequency"
        self._attr_unique_id = f"{entry.entry_id}_upstream_{channel}_frequency"
        self._attr_native_unit_of_measurement = "Hz"
        self._attr_icon = "mdi:sine-wave"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.FREQUENCY

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("upstream", []):
            if ch.get("channel") == self._channel:
                return ch.get("frequency")
        return None
