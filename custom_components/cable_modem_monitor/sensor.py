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
from .lib.utils import parse_uptime_to_seconds

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cable Modem Monitor sensors."""
    _LOGGER.info("async_setup_entry called for %s", entry.entry_id)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug("Coordinator data has %s upstream channels", len(coordinator.data.get('cable_modem_upstream', [])))

    entities = []

    # Add connection status sensor
    entities.append(ModemConnectionStatusSensor(coordinator, entry))

    # Add health monitoring sensors
    entities.extend([
        ModemHealthStatusSensor(coordinator, entry),
        ModemPingLatencySensor(coordinator, entry),
        ModemHttpLatencySensor(coordinator, entry),
    ])

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
    if coordinator.data.get("cable_modem_downstream"):
        for idx, channel in enumerate(coordinator.data["cable_modem_downstream"]):
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
    if coordinator.data.get("cable_modem_upstream"):
        _LOGGER.debug("Creating entities for %s upstream channels", len(coordinator.data['cable_modem_upstream']))
        for idx, channel in enumerate(coordinator.data["cable_modem_upstream"]):
            # v2.0+ parsers return 'channel_id', older versions used 'channel'
            # Fallback to index+1 if neither exists (shouldn't happen in practice)
            channel_num = int(channel.get("channel_id", channel.get("channel", idx + 1)))
            power_sensor = ModemUpstreamPowerSensor(coordinator, entry, channel_num)
            freq_sensor = ModemUpstreamFrequencySensor(coordinator, entry, channel_num)
            entities.extend([power_sensor, freq_sensor])

    # Add LAN stats sensors
    if coordinator.data.get("cable_modem_lan_stats"):
        for interface, stats in coordinator.data["cable_modem_lan_stats"].items():
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

    _LOGGER.info("Created %s total sensor entities", len(entities))
    async_add_entities(entities)


class ModemSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for modem sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry

        # Get detected modem info from config entry, with fallback to generic values
        manufacturer = entry.data.get("detected_manufacturer", "Unknown")
        model = entry.data.get("detected_modem", "Cable Modem Monitor")

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Cable Modem",
            "manufacturer": manufacturer,
            "model": model,
            "configuration_url": f"http://{entry.data[CONF_HOST]}",
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Sensors remain available if coordinator succeeds, even if modem is temporarily offline
        # This allows sensors to retain last known values during modem reboots
        # Only mark unavailable if we truly can't reach the modem
        status = self.coordinator.data.get("cable_modem_connection_status", "unknown")
        return (
            self.coordinator.last_update_success
            and status in ("online", "offline")  # Available for both online and offline (just rebooting)
        )


class ModemConnectionStatusSensor(ModemSensorBase):
    """Sensor for modem connection status."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Connection Status"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_connection_status"
        self._attr_icon = "mdi:router-network"

    @property
    def available(self) -> bool:
        """Connection status sensor is always available to show offline state."""
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.coordinator.data.get("cable_modem_connection_status", "unknown")


class ModemTotalCorrectedSensor(ModemSensorBase):
    """Sensor for total corrected errors."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Total Corrected Errors"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_total_corrected"
        self._attr_icon = "mdi:alert-circle-check"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.get("cable_modem_total_corrected", 0)


class ModemTotalUncorrectedSensor(ModemSensorBase):
    """Sensor for total uncorrected errors."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Total Uncorrected Errors"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_total_uncorrected"
        self._attr_icon = "mdi:alert-circle"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.get("cable_modem_total_uncorrected", 0)


class ModemDownstreamPowerSensor(ModemSensorBase):
    """Sensor for downstream channel power."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, channel: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._channel = channel
        self._attr_name = f"DS Ch {channel} Power"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_downstream_{channel}_power"
        self._attr_native_unit_of_measurement = "dBmV"
        self._attr_icon = "mdi:signal"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("cable_modem_downstream", []):
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
        self._attr_name = f"DS Ch {channel} SNR"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_downstream_{channel}_snr"
        self._attr_native_unit_of_measurement = "dB"
        self._attr_icon = "mdi:signal-variant"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("cable_modem_downstream", []):
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
        self._attr_name = f"DS Ch {channel} Frequency"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_downstream_{channel}_frequency"
        self._attr_native_unit_of_measurement = "Hz"
        self._attr_icon = "mdi:sine-wave"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.FREQUENCY

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("cable_modem_downstream", []):
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
        self._attr_name = f"DS Ch {channel} Corrected"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_downstream_{channel}_corrected"
        self._attr_icon = "mdi:check-circle"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("cable_modem_downstream", []):
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
        self._attr_name = f"DS Ch {channel} Uncorrected"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_downstream_{channel}_uncorrected"
        self._attr_icon = "mdi:alert-circle"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("cable_modem_downstream", []):
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
        self._attr_name = f"US Ch {channel} Power"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_upstream_{channel}_power"
        self._attr_native_unit_of_measurement = "dBmV"
        self._attr_icon = "mdi:signal"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("cable_modem_upstream", []):
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
        self._attr_name = f"US Ch {channel} Frequency"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_upstream_{channel}_frequency"
        self._attr_native_unit_of_measurement = "Hz"
        self._attr_icon = "mdi:sine-wave"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.FREQUENCY

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        for ch in self.coordinator.data.get("cable_modem_upstream", []):
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
        self._attr_name = "DS Channel Count"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_downstream_channel_count"
        self._attr_icon = "mdi:numeric"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.get("cable_modem_downstream_channel_count", 0)


class ModemUpstreamChannelCountSensor(ModemSensorBase):
    """Sensor for upstream channel count."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "US Channel Count"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_upstream_channel_count"
        self._attr_icon = "mdi:numeric"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.get("cable_modem_upstream_channel_count", 0)


class ModemSoftwareVersionSensor(ModemSensorBase):
    """Sensor for modem software version."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Software Version"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_software_version"
        self._attr_icon = "mdi:information-outline"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.coordinator.data.get("cable_modem_software_version", "Unknown")


class ModemSystemUptimeSensor(ModemSensorBase):
    """Sensor for modem system uptime."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "System Uptime"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_system_uptime"
        self._attr_icon = "mdi:clock-outline"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.coordinator.data.get("cable_modem_system_uptime", "Unknown")


class ModemLastBootTimeSensor(ModemSensorBase):
    """Sensor for modem last boot time (calculated from uptime)."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Last Boot Time"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_last_boot_time"
        self._attr_icon = "mdi:restart"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the last boot time as a datetime object."""
        uptime_str = self.coordinator.data.get("cable_modem_system_uptime")
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
        lan_stats = self.coordinator.data.get("cable_modem_lan_stats", {})
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


class ModemHealthStatusSensor(ModemSensorBase):
    """Sensor for modem health status (healthy/degraded/icmp_blocked/unresponsive)."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Health Status"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_health_status"
        self._attr_icon = "mdi:heart-pulse"

    @property
    def native_value(self) -> str:
        """Return the health status."""
        return self.coordinator.data.get("health_status", "unknown")

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes."""
        return {
            "diagnosis": self.coordinator.data.get("health_diagnosis", ""),
            "ping_success": self.coordinator.data.get("ping_success", False),
            "http_success": self.coordinator.data.get("http_success", False),
            "consecutive_failures": self.coordinator.data.get("consecutive_failures", 0),
        }


class ModemPingLatencySensor(ModemSensorBase):
    """Sensor for ICMP ping latency in milliseconds."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Ping Latency"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_ping_latency"
        self._attr_native_unit_of_measurement = "ms"
        self._attr_icon = "mdi:speedometer"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.DURATION

    @property
    def native_value(self) -> float | None:
        """Return the ping latency in milliseconds."""
        return self.coordinator.data.get("ping_latency_ms")


class ModemHttpLatencySensor(ModemSensorBase):
    """Sensor for HTTP HEAD request latency in milliseconds."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "HTTP Latency"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_http_latency"
        self._attr_native_unit_of_measurement = "ms"
        self._attr_icon = "mdi:web-clock"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.DURATION

    @property
    def native_value(self) -> float | None:
        """Return the HTTP latency in milliseconds."""
        return self.coordinator.data.get("http_latency_ms")
