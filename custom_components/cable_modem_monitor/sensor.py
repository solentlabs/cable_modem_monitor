"""Sensor platform for Cable Modem Monitor."""
from __future__ import annotations

from datetime import datetime, timedelta
import re

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
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CUSTOM_PREFIX,
    CONF_ENTITY_PREFIX,
    CONF_HOST,
    DOMAIN,
    ENTITY_PREFIX_CUSTOM,
    ENTITY_PREFIX_DEFAULT,
    ENTITY_PREFIX_DOMAIN,
    ENTITY_PREFIX_IP,
)


def get_unique_id_prefix(entry: ConfigEntry) -> str:
    """Get the prefix for unique IDs based on entity naming configuration.

    Args:
        entry: Config entry containing entity naming preferences

    Returns:
        Prefix string for unique IDs (e.g., "cable_modem_" or "")
    """
    prefix_type = entry.data.get(CONF_ENTITY_PREFIX, ENTITY_PREFIX_DEFAULT)

    if prefix_type == ENTITY_PREFIX_DOMAIN:
        return "cable_modem_"
    elif prefix_type == ENTITY_PREFIX_IP:
        host = entry.data.get(CONF_HOST, "")
        sanitized_host = host.replace(".", "_").replace(":", "_")
        return f"{sanitized_host}_"
    elif prefix_type == ENTITY_PREFIX_CUSTOM:
        custom_prefix = entry.data.get(CONF_CUSTOM_PREFIX, "")
        if custom_prefix:
            ***REMOVED*** Sanitize custom prefix for entity IDs
            sanitized = custom_prefix.strip().lower().replace(" ", "_").replace("-", "_")
            return f"{sanitized}_"

    ***REMOVED*** Default or fallback: no prefix
    return ""


def get_entity_name(entry: ConfigEntry, base_name: str) -> str:
    """Generate entity name with configured prefix.

    Args:
        entry: Config entry containing entity naming preferences
        base_name: Base name for the entity (e.g., "Connection Status")

    Returns:
        Full entity name with appropriate prefix
    """
    prefix_type = entry.data.get(CONF_ENTITY_PREFIX, ENTITY_PREFIX_DEFAULT)

    if prefix_type == ENTITY_PREFIX_DEFAULT:
        ***REMOVED*** No prefix - current behavior
        return base_name
    elif prefix_type == ENTITY_PREFIX_DOMAIN:
        ***REMOVED*** Domain mode: Display name has NO prefix (device name provides context)
        ***REMOVED*** Entity ID will have cable_modem_ prefix (handled via unique_id)
        return base_name
    elif prefix_type == ENTITY_PREFIX_IP:
        ***REMOVED*** Add IP address prefix (sanitized for entity names)
        host = entry.data.get(CONF_HOST, "")
        sanitized_host = host.replace(".", "_").replace(":", "_")
        return f"{sanitized_host} {base_name}"
    elif prefix_type == ENTITY_PREFIX_CUSTOM:
        ***REMOVED*** Add custom prefix
        custom_prefix = entry.data.get(CONF_CUSTOM_PREFIX, "")
        if custom_prefix:
            ***REMOVED*** Ensure custom prefix ends with space if it doesn't already
            if not custom_prefix.endswith(" "):
                custom_prefix += " "
            return f"{custom_prefix}{base_name}"
        return base_name
    else:
        ***REMOVED*** Fallback to no prefix
        return base_name


def parse_uptime_to_seconds(uptime_str: str) -> int | None:
    """Parse uptime string to total seconds.

    Args:
        uptime_str: Uptime string like "2 days 5 hours" or "3 hours 45 minutes"

    Returns:
        Total seconds or None if parsing fails
    """
    if not uptime_str or uptime_str == "Unknown":
        return None

    try:
        total_seconds = 0

        ***REMOVED*** Parse days
        days_match = re.search(r'(\d+)\s*day', uptime_str, re.IGNORECASE)
        if days_match:
            total_seconds += int(days_match.group(1)) * 86400

        ***REMOVED*** Parse hours
        hours_match = re.search(r'(\d+)\s*hour', uptime_str, re.IGNORECASE)
        if hours_match:
            total_seconds += int(hours_match.group(1)) * 3600

        ***REMOVED*** Parse minutes
        minutes_match = re.search(r'(\d+)\s*min', uptime_str, re.IGNORECASE)
        if minutes_match:
            total_seconds += int(minutes_match.group(1)) * 60

        ***REMOVED*** Parse seconds
        seconds_match = re.search(r'(\d+)\s*sec', uptime_str, re.IGNORECASE)
        if seconds_match:
            total_seconds += int(seconds_match.group(1))

        return total_seconds if total_seconds > 0 else None
    except Exception:
        return None


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

    ***REMOVED*** Add channel count sensors
    entities.append(ModemDownstreamChannelCountSensor(coordinator, entry))
    entities.append(ModemUpstreamChannelCountSensor(coordinator, entry))

    ***REMOVED*** Add software version and uptime sensors
    entities.append(ModemSoftwareVersionSensor(coordinator, entry))
    entities.append(ModemSystemUptimeSensor(coordinator, entry))
    entities.append(ModemLastBootTimeSensor(coordinator, entry))

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

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        ***REMOVED*** Make sensors unavailable when modem is offline so charts skip the data point
        ***REMOVED*** instead of showing 0/None values
        return (
            self.coordinator.last_update_success
            and self.coordinator.data.get("connection_status") == "online"
        )


class ModemConnectionStatusSensor(ModemSensorBase):
    """Sensor for modem connection status."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        prefix = get_unique_id_prefix(entry)
        self._attr_name = get_entity_name(entry, "Modem Connection Status")
        self._attr_unique_id = f"{entry.entry_id}_{prefix}connection_status"
        self._attr_icon = "mdi:router-network"

    @property
    def available(self) -> bool:
        """Connection status sensor is always available to show offline state."""
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.coordinator.data.get("connection_status", "unknown")


class ModemTotalCorrectedSensor(ModemSensorBase):
    """Sensor for total corrected errors."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        prefix = get_unique_id_prefix(entry)
        self._attr_name = get_entity_name(entry, "Total Corrected Errors")
        self._attr_unique_id = f"{entry.entry_id}_{prefix}total_corrected"
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
        prefix = get_unique_id_prefix(entry)
        self._attr_name = get_entity_name(entry, "Total Uncorrected Errors")
        self._attr_unique_id = f"{entry.entry_id}_{prefix}total_uncorrected"
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
        prefix = get_unique_id_prefix(entry)
        self._channel = channel
        self._attr_name = get_entity_name(entry, f"Downstream Ch {channel} Power")
        self._attr_unique_id = f"{entry.entry_id}_{prefix}downstream_{channel}_power"
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
        prefix = get_unique_id_prefix(entry)
        self._channel = channel
        self._attr_name = get_entity_name(entry, f"Downstream Ch {channel} SNR")
        self._attr_unique_id = f"{entry.entry_id}_{prefix}downstream_{channel}_snr"
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
        prefix = get_unique_id_prefix(entry)
        self._channel = channel
        self._attr_name = get_entity_name(entry, f"Downstream Ch {channel} Frequency")
        self._attr_unique_id = f"{entry.entry_id}_{prefix}downstream_{channel}_frequency"
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
        prefix = get_unique_id_prefix(entry)
        self._channel = channel
        self._attr_name = get_entity_name(entry, f"Downstream Ch {channel} Corrected")
        self._attr_unique_id = f"{entry.entry_id}_{prefix}downstream_{channel}_corrected"
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
        prefix = get_unique_id_prefix(entry)
        self._channel = channel
        self._attr_name = get_entity_name(entry, f"Downstream Ch {channel} Uncorrected")
        self._attr_unique_id = f"{entry.entry_id}_{prefix}downstream_{channel}_uncorrected"
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
        prefix = get_unique_id_prefix(entry)
        self._channel = channel
        self._attr_name = get_entity_name(entry, f"Upstream Ch {channel} Power")
        self._attr_unique_id = f"{entry.entry_id}_{prefix}upstream_{channel}_power"
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
        prefix = get_unique_id_prefix(entry)
        self._channel = channel
        self._attr_name = get_entity_name(entry, f"Upstream Ch {channel} Frequency")
        self._attr_unique_id = f"{entry.entry_id}_{prefix}upstream_{channel}_frequency"
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


class ModemDownstreamChannelCountSensor(ModemSensorBase):
    """Sensor for downstream channel count."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        prefix = get_unique_id_prefix(entry)
        self._attr_name = get_entity_name(entry, "Downstream Channel Count")
        self._attr_unique_id = f"{entry.entry_id}_{prefix}downstream_channel_count"
        self._attr_icon = "mdi:numeric"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.get("downstream_channel_count", 0)


class ModemUpstreamChannelCountSensor(ModemSensorBase):
    """Sensor for upstream channel count."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        prefix = get_unique_id_prefix(entry)
        self._attr_name = get_entity_name(entry, "Upstream Channel Count")
        self._attr_unique_id = f"{entry.entry_id}_{prefix}upstream_channel_count"
        self._attr_icon = "mdi:numeric"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.get("upstream_channel_count", 0)


class ModemSoftwareVersionSensor(ModemSensorBase):
    """Sensor for modem software version."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        prefix = get_unique_id_prefix(entry)
        self._attr_name = get_entity_name(entry, "Software Version")
        self._attr_unique_id = f"{entry.entry_id}_{prefix}software_version"
        self._attr_icon = "mdi:information-outline"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.coordinator.data.get("software_version", "Unknown")


class ModemSystemUptimeSensor(ModemSensorBase):
    """Sensor for modem system uptime."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        prefix = get_unique_id_prefix(entry)
        self._attr_name = get_entity_name(entry, "System Uptime")
        self._attr_unique_id = f"{entry.entry_id}_{prefix}system_uptime"
        self._attr_icon = "mdi:clock-outline"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.coordinator.data.get("system_uptime", "Unknown")


class ModemLastBootTimeSensor(ModemSensorBase):
    """Sensor for modem last boot time (calculated from uptime)."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        prefix = get_unique_id_prefix(entry)
        self._attr_name = get_entity_name(entry, "Last Boot Time")
        self._attr_unique_id = f"{entry.entry_id}_{prefix}last_boot_time"
        self._attr_icon = "mdi:restart"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the last boot time as a datetime object."""
        uptime_str = self.coordinator.data.get("system_uptime")
        if not uptime_str or uptime_str == "Unknown":
            return None

        ***REMOVED*** Parse uptime string to seconds
        uptime_seconds = parse_uptime_to_seconds(uptime_str)
        if uptime_seconds is None:
            return None

        ***REMOVED*** Calculate last boot time: current time - uptime
        now = dt_util.now()
        last_boot = now - timedelta(seconds=uptime_seconds)
        return last_boot
