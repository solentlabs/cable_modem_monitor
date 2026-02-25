"""Sensor platform for Cable Modem Monitor.

This module creates Home Assistant sensor entities from modem data provided by
the DataUpdateCoordinator. It does NOT handle authentication or data fetching -
those responsibilities belong to __init__.py and DataOrchestrator.

Entity Types:
    - Status/Info: ModemStatusSensor, ModemInfoSensor
    - Latency: ModemPingLatencySensor, ModemHttpLatencySensor
    - System: channel counts, software version, uptime, last boot time
    - Per-channel: power, SNR, frequency, corrected/uncorrected errors
    - LAN stats: bytes, packets, errors, drops per interface

Architecture:
    - All sensors inherit from ModemSensorBase (device info, availability)
    - Per-channel sensors use O(1) indexed lookups (_downstream_by_id, _upstream_by_id)
    - Capability-gated sensors only created if parser reports the capability
    - Fallback mode: only connectivity sensors when modem is unsupported
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

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
    CONF_ACTUAL_MODEL,
    CONF_DETECTED_MODEM,
    CONF_ENTITY_PREFIX,
    CONF_HOST,
    DOMAIN,
    ENTITY_PREFIX_IP,
    ENTITY_PREFIX_MODEL,
    ENTITY_PREFIX_NONE,
)
from .core.base_parser import ModemCapability
from .lib.utils import parse_uptime_to_seconds

_LOGGER = logging.getLogger(__name__)


def _has_capability(coordinator: DataUpdateCoordinator, capability: ModemCapability) -> bool:
    """Check if the parser has a specific capability."""
    capabilities = coordinator.data.get("_parser_capabilities", [])
    return capability.value in capabilities


def _create_system_sensors(coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> list[SensorEntity]:
    """Create system-level sensors (error totals, channel counts, version, uptime)."""
    entities: list[SensorEntity] = []

    # Error totals
    entities.append(ModemTotalCorrectedSensor(coordinator, entry))
    entities.append(ModemTotalUncorrectedSensor(coordinator, entry))

    # Channel counts
    entities.append(ModemDownstreamChannelCountSensor(coordinator, entry))
    entities.append(ModemUpstreamChannelCountSensor(coordinator, entry))

    # Software version (only if parser has capability)
    if _has_capability(coordinator, ModemCapability.SOFTWARE_VERSION):
        entities.append(ModemSoftwareVersionSensor(coordinator, entry))

    # Uptime sensors (only if parser has capability)
    if _has_capability(coordinator, ModemCapability.SYSTEM_UPTIME):
        entities.append(ModemSystemUptimeSensor(coordinator, entry))
        entities.append(ModemLastBootTimeSensor(coordinator, entry))

    return entities


def _create_downstream_sensors(coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> list[SensorEntity]:
    """Create per-channel downstream sensors."""
    entities: list[SensorEntity] = []
    downstream_by_id = coordinator.data.get("_downstream_by_id", {})

    for (channel_type, channel_id), channel in downstream_by_id.items():
        entities.append(ModemDownstreamPowerSensor(coordinator, entry, channel_type, channel_id))
        entities.append(ModemDownstreamSNRSensor(coordinator, entry, channel_type, channel_id))

        if "frequency" in channel:
            entities.append(ModemDownstreamFrequencySensor(coordinator, entry, channel_type, channel_id))
        if "corrected" in channel:
            entities.append(ModemDownstreamCorrectedSensor(coordinator, entry, channel_type, channel_id))
        if "uncorrected" in channel:
            entities.append(ModemDownstreamUncorrectedSensor(coordinator, entry, channel_type, channel_id))

    return entities


def _create_upstream_sensors(coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> list[SensorEntity]:
    """Create per-channel upstream sensors."""
    entities: list[SensorEntity] = []
    upstream_by_id = coordinator.data.get("_upstream_by_id", {})

    _LOGGER.debug("Creating entities for %s upstream channels", len(upstream_by_id))
    for (channel_type, channel_id), channel in upstream_by_id.items():
        entities.append(ModemUpstreamPowerSensor(coordinator, entry, channel_type, channel_id))
        if "frequency" in channel:
            entities.append(ModemUpstreamFrequencySensor(coordinator, entry, channel_type, channel_id))

    return entities


def _create_lan_stats_sensors(coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> list[SensorEntity]:
    """Create LAN stats sensors for each interface."""
    entities: list[SensorEntity] = []
    lan_stats = coordinator.data.get("cable_modem_lan_stats")

    if not lan_stats:
        return entities

    for interface in lan_stats:
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

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cable Modem Monitor sensors."""
    _LOGGER.debug("async_setup_entry called for %s", entry.entry_id)
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    # Core sensors (always created)
    entities.append(ModemStatusSensor(coordinator, entry))
    entities.append(ModemInfoSensor(coordinator, entry))
    entities.append(ModemHttpLatencySensor(coordinator, entry))
    if coordinator.data.get("supports_icmp", True):
        entities.append(ModemPingLatencySensor(coordinator, entry))

    # System and channel sensors (not in fallback mode)
    is_fallback_mode = coordinator.data.get("cable_modem_fallback_mode", False)
    if not is_fallback_mode:
        entities.extend(_create_system_sensors(coordinator, entry))
    else:
        _LOGGER.info("Fallback mode - skipping channel/system sensors")

    # Per-channel sensors
    entities.extend(_create_downstream_sensors(coordinator, entry))
    entities.extend(_create_upstream_sensors(coordinator, entry))

    # LAN stats sensors
    entities.extend(_create_lan_stats_sensors(coordinator, entry))

    _LOGGER.info("Created %s total sensor entities", len(entities))
    async_add_entities(entities)


class ModemSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for modem sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry

        # Get modem info from config entry
        manufacturer = entry.data.get("detected_manufacturer", "Unknown")
        actual_model = entry.data.get(CONF_ACTUAL_MODEL)
        detected_modem = entry.data.get(CONF_DETECTED_MODEM, "Cable Modem")
        host = entry.data.get(CONF_HOST, "")

        # Use actual_model if available, otherwise fall back to detected_modem
        # Strip manufacturer prefix to avoid redundancy (e.g., "Motorola MB7621" -> "MB7621")
        model = actual_model or detected_modem
        if model and manufacturer and model.lower().startswith(manufacturer.lower()):
            model = model[len(manufacturer) :].strip()

        # Device name based on entity_prefix setting (for multi-modem disambiguation)
        # With has_entity_name=True, entity IDs are generated from device_name + entity_name
        entity_prefix = entry.data.get(CONF_ENTITY_PREFIX, ENTITY_PREFIX_NONE)
        if entity_prefix == ENTITY_PREFIX_MODEL:
            device_name = f"Cable Modem {model}"
        elif entity_prefix == ENTITY_PREFIX_IP:
            sanitized_host = host.replace(".", "_").replace(":", "_")
            device_name = f"Cable Modem {sanitized_host}"
        else:
            device_name = "Cable Modem"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": device_name,
            "manufacturer": manufacturer,
            "model": model,
            "configuration_url": f"http://{host}",
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Sensors remain available if coordinator succeeds, even if modem is temporarily offline
        # This allows sensors to retain last known values during modem reboots
        # Only mark unavailable if we truly can't reach the modem
        status = self.coordinator.data.get("cable_modem_connection_status", "unknown")
        return self.coordinator.last_update_success and status in (
            "online",
            "offline",
            "limited",  # Fallback mode - basic connectivity only
            "parser_issue",  # Known parser but no channel data extracted
            "no_signal",  # Modem online but no cable signal
        )


class ModemStatusSensor(ModemSensorBase):
    """Unified sensor for modem status.

    Pass/fail status combining connection, health, and DOCSIS state:
    - Operational: All good - data parsed, DOCSIS locked, reachable
    - ICMP Blocked: HTTP works but ping fails (only if supports_icmp=True)
    - Partial Lock: Some downstream channels not locked
    - Not Locked: DOCSIS not locked to ISP
    - Parser Error: Modem reachable but data couldn't be parsed
    - Unresponsive: Can't reach modem via HTTP
    """

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Status"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_status"
        self._attr_icon = "mdi:router-network"

    @property
    def available(self) -> bool:
        """Status sensor is always available to show current state."""
        return bool(self.coordinator.last_update_success)

    @property
    def native_value(self) -> str:
        """Return the unified modem status.

        Priority order (most to least concerning):
        1. Unresponsive - can't reach modem via ping OR HTTP
        2. Degraded - ping works but HTTP doesn't (web server hung)
        3. Parser Error - reached modem but can't parse data
        4. Not Locked - DOCSIS not locked to ISP
        5. Partial Lock - some downstream channels unlocked
        6. ICMP Blocked - HTTP works but ping fails (parser expects ping)
        7. Operational - all good
        """
        data = self.coordinator.data

        # Check health status first - can we reach the modem?
        health_status = data.get("health_status", "unknown")
        if health_status == "unresponsive":
            return "Unresponsive"

        # Check connection status - did parsing work?
        connection_status = data.get("cable_modem_connection_status", "unknown")

        # Degraded = ping works but HTTP/scraper failed (web server hung)
        if connection_status == "degraded":
            return "Degraded"

        if connection_status in ("offline", "unreachable"):
            return "Unresponsive"
        if connection_status == "parser_issue":
            return "Parser Error"
        if connection_status == "no_signal":
            return "No Signal"

        # Check DOCSIS status - derive from channel lock status
        docsis_status = self._derive_docsis_status(data)
        if docsis_status == "Not Locked":
            return "Not Locked"
        if docsis_status == "Partial Lock":
            return "Partial Lock"

        # Check for ICMP blocked (only if parser expects ping to work)
        supports_icmp = data.get("supports_icmp", True)
        if supports_icmp and health_status == "icmp_blocked":
            return "ICMP Blocked"

        # All good
        return "Operational"

    def _derive_docsis_status(self, data: dict) -> str:
        """Derive DOCSIS lock status from channel data.

        Returns:
            - "Operational": All DS channels locked and US channels present
            - "Partial Lock": Some DS channels locked
            - "Not Locked": No DS channels locked
        """
        downstream = data.get("cable_modem_downstream", [])
        upstream = data.get("cable_modem_upstream", [])

        if not downstream:
            # No downstream data - might be fallback mode or parser issue
            # Don't report as "Not Locked" if we simply don't have the data
            return "Operational" if data.get("cable_modem_fallback_mode") else "Unknown"

        # Count locked channels
        locked_count = 0
        total_count = len(downstream)

        for ch in downstream:
            lock_status = ch.get("lock_status", "").lower()
            # Consider various "locked" indicators
            if lock_status in ("locked", "locked qam", "qam256", "qam64", "ofdm"):
                locked_count += 1
            elif not lock_status:
                # No lock_status field - assume locked if we have data
                locked_count += 1

        if locked_count == total_count and upstream:
            return "Operational"
        elif locked_count > 0:
            return "Partial Lock"
        else:
            return "Not Locked"

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional diagnostic attributes."""
        data = self.coordinator.data
        return {
            "connection_status": data.get("cable_modem_connection_status", "unknown"),
            "health_status": data.get("health_status", "unknown"),
            "docsis_status": self._derive_docsis_status(data),
            "diagnosis": data.get("health_diagnosis", ""),
        }


class ModemInfoSensor(ModemSensorBase):
    """Sensor for modem device information and parser metadata."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Modem Info"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_info"
        self._attr_icon = "mdi:information-outline"

    @property
    def native_value(self) -> str:
        """Return the detected modem model as the state."""
        return str(self._entry.data.get("detected_modem", "Unknown"))

    @property
    def extra_state_attributes(self) -> dict:
        """Return device metadata as attributes."""
        attrs: dict[str, str | bool | None] = {}

        # Static info from config entry
        attrs["manufacturer"] = self._entry.data.get("detected_manufacturer", "Unknown")

        # Dynamic info from coordinator (parser metadata)
        if release_date := self.coordinator.data.get("_parser_release_date"):
            attrs["release_date"] = release_date
        if docsis_version := self.coordinator.data.get("_parser_docsis_version"):
            attrs["docsis_version"] = docsis_version
        if fixtures_url := self.coordinator.data.get("_parser_fixtures_url"):
            attrs["fixtures_url"] = fixtures_url
        attrs["parser_verified"] = self.coordinator.data.get("_parser_verified", False)

        return attrs


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
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        value = self.coordinator.data.get("cable_modem_total_corrected")
        return int(value) if value is not None else None


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
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        value = self.coordinator.data.get("cable_modem_total_uncorrected")
        return int(value) if value is not None else None


class ModemDownstreamPowerSensor(ModemSensorBase):
    """Sensor for downstream channel power."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        channel_type: str,
        channel_id: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._channel_type = channel_type
        self._channel_id = channel_id
        self._attr_name = f"DS {channel_type.upper()} Ch {channel_id} Power"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_ds_{channel_type}_ch_{channel_id}_power"
        self._attr_native_unit_of_measurement = "dBmV"
        self._attr_icon = "mdi:signal"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        # Use indexed lookup for O(1) performance instead of O(n) linear search
        channel_map = self.coordinator.data.get("_downstream_by_id", {})
        key = (self._channel_type, self._channel_id)
        if key in channel_map:
            value = channel_map[key].get("power")
            return float(value) if value is not None else None
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional channel attributes."""
        channel_map = self.coordinator.data.get("_downstream_by_id", {})
        key = (self._channel_type, self._channel_id)
        if key in channel_map:
            ch = channel_map[key]
            return {
                "channel_id": self._channel_id,
                "channel_type": self._channel_type,
                "frequency": ch.get("frequency"),
            }
        return {}


class ModemDownstreamSNRSensor(ModemSensorBase):
    """Sensor for downstream channel SNR."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, channel_type: str, channel_id: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._channel_type = channel_type
        self._channel_id = channel_id
        self._attr_name = f"DS {channel_type.upper()} Ch {channel_id} SNR"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_ds_{channel_type}_ch_{channel_id}_snr"
        self._attr_native_unit_of_measurement = "dB"
        self._attr_icon = "mdi:signal-variant"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        # Use indexed lookup for O(1) performance instead of O(n) linear search
        channel_map = self.coordinator.data.get("_downstream_by_id", {})
        key = (self._channel_type, self._channel_id)
        if key in channel_map:
            value = channel_map[key].get("snr")
            return float(value) if value is not None else None
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional channel attributes."""
        channel_map = self.coordinator.data.get("_downstream_by_id", {})
        key = (self._channel_type, self._channel_id)
        if key in channel_map:
            ch = channel_map[key]
            return {
                "channel_id": self._channel_id,
                "channel_type": self._channel_type,
                "frequency": ch.get("frequency"),
            }
        return {}


class ModemDownstreamFrequencySensor(ModemSensorBase):
    """Sensor for downstream channel frequency."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, channel_type: str, channel_id: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._channel_type = channel_type
        self._channel_id = channel_id
        self._attr_name = f"DS {channel_type.upper()} Ch {channel_id} Frequency"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_ds_{channel_type}_ch_{channel_id}_frequency"
        self._attr_native_unit_of_measurement = "Hz"
        self._attr_icon = "mdi:sine-wave"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.FREQUENCY

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        # Use indexed lookup for O(1) performance instead of O(n) linear search
        channel_map = self.coordinator.data.get("_downstream_by_id", {})
        key = (self._channel_type, self._channel_id)
        if key in channel_map:
            value = channel_map[key].get("frequency")
            return int(value) if value is not None else None
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional channel attributes."""
        return {
            "channel_id": self._channel_id,
            "channel_type": self._channel_type,
        }


class ModemDownstreamCorrectedSensor(ModemSensorBase):
    """Sensor for downstream channel corrected errors."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, channel_type: str, channel_id: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._channel_type = channel_type
        self._channel_id = channel_id
        self._attr_name = f"DS {channel_type.upper()} Ch {channel_id} Corrected"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_ds_{channel_type}_ch_{channel_id}_corrected"
        self._attr_icon = "mdi:check-circle"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        # Use indexed lookup for O(1) performance instead of O(n) linear search
        channel_map = self.coordinator.data.get("_downstream_by_id", {})
        key = (self._channel_type, self._channel_id)
        if key in channel_map:
            value = channel_map[key].get("corrected")
            return int(value) if value is not None else None
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional channel attributes."""
        channel_map = self.coordinator.data.get("_downstream_by_id", {})
        key = (self._channel_type, self._channel_id)
        if key in channel_map:
            ch = channel_map[key]
            return {
                "channel_id": self._channel_id,
                "channel_type": self._channel_type,
                "frequency": ch.get("frequency"),
            }
        return {}


class ModemDownstreamUncorrectedSensor(ModemSensorBase):
    """Sensor for downstream channel uncorrected errors."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, channel_type: str, channel_id: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._channel_type = channel_type
        self._channel_id = channel_id
        self._attr_name = f"DS {channel_type.upper()} Ch {channel_id} Uncorrected"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_ds_{channel_type}_ch_{channel_id}_uncorrected"
        self._attr_icon = "mdi:alert-circle"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        # Use indexed lookup for O(1) performance instead of O(n) linear search
        channel_map = self.coordinator.data.get("_downstream_by_id", {})
        key = (self._channel_type, self._channel_id)
        if key in channel_map:
            value = channel_map[key].get("uncorrected")
            return int(value) if value is not None else None
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional channel attributes."""
        channel_map = self.coordinator.data.get("_downstream_by_id", {})
        key = (self._channel_type, self._channel_id)
        if key in channel_map:
            ch = channel_map[key]
            return {
                "channel_id": self._channel_id,
                "channel_type": self._channel_type,
                "frequency": ch.get("frequency"),
            }
        return {}


class ModemUpstreamPowerSensor(ModemSensorBase):
    """Sensor for upstream channel power."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, channel_type: str, channel_id: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._channel_type = channel_type
        self._channel_id = channel_id
        self._attr_name = f"US {channel_type.upper()} Ch {channel_id} Power"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_us_{channel_type}_ch_{channel_id}_power"
        self._attr_native_unit_of_measurement = "dBmV"
        self._attr_icon = "mdi:signal"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        # Use indexed lookup for O(1) performance instead of O(n) linear search
        channel_map = self.coordinator.data.get("_upstream_by_id", {})
        key = (self._channel_type, self._channel_id)
        if key in channel_map:
            value = channel_map[key].get("power")
            return float(value) if value is not None else None
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional channel attributes."""
        channel_map = self.coordinator.data.get("_upstream_by_id", {})
        key = (self._channel_type, self._channel_id)
        if key in channel_map:
            ch = channel_map[key]
            return {
                "channel_id": self._channel_id,
                "channel_type": self._channel_type,
                "frequency": ch.get("frequency"),
            }
        return {}


class ModemUpstreamFrequencySensor(ModemSensorBase):
    """Sensor for upstream channel frequency."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, channel_type: str, channel_id: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._channel_type = channel_type
        self._channel_id = channel_id
        self._attr_name = f"US {channel_type.upper()} Ch {channel_id} Frequency"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_us_{channel_type}_ch_{channel_id}_frequency"
        self._attr_native_unit_of_measurement = "Hz"
        self._attr_icon = "mdi:sine-wave"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.FREQUENCY

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        # Use indexed lookup for O(1) performance instead of O(n) linear search
        channel_map = self.coordinator.data.get("_upstream_by_id", {})
        key = (self._channel_type, self._channel_id)
        if key in channel_map:
            value = channel_map[key].get("frequency")
            return int(value) if value is not None else None
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional channel attributes."""
        return {
            "channel_id": self._channel_id,
            "channel_type": self._channel_type,
        }


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
        return int(self.coordinator.data.get("cable_modem_downstream_channel_count", 0))


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
        return int(self.coordinator.data.get("cable_modem_upstream_channel_count", 0))


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
        return str(self.coordinator.data.get("cable_modem_software_version", "Unknown"))


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
        return str(self.coordinator.data.get("cable_modem_system_uptime", "Unknown"))


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
        last_boot: datetime | None = now - timedelta(seconds=uptime_seconds)
        return last_boot


class ModemLanStatsSensor(ModemSensorBase):
    """Base class for LAN statistics sensors."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, interface: str, sensor_type: str
    ) -> None:
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
            value = lan_stats[self._interface].get(self._sensor_type)
            return int(value) if value is not None else None
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
        # No device_class - latency measurements don't have a standard class

    @property
    def available(self) -> bool:
        """Ping sensor is available if we have ping data, independent of HTTP status.

        This allows ping metrics to be reported even when the modem's HTTP
        server is unresponsive (degraded mode).
        """
        if not self.coordinator.last_update_success:
            return False
        if self.coordinator.data is None:
            return False
        # Available if we have ping data (ping_success can be True or False)
        return self.coordinator.data.get("ping_success") is not None

    @property
    def native_value(self) -> int | None:
        """Return the ping latency in milliseconds."""
        ping_latency = self.coordinator.data.get("ping_latency_ms")
        if ping_latency is None:
            return None
        return int(round(ping_latency))


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
        # No device_class - latency measurements don't have a standard class

    @property
    def available(self) -> bool:
        """HTTP sensor is available if we have HTTP check data.

        This allows HTTP metrics to be reported based on health check results,
        independent of full modem data scraping success.
        """
        if not self.coordinator.last_update_success:
            return False
        if self.coordinator.data is None:
            return False
        # Available if we have HTTP data (http_success can be True or False)
        return self.coordinator.data.get("http_success") is not None

    @property
    def native_value(self) -> int | None:
        """Return the HTTP latency in milliseconds."""
        http_latency = self.coordinator.data.get("http_latency_ms")
        if http_latency is None:
            return None
        return int(round(http_latency))
