"""Sensor platform for Cable Modem Monitor.

Creates Home Assistant sensor entities from Core's ModemSnapshot and
HealthInfo types.  All modem-specific logic lives in Core — this module
is pure HA presentation.

Entity types:
    - Status: 10-level priority cascade over connection/health/DOCSIS
    - Modem Info: static metadata from ModemIdentity
    - System: channel counts, error totals, software version, uptime
    - Per-channel: power, SNR, frequency, corrected/uncorrected
    - LAN stats: bytes, packets, errors, drops per interface
    - Health: ICMP and HTTP latency (from health coordinator)

See ENTITY_MODEL_SPEC.md for the full entity catalog.
"""

from __future__ import annotations

import functools
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util
from solentlabs.cable_modem_monitor_core.orchestration.models import (
    HealthInfo,
    ModemSnapshot,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    ConnectionStatus,
    DocsisStatus,
    HealthStatus,
)

from .const import CONF_ENTITY_PREFIX, CONF_SUPPORTS_ICMP, DOMAIN, get_device_name
from .coordinator import CableModemConfigEntry
from .lib.utils import parse_uptime_to_seconds

_LOGGER = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Channel indexing
# ------------------------------------------------------------------


def _index_channels(
    channels: list[dict[str, Any]],
    default_type: str,
) -> dict[tuple[str, str | int], dict[str, Any]]:
    """Build an indexed dict from a channel list for O(1) lookup.

    Args:
        channels: List of channel dicts from modem_data.
        default_type: Default channel_type when not present on channel.

    Returns:
        Dict keyed by (channel_type, channel_id).
    """
    result: dict[tuple[str, str | int], dict[str, Any]] = {}
    for ch in channels:
        ch_type = ch.get("channel_type", default_type)
        ch_id = ch.get("channel_id")
        if ch_id is not None:
            result[(ch_type, ch_id)] = ch
    return result


# ------------------------------------------------------------------
# Status cascade
# ------------------------------------------------------------------


def _compute_display_status(
    connection: ConnectionStatus,
    health: HealthStatus | None,
    docsis: DocsisStatus,
) -> str:
    """Apply the 10-level priority cascade to derive display state.

    Pure lookup — no business logic.  Core derives the three input
    values; this function maps them to a human-readable string.

    See ENTITY_MODEL_SPEC.md § Status Sensor.
    """
    effective_health = health or HealthStatus.UNKNOWN

    if effective_health == HealthStatus.UNRESPONSIVE:
        return "Unresponsive"
    if connection == ConnectionStatus.UNREACHABLE:
        return "Unreachable"
    if connection == ConnectionStatus.AUTH_FAILED:
        return "Auth Failed"
    if effective_health == HealthStatus.DEGRADED:
        return "Degraded"
    if connection == ConnectionStatus.PARSER_ISSUE:
        return "Parser Error"
    if connection == ConnectionStatus.NO_SIGNAL:
        return "No Signal"
    if docsis == DocsisStatus.NOT_LOCKED:
        return "Not Locked"
    if docsis == DocsisStatus.PARTIAL_LOCK:
        return "Partial Lock"
    if effective_health == HealthStatus.ICMP_BLOCKED:
        return "ICMP Blocked"
    return "Operational"


_DIAGNOSIS_MAP: dict[HealthStatus, str] = {
    HealthStatus.RESPONSIVE: "Modem is responsive to health probes",
    HealthStatus.DEGRADED: ("Modem responds to ICMP but HTTP is failing" " — web server may be hung"),
    HealthStatus.ICMP_BLOCKED: ("HTTP works but ICMP is blocked" " — network may filter ping"),
    HealthStatus.UNRESPONSIVE: ("Modem is not responding to any health probes"),
}


def _derive_diagnosis(health: HealthStatus | None) -> str:
    """Derive a human-readable diagnosis from health status."""
    if health is None:
        return ""
    return _DIAGNOSIS_MAP.get(health, "")


# ------------------------------------------------------------------
# Channel metric definitions (table-driven entity creation)
# ------------------------------------------------------------------

# Aliases for table readability
_M = SensorStateClass.MEASUREMENT
_TI = SensorStateClass.TOTAL_INCREASING
_FREQ = SensorDeviceClass.FREQUENCY
_DSIZE = SensorDeviceClass.DATA_SIZE

# Each tuple: (field, name_suffix, unit, device_class, state_class, icon, value_type)
# fmt: off
_DS_METRICS = [
    ("power",       "Power",       "dBmV", None,  _M,  "mdi:signal",        float),
    ("snr",         "SNR",         "dB",   None,  _M,  "mdi:signal-variant", float),
    ("frequency",   "Frequency",   "Hz",   _FREQ, _M,  "mdi:sine-wave",     int),
    ("corrected",   "Corrected",   None,   None,  _TI, "mdi:check-circle",  int),
    ("uncorrected", "Uncorrected", None,   None,  _TI, "mdi:alert-circle",  int),
]

_US_METRICS = [
    ("power",     "Power",     "dBmV", None,  _M, "mdi:signal",    float),
    ("frequency", "Frequency", "Hz",   _FREQ, _M, "mdi:sine-wave", int),
]

_LAN_METRICS = [
    ("received_bytes",      "Received Bytes",      _DSIZE, "B"),
    ("received_packets",    "Received Packets",    None,   None),
    ("received_errors",     "Received Errors",     None,   None),
    ("received_drops",      "Received Drops",      None,   None),
    ("transmitted_bytes",   "Transmitted Bytes",   _DSIZE, "B"),
    ("transmitted_packets", "Transmitted Packets", None,   None),
    ("transmitted_errors",  "Transmitted Errors",  None,   None),
    ("transmitted_drops",   "Transmitted Drops",   None,   None),
]
# fmt: on

# Power and SNR are always created for downstream; power for upstream.
# Other metrics are created only when the field is present on the channel.
_DS_ALWAYS_FIELDS = frozenset(("power", "snr"))
_US_ALWAYS_FIELDS = frozenset(("power",))


# ------------------------------------------------------------------
# Base classes
# ------------------------------------------------------------------


class ModemSensorBase(
    CoordinatorEntity[DataUpdateCoordinator[ModemSnapshot]],
    SensorEntity,
):
    """Base class for sensors that read from the data coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[ModemSnapshot],
        entry: CableModemConfigEntry,
    ) -> None:
        """Initialize with data coordinator and config entry."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=get_device_name(
                entry.data.get(CONF_ENTITY_PREFIX, "default"),
                model=entry.runtime_data.modem_identity.model,
                host=entry.data.get("host", ""),
            ),
        )

    @property
    def _snapshot(self) -> ModemSnapshot:
        """Current snapshot from the data coordinator."""
        return self.coordinator.data

    @property
    def available(self) -> bool:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Available when coordinator succeeds and modem_data is present."""
        return self.coordinator.last_update_success and self._snapshot.modem_data is not None


class HealthSensorBase(  # pyright: ignore[reportIncompatibleVariableOverride]
    CoordinatorEntity[DataUpdateCoordinator[HealthInfo]],
    SensorEntity,
):
    """Base class for sensors that read from the health coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[HealthInfo],
        entry: CableModemConfigEntry,
    ) -> None:
        """Initialize with health coordinator and config entry."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=get_device_name(
                entry.data.get(CONF_ENTITY_PREFIX, "default"),
                model=entry.runtime_data.modem_identity.model,
                host=entry.data.get("host", ""),
            ),
        )

    @property
    def _health_info(self) -> HealthInfo:
        """Current health info from the health coordinator."""
        return self.coordinator.data


# ------------------------------------------------------------------
# System sensors
# ------------------------------------------------------------------


class ModemStatusSensor(ModemSensorBase):
    """Unified status sensor with 10-level priority cascade.

    Listens to both the data coordinator (10min poll) and the health
    coordinator (30s probes) so status reflects health changes in
    near-real-time.

    See ENTITY_MODEL_SPEC.md § Status Sensor.
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[ModemSnapshot],
        entry: CableModemConfigEntry,
    ) -> None:
        """Initialize the status sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Status"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_status"
        self._attr_icon = "mdi:router-network"
        self._health_coordinator: DataUpdateCoordinator[HealthInfo] | None = entry.runtime_data.health_coordinator

    async def async_added_to_hass(self) -> None:
        """Subscribe to both data and health coordinators."""
        await super().async_added_to_hass()
        if self._health_coordinator is not None:
            self.async_on_remove(
                self._health_coordinator.async_add_listener(
                    self._handle_health_update,
                )
            )

    @callback
    def _handle_health_update(self) -> None:
        """Re-render when health coordinator updates."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Status sensor is always available to show current state."""
        return self.coordinator.last_update_success

    @property
    def _latest_health_status(self) -> HealthStatus | None:
        """Return the freshest health status from either source.

        Prefers the health coordinator (30s updates) over the snapshot
        (10min updates) so status reflects health changes promptly.
        """
        if self._health_coordinator is not None and self._health_coordinator.data is not None:
            health_info: HealthInfo = self._health_coordinator.data
            return health_info.health_status
        snapshot = self._snapshot
        return snapshot.health_info.health_status if snapshot.health_info else None

    @functools.cached_property
    def native_value(self) -> str:
        """Return display state from the priority cascade."""
        snapshot = self._snapshot
        return _compute_display_status(
            snapshot.connection_status,
            self._latest_health_status,
            snapshot.docsis_status,
        )

    @functools.cached_property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return connection, health, DOCSIS status and diagnosis."""
        snapshot = self._snapshot
        health_status = self._latest_health_status
        return {
            "connection_status": snapshot.connection_status.value,
            "health_status": (health_status.value if health_status else "unknown"),
            "docsis_status": snapshot.docsis_status.value,
            "diagnosis": _derive_diagnosis(health_status),
        }


class ModemInfoSensor(ModemSensorBase):
    """Static modem metadata from ModemIdentity.

    State is the detected model.  Attributes pass through all
    ModemIdentity fields.  Always available — reads from runtime_data,
    not live poll data.
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[ModemSnapshot],
        entry: CableModemConfigEntry,
    ) -> None:
        """Initialize the modem info sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Modem Info"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_info"
        self._attr_icon = "mdi:information-outline"

    @property
    def available(self) -> bool:
        """Always available — reads static identity, not live data."""
        return self.coordinator.last_update_success

    @functools.cached_property
    def native_value(self) -> str:
        """Return the detected model name."""
        return self._entry.runtime_data.modem_identity.model

    @functools.cached_property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return ModemIdentity fields as attributes."""
        identity = self._entry.runtime_data.modem_identity
        return {
            "manufacturer": identity.manufacturer,
            "model": identity.model,
            "release_date": identity.release_date,
            "docsis_version": identity.docsis_version,
            "status": identity.status,
        }


# ------------------------------------------------------------------
# System info sensors
# ------------------------------------------------------------------


class _SystemInfoSensor(ModemSensorBase):
    """Base for sensors that read from modem_data system_info."""

    def _get_system_info(self) -> dict[str, Any]:
        """Return system_info dict, or empty dict if unavailable."""
        modem_data = self._snapshot.modem_data
        if modem_data is None:
            return {}
        return modem_data.get("system_info", {})  # type: ignore[no-any-return]


class ModemChannelCountSensor(_SystemInfoSensor):
    """Channel count sensor (downstream or upstream)."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[ModemSnapshot],
        entry: CableModemConfigEntry,
        *,
        direction: str,
    ) -> None:
        """Initialize the channel count sensor."""
        super().__init__(coordinator, entry)
        label = "DS" if direction == "downstream" else "US"
        self._field = f"{direction}_channel_count"
        self._attr_name = f"{label} Channel Count"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_{direction}_channel_count"
        self._attr_icon = "mdi:numeric"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @functools.cached_property
    def native_value(self) -> int | None:
        """Return the channel count."""
        value = self._get_system_info().get(self._field)
        return int(value) if value is not None else None


class ModemErrorTotalSensor(_SystemInfoSensor):
    """Total corrected or uncorrected error sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[ModemSnapshot],
        entry: CableModemConfigEntry,
        *,
        error_type: str,
    ) -> None:
        """Initialize the error total sensor."""
        super().__init__(coordinator, entry)
        self._field = f"total_{error_type}"
        label = error_type.title()
        self._attr_name = f"Total {label} Errors"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_total_{error_type}"
        self._attr_icon = "mdi:alert-circle-check" if error_type == "corrected" else "mdi:alert-circle"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @functools.cached_property
    def native_value(self) -> int | None:
        """Return the error total."""
        value = self._get_system_info().get(self._field)
        return int(value) if value is not None else None


class ModemSoftwareVersionSensor(_SystemInfoSensor):
    """Software version sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[ModemSnapshot],
        entry: CableModemConfigEntry,
    ) -> None:
        """Initialize the software version sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Software Version"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_software_version"
        self._attr_icon = "mdi:information-outline"

    @functools.cached_property
    def native_value(self) -> str | None:
        """Return the software version string."""
        return self._get_system_info().get("software_version")


class ModemSystemUptimeSensor(_SystemInfoSensor):
    """System uptime sensor (raw string from modem)."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[ModemSnapshot],
        entry: CableModemConfigEntry,
    ) -> None:
        """Initialize the system uptime sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "System Uptime"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_system_uptime"
        self._attr_icon = "mdi:clock-outline"

    @functools.cached_property
    def native_value(self) -> str | None:
        """Return the uptime string as reported by the modem.

        If the modem reports raw seconds (e.g., "1471890"), formats
        as "17d 0h 51m 30s" for readability.
        """
        raw = self._get_system_info().get("system_uptime")
        if raw and raw.strip().isdigit():
            total = int(raw.strip())
            days, rem = divmod(total, 86400)
            hours, rem = divmod(rem, 3600)
            minutes, seconds = divmod(rem, 60)
            return f"{days}d {hours}h {minutes}m {seconds}s"
        return raw


class ModemLastBootTimeSensor(_SystemInfoSensor):
    """Last boot time (derived from system uptime or counter reset).

    Priority: native system_uptime from modem > counter-reset detection
    from the orchestrator. Counter-reset provides a proxy for modems
    that don't report uptime (see #110).
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[ModemSnapshot],
        entry: CableModemConfigEntry,
    ) -> None:
        """Initialize the last boot time sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Last Boot Time"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_last_boot_time"
        self._attr_icon = "mdi:restart"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @functools.cached_property
    def native_value(self) -> datetime | None:
        """Return last boot time calculated from uptime or counter reset."""
        # Priority 1: native uptime from modem
        uptime_str = self._get_system_info().get("system_uptime")
        if uptime_str:
            uptime_seconds = parse_uptime_to_seconds(uptime_str)
            if uptime_seconds is not None:
                return dt_util.now() - timedelta(seconds=uptime_seconds)

        # Priority 2: counter-reset detection from orchestrator
        return self._snapshot.stats_last_reset


# ------------------------------------------------------------------
# Per-channel sensors
# ------------------------------------------------------------------


class ChannelSensor(ModemSensorBase):
    """Generic channel metric sensor.

    Parameterized by direction, channel key, and metric definition.
    One instance per channel per metric.  All non-metric fields from the
    channel dict flow as extra_state_attributes (tier 2/3 pass-through).
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[ModemSnapshot],
        entry: CableModemConfigEntry,
        *,
        direction: str,
        channel_type: str,
        channel_id: str | int,
        field: str,
        name_suffix: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass,
        icon: str,
        value_type: type,
    ) -> None:
        """Initialize the channel sensor."""
        super().__init__(coordinator, entry)
        self._direction = direction
        self._channel_type = channel_type
        self._channel_id = channel_id
        self._field = field
        self._value_type = value_type

        prefix = "DS" if direction == "downstream" else "US"
        dir_code = "ds" if direction == "downstream" else "us"

        self._attr_name = f"{prefix} {channel_type.upper()} Ch {channel_id} {name_suffix}"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem" f"_{dir_code}_{channel_type}_ch_{channel_id}_{field}"
        self._attr_icon = icon
        self._attr_state_class = state_class
        if unit:
            self._attr_native_unit_of_measurement = unit
        if device_class:
            self._attr_device_class = device_class

    def _find_channel(self) -> dict[str, Any] | None:
        """Find this channel in modem_data by type and ID."""
        modem_data = self._snapshot.modem_data
        if modem_data is None:
            return None
        for ch in modem_data.get(self._direction, []):
            if ch.get("channel_type", "") == self._channel_type and ch.get("channel_id") == self._channel_id:
                return ch  # type: ignore[no-any-return]
        return None

    @functools.cached_property
    def native_value(self) -> float | int | None:
        """Return the channel metric value."""
        ch = self._find_channel()
        if ch is None:
            return None
        value = ch.get(self._field)
        if value is None:
            return None
        return self._value_type(value)  # type: ignore[no-any-return]

    @functools.cached_property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return channel identity and all non-metric fields."""
        attrs: dict[str, Any] = {
            "channel_id": self._channel_id,
            "channel_type": self._channel_type,
        }
        ch = self._find_channel()
        if ch is not None:
            for key, value in ch.items():
                if key not in ("channel_id", "channel_type", self._field):
                    attrs[key] = value
        return attrs


# ------------------------------------------------------------------
# LAN statistics sensors
# ------------------------------------------------------------------


class LanStatsSensor(ModemSensorBase):
    """LAN statistics sensor for a specific interface and metric."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[ModemSnapshot],
        entry: CableModemConfigEntry,
        *,
        interface: str,
        field: str,
        name_suffix: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
    ) -> None:
        """Initialize the LAN stats sensor."""
        super().__init__(coordinator, entry)
        self._interface = interface
        self._field = field
        self._attr_name = f"LAN {interface} {name_suffix}"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_lan_{interface}_{field}"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        if device_class:
            self._attr_device_class = device_class
        if unit:
            self._attr_native_unit_of_measurement = unit

    @functools.cached_property
    def native_value(self) -> int | None:
        """Return the LAN stats value."""
        modem_data = self._snapshot.modem_data
        if modem_data is None:
            return None
        lan_stats = modem_data.get("lan_stats", {})
        iface_data = lan_stats.get(self._interface)
        if iface_data is None:
            return None
        value = iface_data.get(self._field)
        return int(value) if value is not None else None


# ------------------------------------------------------------------
# Health sensors
# ------------------------------------------------------------------


class PingLatencySensor(HealthSensorBase):
    """ICMP ping latency sensor.

    Only created when supports_icmp is True.  Reads from the health
    coordinator, independent of data collection timing.
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[HealthInfo],
        entry: CableModemConfigEntry,
    ) -> None:
        """Initialize the ping latency sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Ping Latency"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_ping_latency"
        self._attr_native_unit_of_measurement = "ms"
        self._attr_icon = "mdi:speedometer"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @functools.cached_property
    def native_value(self) -> int | None:
        """Return ping latency in milliseconds."""
        latency = self._health_info.icmp_latency_ms
        return int(round(latency)) if latency is not None else None


class HttpLatencySensor(HealthSensorBase):
    """HTTP latency sensor.

    Always created when health coordinator exists.  HTTP latency may be
    None when suppressed by collection evidence — this is transient.
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[HealthInfo],
        entry: CableModemConfigEntry,
    ) -> None:
        """Initialize the HTTP latency sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "HTTP Latency"
        self._attr_unique_id = f"{entry.entry_id}_cable_modem_http_latency"
        self._attr_native_unit_of_measurement = "ms"
        self._attr_icon = "mdi:web-clock"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @functools.cached_property
    def native_value(self) -> int | None:
        """Return HTTP latency in milliseconds."""
        latency = self._health_info.http_latency_ms
        return int(round(latency)) if latency is not None else None


# ------------------------------------------------------------------
# Platform setup
# ------------------------------------------------------------------


def _create_channel_sensors(
    data_coord: DataUpdateCoordinator[ModemSnapshot],
    entry: CableModemConfigEntry,
    modem_data: dict[str, Any],
) -> list[SensorEntity]:
    """Create per-channel sensor entities from first poll data."""
    entities: list[SensorEntity] = []

    # Downstream
    ds_index = _index_channels(modem_data.get("downstream", []), "qam")
    for (ch_type, ch_id), ch in ds_index.items():
        for field, name, unit, dev_cls, state_cls, icon, val_type in _DS_METRICS:
            if field in _DS_ALWAYS_FIELDS or field in ch:
                entities.append(
                    ChannelSensor(
                        data_coord,
                        entry,
                        direction="downstream",
                        channel_type=ch_type,
                        channel_id=ch_id,
                        field=field,
                        name_suffix=name,
                        unit=unit,
                        device_class=dev_cls,
                        state_class=state_cls,
                        icon=icon,
                        value_type=val_type,
                    )
                )

    # Upstream
    us_index = _index_channels(modem_data.get("upstream", []), "atdma")
    for (ch_type, ch_id), ch in us_index.items():
        for field, name, unit, dev_cls, state_cls, icon, val_type in _US_METRICS:
            if field in _US_ALWAYS_FIELDS or field in ch:
                entities.append(
                    ChannelSensor(
                        data_coord,
                        entry,
                        direction="upstream",
                        channel_type=ch_type,
                        channel_id=ch_id,
                        field=field,
                        name_suffix=name,
                        unit=unit,
                        device_class=dev_cls,
                        state_class=state_cls,
                        icon=icon,
                        value_type=val_type,
                    )
                )

    return entities


def _create_lan_sensors(
    data_coord: DataUpdateCoordinator[ModemSnapshot],
    entry: CableModemConfigEntry,
    modem_data: dict[str, Any],
) -> list[SensorEntity]:
    """Create LAN statistics sensors from first poll data."""
    entities: list[SensorEntity] = []
    lan_stats = modem_data.get("lan_stats", {})

    for interface in lan_stats:
        for field, name, dev_cls, unit in _LAN_METRICS:
            entities.append(
                LanStatsSensor(
                    data_coord,
                    entry,
                    interface=interface,
                    field=field,
                    name_suffix=name,
                    device_class=dev_cls,
                    unit=unit,
                )
            )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CableModemConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cable Modem Monitor sensor entities."""
    runtime = entry.runtime_data
    data_coord = runtime.data_coordinator
    health_coord = runtime.health_coordinator
    snapshot = data_coord.data

    entities: list[SensorEntity] = []

    # -- Always created --
    entities.append(ModemStatusSensor(data_coord, entry))
    entities.append(ModemInfoSensor(data_coord, entry))

    # -- Health sensors (from health coordinator) --
    if health_coord is not None:
        entities.append(HttpLatencySensor(health_coord, entry))
        if entry.data.get(CONF_SUPPORTS_ICMP, False):
            entities.append(PingLatencySensor(health_coord, entry))

    # -- Data-dependent sensors (require modem_data from first poll) --
    modem_data = snapshot.modem_data if snapshot else None
    if modem_data is None:
        _LOGGER.info(
            "No modem data from first poll [%s] — skipping data sensors",
            runtime.modem_identity.model,
        )
        async_add_entities(entities)
        return

    system_info = modem_data.get("system_info", {})

    # Channel counts (always computed by parser coordinator)
    entities.append(ModemChannelCountSensor(data_coord, entry, direction="downstream"))
    entities.append(ModemChannelCountSensor(data_coord, entry, direction="upstream"))

    # Error totals (gated by field presence)
    if "total_corrected" in system_info:
        entities.append(ModemErrorTotalSensor(data_coord, entry, error_type="corrected"))
    if "total_uncorrected" in system_info:
        entities.append(ModemErrorTotalSensor(data_coord, entry, error_type="uncorrected"))

    # Software version and uptime (gated by field presence)
    if "software_version" in system_info:
        entities.append(ModemSoftwareVersionSensor(data_coord, entry))
    if "system_uptime" in system_info:
        entities.append(ModemSystemUptimeSensor(data_coord, entry))

    # Last boot time — from native uptime OR counter-reset detection.
    # Created when modem has uptime data OR any channel has error counters
    # (for reset proxy — orchestrator sums from channels, not aggregates).
    has_error_counters = any(
        "corrected" in ch or "uncorrected" in ch
        for direction in ("downstream", "upstream")
        for ch in modem_data.get(direction, [])
    )
    if "system_uptime" in system_info or has_error_counters:
        entities.append(ModemLastBootTimeSensor(data_coord, entry))

    # Per-channel sensors
    entities.extend(_create_channel_sensors(data_coord, entry, modem_data))

    # LAN stats sensors
    entities.extend(_create_lan_sensors(data_coord, entry, modem_data))

    _LOGGER.info("Created %d sensor entities [%s]", len(entities), runtime.modem_identity.model)
    async_add_entities(entities)
