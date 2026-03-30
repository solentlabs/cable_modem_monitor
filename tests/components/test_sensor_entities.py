"""Tests for sensor entity creation and value rendering.

Tests the pure _index_channels function and verifies sensor entity
creation logic via _create_channel_sensors and _create_lan_sensors.
Entity value rendering is tested with mock coordinator data.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import SensorStateClass
from solentlabs.cable_modem_monitor_core.orchestration.models import (
    HealthInfo,
    ModemSnapshot,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    ConnectionStatus,
    DocsisStatus,
    HealthStatus,
)

from custom_components.cable_modem_monitor.sensor import (
    ChannelSensor,
    HttpLatencySensor,
    LanStatsSensor,
    ModemChannelCountSensor,
    ModemErrorTotalSensor,
    ModemInfoSensor,
    ModemSoftwareVersionSensor,
    ModemStatusSensor,
    ModemSystemUptimeSensor,
    PingLatencySensor,
    _create_channel_sensors,
    _create_lan_sensors,
    _index_channels,
)

from .conftest import MOCK_ENTRY_DATA, MOCK_MODEM_DATA

# -----------------------------------------------------------------------
# Module-level test data
# -----------------------------------------------------------------------

MODEM_DATA_RAW_SECONDS_UPTIME: dict[str, Any] = {
    "system_info": {"system_uptime": "90061"},
    "downstream": [],
    "upstream": [],
}

MODEM_DATA_WITH_LAN: dict[str, Any] = {
    **MOCK_MODEM_DATA,
    "lan_stats": {
        "eth0": {"received_bytes": 1000, "transmitted_bytes": 500},
    },
}

MODEM_DATA_LAN_SINGLE: dict[str, Any] = {
    **MOCK_MODEM_DATA,
    "lan_stats": {"eth0": {"received_bytes": 42000}},
}

# -----------------------------------------------------------------------
# _index_channels — pure function
# -----------------------------------------------------------------------

# ┌────────────────────────────────┬──────────────┬─────────────────────────┬────────────────────┐
# │ channels                       │ default_type │ expected keys           │ description        │
# ├────────────────────────────────┼──────────────┼─────────────────────────┼────────────────────┤
# │ typed channels                 │ "qam"        │ (type, id) tuples       │ basic indexing     │
# │ missing channel_type           │ "qam"        │ uses default_type       │ default fallback   │
# │ missing channel_id             │ "qam"        │ skipped                 │ no id = no entry   │
# │ empty list                     │ "qam"        │ empty dict              │ no channels        │
# └────────────────────────────────┴──────────────┴─────────────────────────┴────────────────────┘
#
# fmt: off
INDEX_CASES = [
    (
        [{"channel_type": "qam", "channel_id": 1, "power": 2.5}],
        "qam",
        {("qam", 1)},
        "basic",
    ),
    (
        [{"channel_id": 5, "power": 1.0}],
        "ofdm",
        {("ofdm", 5)},
        "default_type",
    ),
    (
        [{"channel_type": "qam", "power": 0.0}],
        "qam",
        set(),
        "no_id_skipped",
    ),
    (
        [],
        "qam",
        set(),
        "empty",
    ),
]
# fmt: on


@pytest.mark.parametrize("channels,default,expected_keys,desc", INDEX_CASES, ids=[c[3] for c in INDEX_CASES])
def test_index_channels(channels, default, expected_keys, desc):
    """_index_channels builds dict keyed by (type, id)."""
    result = _index_channels(channels, default)
    assert set(result.keys()) == expected_keys


# -----------------------------------------------------------------------
# _create_channel_sensors
# -----------------------------------------------------------------------


def _make_coord_and_entry(modem_data, runtime_data):
    """Create mock coordinator and entry for sensor construction."""
    coord = MagicMock()
    coord.data = ModemSnapshot(
        connection_status=ConnectionStatus.ONLINE,
        docsis_status=DocsisStatus.OPERATIONAL,
        modem_data=modem_data,
    )
    coord.last_update_success = True

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = MOCK_ENTRY_DATA
    entry.runtime_data = runtime_data
    return coord, entry


def test_create_channel_sensors_downstream(mock_runtime_data):
    """Downstream channels create power+SNR sensors (always) + conditional metrics."""
    coord, entry = _make_coord_and_entry(MOCK_MODEM_DATA, mock_runtime_data)
    sensors = _create_channel_sensors(coord, entry, MOCK_MODEM_DATA)

    # 2 DS channels × (power, snr always + frequency, corrected, uncorrected present) = 2 × 5 = 10
    # 1 US channel × (power always + frequency present) = 1 × 2 = 2
    # Total = 12
    assert len(sensors) == 12

    # Verify a downstream sensor has correct attributes
    ds_power = [s for s in sensors if "qam" in str(s._attr_unique_id) and "power" in str(s._attr_unique_id)]
    assert len(ds_power) == 1
    assert ds_power[0]._attr_name == "DS QAM Ch 1 Power"


def test_create_channel_sensors_empty_data(mock_runtime_data):
    """No channels produces no sensors."""
    coord, entry = _make_coord_and_entry({}, mock_runtime_data)
    sensors = _create_channel_sensors(coord, entry, {})
    assert sensors == []


def test_create_lan_sensors(mock_runtime_data):
    """LAN stats sensors created per interface per metric."""
    coord, entry = _make_coord_and_entry(MODEM_DATA_WITH_LAN, mock_runtime_data)
    sensors = _create_lan_sensors(coord, entry, MODEM_DATA_WITH_LAN)
    # 1 interface × 8 metrics = 8
    assert len(sensors) == 8


# -----------------------------------------------------------------------
# Sensor value rendering (with mock coordinator)
# -----------------------------------------------------------------------


def _make_sensor(sensor_cls, mock_runtime_data, modem_data=None, **kwargs):
    """Helper to construct a sensor with mock coordinator."""
    snapshot = ModemSnapshot(
        connection_status=ConnectionStatus.ONLINE,
        docsis_status=DocsisStatus.OPERATIONAL,
        modem_data=modem_data if modem_data is not None else MOCK_MODEM_DATA,
        health_info=HealthInfo(health_status=HealthStatus.RESPONSIVE, icmp_latency_ms=2.5, http_latency_ms=15.0),
    )
    coord = MagicMock()
    coord.data = snapshot
    coord.last_update_success = True

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = MOCK_ENTRY_DATA
    entry.runtime_data = mock_runtime_data

    return sensor_cls(coord, entry, **kwargs)


def test_channel_count_sensor_value(mock_runtime_data):
    """Channel count sensor reads from system_info."""
    sensor = _make_sensor(ModemChannelCountSensor, mock_runtime_data, direction="downstream")
    assert sensor.native_value == 2


def test_channel_count_sensor_missing(mock_runtime_data):
    """Channel count returns None when system_info missing."""
    sensor = _make_sensor(ModemChannelCountSensor, mock_runtime_data, modem_data={}, direction="downstream")
    assert sensor.native_value is None


def test_error_total_sensor_value(mock_runtime_data):
    """Error total reads from system_info."""
    sensor = _make_sensor(ModemErrorTotalSensor, mock_runtime_data, error_type="corrected")
    assert sensor.native_value == 150


def test_software_version_sensor_value(mock_runtime_data):
    """Software version sensor returns version string."""
    sensor = _make_sensor(ModemSoftwareVersionSensor, mock_runtime_data)
    assert sensor.native_value == "4502.9.016"


def test_system_uptime_sensor_value(mock_runtime_data):
    """System uptime returns raw string."""
    sensor = _make_sensor(ModemSystemUptimeSensor, mock_runtime_data)
    assert sensor.native_value == "2d 5h 30m"


def test_system_uptime_sensor_raw_seconds(mock_runtime_data):
    """System uptime formats raw seconds into human-readable form."""
    sensor = _make_sensor(ModemSystemUptimeSensor, mock_runtime_data, modem_data=MODEM_DATA_RAW_SECONDS_UPTIME)
    assert sensor.native_value == "1d 1h 1m 1s"


def test_modem_info_sensor(mock_runtime_data):
    """Modem info shows model name and identity attributes."""
    sensor = _make_sensor(ModemInfoSensor, mock_runtime_data)
    assert sensor.native_value == "MB7621"
    attrs = sensor.extra_state_attributes
    assert attrs["manufacturer"] == "Motorola"
    assert attrs["status"] == "verified"


def test_modem_status_sensor_operational(mock_runtime_data):
    """Status sensor shows Operational when all good."""
    snapshot = ModemSnapshot(
        connection_status=ConnectionStatus.ONLINE,
        docsis_status=DocsisStatus.OPERATIONAL,
        modem_data=MOCK_MODEM_DATA,
        health_info=HealthInfo(health_status=HealthStatus.RESPONSIVE),
    )
    coord = MagicMock()
    coord.data = snapshot
    coord.last_update_success = True

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = MOCK_ENTRY_DATA
    entry.runtime_data = mock_runtime_data
    entry.runtime_data.health_coordinator = None  # No separate health coord

    sensor = ModemStatusSensor(coord, entry)
    assert sensor.native_value == "Operational"
    assert sensor.extra_state_attributes["connection_status"] == "online"


def test_channel_sensor_native_value(mock_runtime_data):
    """Channel sensor reads correct field from channel data."""
    coord = MagicMock()
    coord.data = ModemSnapshot(
        connection_status=ConnectionStatus.ONLINE,
        docsis_status=DocsisStatus.OPERATIONAL,
        modem_data=MOCK_MODEM_DATA,
    )
    coord.last_update_success = True

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = MOCK_ENTRY_DATA
    entry.runtime_data = mock_runtime_data

    sensor = ChannelSensor(
        coord,
        entry,
        direction="downstream",
        channel_type="qam",
        channel_id=1,
        field="power",
        name_suffix="Power",
        unit="dBmV",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:signal",
        value_type=float,
    )
    assert sensor.native_value == 2.5
    attrs = sensor.extra_state_attributes
    assert attrs["channel_id"] == 1
    assert attrs["channel_type"] == "qam"
    # Non-metric fields pass through
    assert "modulation" in attrs


def test_channel_sensor_not_found(mock_runtime_data):
    """Channel sensor returns None when channel not in data."""
    coord = MagicMock()
    coord.data = ModemSnapshot(
        connection_status=ConnectionStatus.ONLINE,
        docsis_status=DocsisStatus.OPERATIONAL,
        modem_data=MOCK_MODEM_DATA,
    )

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = MOCK_ENTRY_DATA
    entry.runtime_data = mock_runtime_data

    sensor = ChannelSensor(
        coord,
        entry,
        direction="downstream",
        channel_type="qam",
        channel_id=999,  # doesn't exist
        field="power",
        name_suffix="Power",
        unit="dBmV",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:signal",
        value_type=float,
    )
    assert sensor.native_value is None


def test_health_sensor_ping_latency(mock_runtime_data):
    """Ping latency sensor reads from health coordinator."""
    health_info = HealthInfo(
        health_status=HealthStatus.RESPONSIVE,
        icmp_latency_ms=3.7,
        http_latency_ms=12.0,
    )
    coord = MagicMock()
    coord.data = health_info
    coord.last_update_success = True

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = MOCK_ENTRY_DATA
    entry.runtime_data = mock_runtime_data

    sensor = PingLatencySensor(coord, entry)
    assert sensor.native_value == 4  # rounded from 3.7


def test_health_sensor_http_latency(mock_runtime_data):
    """HTTP latency sensor reads from health coordinator."""
    health_info = HealthInfo(
        health_status=HealthStatus.RESPONSIVE,
        icmp_latency_ms=2.5,
        http_latency_ms=14.8,
    )
    coord = MagicMock()
    coord.data = health_info
    coord.last_update_success = True

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = MOCK_ENTRY_DATA
    entry.runtime_data = mock_runtime_data

    sensor = HttpLatencySensor(coord, entry)
    assert sensor.native_value == 15  # rounded from 14.8


def test_lan_stats_sensor_value(mock_runtime_data):
    """LAN stats sensor reads interface data."""
    coord = MagicMock()
    coord.data = ModemSnapshot(
        connection_status=ConnectionStatus.ONLINE,
        docsis_status=DocsisStatus.OPERATIONAL,
        modem_data=MODEM_DATA_LAN_SINGLE,
    )
    coord.last_update_success = True

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = MOCK_ENTRY_DATA
    entry.runtime_data = mock_runtime_data

    sensor = LanStatsSensor(
        coord,
        entry,
        interface="eth0",
        field="received_bytes",
        name_suffix="Received Bytes",
        device_class=None,
        unit="B",
    )
    assert sensor.native_value == 42000
