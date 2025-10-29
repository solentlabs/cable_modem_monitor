"""Sensor platform for Cable Modem Monitor."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
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
    CONF_HOST,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


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

        # Parse days
        days_match = re.search(r'(\d+)\s*day', uptime_str, re.IGNORECASE)
        if days_match:
            total_seconds += int(days_match.group(1)) * 86400

        # Parse hours
        hours_match = re.search(r'(\d+)\s*hour', uptime_str, re.IGNORECASE)
        if hours_match:
            total_seconds += int(hours_match.group(1)) * 3600

        # Parse minutes
        minutes_match = re.search(r'(\d+)\s*min', uptime_str, re.IGNORECASE)
        if minutes_match:
            total_seconds += int(minutes_match.group(1)) * 60

        # Parse seconds
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
    _LOGGER.info(f"async_setup_entry called for {entry.entry_id}")
    coordinator = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug(f"Coordinator data has {len(coordinator.data.get('upstream', []))} upstream channels")

    entities = []

    # Add connection status sensor
    entities.append(ModemConnectionStatusSensor(coordinator, entry))

    # Add total error sensors
    entities.append(ModemTotalCorrectedSensor(coordinator, entry))
    entities.append(ModemTotalUncorrectedSensor(coordinator, entry))

    # Add channel count sensors
    entities.append(ModemDownstreamChannelCountSensor(coordinator, entry))
    entities.append(ModemUpstreamChannelCountSensor(coordinator, entry))

    # Add software version and uptime sensors
    entities.append(ModemSoftwareVersionSensor(coordinator, entry))
    entities.append(ModemSystemUptimeSensor(coordinator, entry))
    entities.append(ModemLastBootTimeSensor(coordinator, entry))

    # Add per-channel downstream sensors
    if coordinator.data.get("downstream"):
        for idx, channel in enumerate(coordinator.data["downstream"]):
            # v2.0+ parsers return 'channel_id', older versions used 'channel'
            # Fallback to index+1 if neither exists (shouldn't happen in practice)
            channel_num = int(channel.get("channel_id", channel.get("channel", idx + 1)))
            entities.extend(
                [
                    ModemDownstreamPowerSensor(coordinator, entry, channel_num),
                    ModemDownstreamSNRSensor(coordinator, entry, channel_num),
                    ModemDownstreamFrequencySensor(coordinator, entry, channel_num),
                ]
            )
            # Only add error sensors if the data includes them
            if "corrected" in channel:
                entities.append(
                    ModemDownstreamCorrectedSensor(coordinator, entry, channel_num)
                )
            if "uncorrected" in channel:
                entities.append(
                    ModemDownstreamUncorrectedSensor(coordinator, entry, channel_num)
                )

    # Add per-channel upstream sensors
    if coordinator.data.get("upstream"):
        _LOGGER.debug(f"Creating entities for {len(coordinator.data['upstream'])} upstream channels")
        for idx, channel in enumerate(coordinator.data["upstream"]):
            # v2.0+ parsers return 'channel_id', older versions used 'channel'
            # Fallback to index+1 if neither exists (shouldn't happen in practice)
            channel_num = int(channel.get("channel_id", channel.get("channel", idx + 1)))
            _LOGGER.debug(f"Creating upstream entities for channel {channel_num}: {channel}")
            power_sensor = ModemUpstreamPowerSensor(coordinator, entry, channel_num)
            freq_sensor = ModemUpstreamFrequencySensor(coordinator, entry, channel_num)
            _LOGGER.debug(f"  Power sensor unique_id: {power_sensor.unique_id}")
            _LOGGER.debug(f"  Freq sensor unique_id: {freq_sensor.unique_id}")
            entities.extend([power_sensor, freq_sensor])

    # Add LAN stats sensors
    if coordinator.data.get("lan_stats"):
        for interface, stats in coordinator.data["lan_stats"].items():
            entities.extend(
                [
                    ModemLanReceivedBytesSensor(coordinator, entry, interface),
                    ModemLanReceivedPacketsSensor(coordinator, entry, interface),
                    ModemLanReceivedErrorsSensor(coordinator, entry, interface),
                    ModemLanReceivedDropsSensor(coordinator, entry, interface),
                    ModemLanTransmittedBytesSensor(coordinator, entry, interface),
                    ModemLanTransmittedPacketsSensor(coordinator, entry, interface),
                    ModemLanTransmittedErrorsSensor(coordinator, entry, interface),
                    ModemLanTransmittedDropsSensor(coordinator, entry, interface),
                ]
            )

    _LOGGER.info(f"Created {len(entities)} total sensor entities")
    upstream_entities = [e for e in entities if 'upstream' in e.unique_id and 'US Ch' in e.name]
    _LOGGER.info(f"About to add {len(upstream_entities)} upstream channel entities:")
    for e in upstream_entities:
        _LOGGER.debug(f"  - {e.name} (unique_id: {e.unique_id})")
    async_add_entities(entities)


class ModemSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for modem sensors."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry

        # Get detected modem info from config entry, with fallback to generic values
        manufacturer = entry.data.get("detected_manufacturer", "Unknown")
        model = entry.data.get("detected_modem", "Cable Modem Monitor")

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Cable Modem {entry.data['host']}",
            "manufacturer": manufacturer,
            "model": model,
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Make sensors unavailable when modem is offline so charts skip the data point
        # instead of showing 0/None values
        return (
            self.coordinator.last_update_success
            and self.coordinator.data.get("connection_status") == "online"
        )


class ModemConnectionStatusSensor(ModemSensorBase):
    """Sensor for modem connection status."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Cable Modem Connection Status"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_connection_status"
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
        self._attr_name = "Cable Modem Total Corrected Errors"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_total_corrected"
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
        self._attr_name = "Cable Modem Total Uncorrected Errors"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_total_uncorrected"
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
        self._attr_name = f"Cable Modem DS Ch {channel} Power"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_downstream_{channel}_power"
        self._attr_native_unit_of_measurement = "dBmV"
        self._attr_icon = "mdi:signal"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("downstream", []):
            # v2.0+ parsers return 'channel_id', older versions used 'channel'
            # Fallback to 0 if neither exists (will not match, returns None)
            ch_num = int(ch.get("channel_id", ch.get("channel", 0)))
            if ch_num == self._channel:
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
        self._attr_name = f"Cable Modem DS Ch {channel} SNR"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_downstream_{channel}_snr"
        self._attr_native_unit_of_measurement = "dB"
        self._attr_icon = "mdi:signal-variant"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("downstream", []):
            # v2.0+ parsers return 'channel_id', older versions used 'channel'
            # Fallback to 0 if neither exists (will not match, returns None)
            ch_num = int(ch.get("channel_id", ch.get("channel", 0)))
            if ch_num == self._channel:
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
        self._attr_name = f"Cable Modem DS Ch {channel} Frequency"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_downstream_{channel}_frequency"
        self._attr_native_unit_of_measurement = "Hz"
        self._attr_icon = "mdi:sine-wave"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.FREQUENCY

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("downstream", []):
            # v2.0+ parsers return 'channel_id', older versions used 'channel'
            # Fallback to 0 if neither exists (will not match, returns None)
            ch_num = int(ch.get("channel_id", ch.get("channel", 0)))
            if ch_num == self._channel:
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
        self._attr_name = f"Cable Modem DS Ch {channel} Corrected"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_downstream_{channel}_corrected"
        self._attr_icon = "mdi:check-circle"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("downstream", []):
            # v2.0+ parsers return 'channel_id', older versions used 'channel'
            # Fallback to 0 if neither exists (will not match, returns None)
            ch_num = int(ch.get("channel_id", ch.get("channel", 0)))
            if ch_num == self._channel:
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
        self._attr_name = f"Cable Modem DS Ch {channel} Uncorrected"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_downstream_{channel}_uncorrected"
        self._attr_icon = "mdi:alert-circle"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("downstream", []):
            # v2.0+ parsers return 'channel_id', older versions used 'channel'
            # Fallback to 0 if neither exists (will not match, returns None)
            ch_num = int(ch.get("channel_id", ch.get("channel", 0)))
            if ch_num == self._channel:
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
        self._attr_name = f"Cable Modem US Ch {channel} Power"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_upstream_{channel}_power"
        self._attr_native_unit_of_measurement = "dBmV"
        self._attr_icon = "mdi:signal"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("upstream", []):
            # v2.0+ parsers return 'channel_id', older versions used 'channel'
            # Fallback to 0 if neither exists (will not match, returns None)
            ch_num = int(ch.get("channel_id", ch.get("channel", 0)))
            if ch_num == self._channel:
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
        self._attr_name = f"Cable Modem US Ch {channel} Frequency"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_upstream_{channel}_frequency"
        self._attr_native_unit_of_measurement = "Hz"
        self._attr_icon = "mdi:sine-wave"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.FREQUENCY

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("upstream", []):
            # v2.0+ parsers return 'channel_id', older versions used 'channel'
            # Fallback to 0 if neither exists (will not match, returns None)
            ch_num = int(ch.get("channel_id", ch.get("channel", 0)))
            if ch_num == self._channel:
                return ch.get("frequency")
        return None


class ModemDownstreamChannelCountSensor(ModemSensorBase):
    """Sensor for downstream channel count."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Cable Modem Downstream Channel Count"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_downstream_channel_count"
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
        self._attr_name = "Cable Modem Upstream Channel Count"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_upstream_channel_count"
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
        self._attr_name = "Cable Modem Software Version"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_software_version"
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
        self._attr_name = "Cable Modem System Uptime"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_system_uptime"
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
        self._attr_name = "Cable Modem Last Boot Time"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_last_boot_time"
        self._attr_icon = "mdi:restart"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the last boot time as a datetime object."""
        uptime_str = self.coordinator.data.get("system_uptime")
        if not uptime_str or uptime_str == "Unknown":
            return None

        # Parse uptime string to seconds
        uptime_seconds = parse_uptime_to_seconds(uptime_str)
        if uptime_seconds is None:
            return None

        # Calculate last boot time: current time - uptime
        now = dt_util.now()
        last_boot = now - timedelta(seconds=uptime_seconds)
        return last_boot


class ModemLanStatsSensor(ModemSensorBase):
    """Base class for LAN statistics sensors."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, interface: str, sensor_type: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._interface = interface
        self._sensor_type = sensor_type
        self._attr_name = f"LAN {interface} {sensor_type.replace('_', ' ').title()}"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_lan_{interface}_{sensor_type}"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        lan_stats = self.coordinator.data.get("lan_stats", {})
        if self._interface in lan_stats:
            return lan_stats[self._interface].get(self._sensor_type)
        return None


class ModemLanReceivedBytesSensor(ModemLanStatsSensor):
    """Sensor for LAN received bytes."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, interface: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, interface, "received_bytes")
        self._attr_device_class = SensorDeviceClass.DATA_SIZE
        self._attr_native_unit_of_measurement = "B"


class ModemLanReceivedPacketsSensor(ModemLanStatsSensor):
    """Sensor for LAN received packets."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, interface: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, interface, "received_packets")


class ModemLanReceivedErrorsSensor(ModemLanStatsSensor):
    """Sensor for LAN received errors."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, interface: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, interface, "received_errors")


class ModemLanReceivedDropsSensor(ModemLanStatsSensor):
    """Sensor for LAN received drops."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, interface: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, interface, "received_drops")


class ModemLanTransmittedBytesSensor(ModemLanStatsSensor):
    """Sensor for LAN transmitted bytes."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, interface: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, interface, "transmitted_bytes")
        self._attr_device_class = SensorDeviceClass.DATA_SIZE
        self._attr_native_unit_of_measurement = "B"


class ModemLanTransmittedPacketsSensor(ModemLanStatsSensor):
    """Sensor for LAN transmitted packets."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, interface: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, interface, "transmitted_packets")


class ModemLanTransmittedErrorsSensor(ModemLanStatsSensor):
    """Sensor for LAN transmitted errors."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, interface: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, interface, "transmitted_errors")


class ModemLanTransmittedDropsSensor(ModemLanStatsSensor):
    """Sensor for LAN transmitted drops."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, interface: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, interface, "transmitted_drops")
