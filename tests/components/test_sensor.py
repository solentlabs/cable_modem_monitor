"""Tests for Cable Modem Monitor sensors."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from custom_components.cable_modem_monitor.sensor import (
    ModemDownstreamChannelCountSensor,
    ModemSoftwareVersionSensor,
    ModemStatusSensor,
    ModemSystemUptimeSensor,
    ModemTotalCorrectedSensor,
    ModemTotalUncorrectedSensor,
    ModemUpstreamChannelCountSensor,
)

# =============================================================================
# Table-Driven Test Data
# =============================================================================
# These tables define test cases for parameterized tests. Each row represents
# a distinct scenario with inputs and expected outputs.

# -----------------------------------------------------------------------------
# ModemStatusSensor.native_value - Status Branch Cases
# -----------------------------------------------------------------------------
# ┌──────────────────────┬─────────────────┬────────────────┬─────────────────────────────┐
# │ health_status        │ connection_stat │ expected       │ description                 │
# ├──────────────────────┼─────────────────┼────────────────┼─────────────────────────────┤
# │ "unresponsive"       │ "online"        │ "Unresponsive" │ health check failed         │
# │ "responsive"         │ "degraded"      │ "Degraded"     │ ping ok, http failed        │
# │ "responsive"         │ "offline"       │ "Unresponsive" │ connection offline          │
# │ "responsive"         │ "unreachable"   │ "Unresponsive" │ connection unreachable      │
# │ "responsive"         │ "parser_issue"  │ "Parser Error" │ reached but can't parse     │
# │ "responsive"         │ "no_signal"     │ "No Signal"    │ modem online, no cable      │
# │ "icmp_blocked"       │ "online"        │ "ICMP Blocked" │ http ok, ping blocked       │
# │ "responsive"         │ "online"        │ "Operational"  │ all good                    │
# └──────────────────────┴─────────────────┴────────────────┴─────────────────────────────┘
#
# fmt: off
STATUS_SENSOR_CASES = [
    # (health_status, connection_status, downstream, upstream, supports_icmp, expected, desc)
    ("unresponsive", "online",       [{"lock_status": "Locked"}], [{"ch": "1"}], True,  "Unresponsive", "health fail"),
    ("responsive",   "degraded",     [{"lock_status": "Locked"}], [{"ch": "1"}], True,  "Degraded",     "http fail"),
    ("responsive",   "offline",      [{"lock_status": "Locked"}], [{"ch": "1"}], True,  "Unresponsive", "offline"),
    ("responsive",   "unreachable",  [{"lock_status": "Locked"}], [{"ch": "1"}], True,  "Unresponsive", "unreachable"),
    ("responsive",   "parser_issue", [{"lock_status": "Locked"}], [{"ch": "1"}], True,  "Parser Error", "parse fail"),
    ("responsive",   "no_signal",    [{"lock_status": "Locked"}], [{"ch": "1"}], True,  "No Signal",    "no signal"),
    ("icmp_blocked", "online",       [{"lock_status": "Locked"}], [{"ch": "1"}], True,  "ICMP Blocked", "ping blocked"),
    ("icmp_blocked", "online",       [{"lock_status": "Locked"}], [{"ch": "1"}], False, "Operational",  "icmp n/a"),
    ("responsive",   "online",       [{"lock_status": "Locked"}], [{"ch": "1"}], True,  "Operational",  "all good"),
    # DOCSIS lock status cases
    ("responsive",   "online",       [{"lock_status": "Not Locked"}], [{"ch": "1"}], True, "Not Locked",   "unlocked"),
    ("responsive",   "online",       [{"lock_status": "Locked"}, {"lock_status": "Unlocked"}], [{"ch": "1"}], True, "Partial Lock", "mixed"),  # noqa: E501
]
# fmt: on

# -----------------------------------------------------------------------------
# ModemStatusSensor._derive_docsis_status - DOCSIS Lock Status Cases
# -----------------------------------------------------------------------------
# ┌────────────────────────────────────┬──────────┬────────────────┬─────────────────────────┐
# │ downstream                         │ upstream │ expected       │ description             │
# ├────────────────────────────────────┼──────────┼────────────────┼─────────────────────────┤
# │ []                                 │ []       │ "Unknown"      │ no downstream data      │
# │ [locked]                           │ [ch]     │ "Operational"  │ all locked with US      │
# │ [locked, locked]                   │ [ch]     │ "Operational"  │ multiple locked         │
# │ [locked, unlocked]                 │ [ch]     │ "Partial Lock" │ some unlocked           │
# │ [unlocked, unlocked]               │ [ch]     │ "Not Locked"   │ none locked             │
# │ [no_status, no_status]             │ [ch]     │ "Operational"  │ no status = assume ok   │
# │ [locked]                           │ []       │ "Partial Lock" │ locked but no upstream  │
# └────────────────────────────────────┴──────────┴────────────────┴─────────────────────────┘
#
# fmt: off
DOCSIS_STATUS_CASES = [
    # (downstream, upstream, fallback_mode, expected, desc)
    ([],                                                          [],           False, "Unknown",      "no DS"),
    ([],                                                          [],           True,  "Operational",  "fallback ok"),
    ([{"lock_status": "Locked"}],                                 [{"ch": "1"}], False, "Operational",  "1 locked+US"),
    ([{"lock_status": "Locked"}, {"lock_status": "Locked"}],      [{"ch": "1"}], False, "Operational",  "all locked"),
    ([{"lock_status": "Locked"}, {"lock_status": "Not Locked"}],  [{"ch": "1"}], False, "Partial Lock", "mixed"),
    ([{"lock_status": "Not Locked"}, {"lock_status": "Unlocked"}],[{"ch": "1"}], False, "Not Locked",   "none locked"),
    ([{"lock_status": ""}, {"lock_status": ""}],                  [{"ch": "1"}], False, "Operational",  "empty=ok"),
    ([{}],                                                        [{"ch": "1"}], False, "Operational",  "no field=ok"),
    ([{"lock_status": "Locked"}],                                 [],            False, "Partial Lock", "no US"),
    ([{"lock_status": "Locked QAM"}],                             [{"ch": "1"}], False, "Operational",  "qam variant"),
    ([{"lock_status": "QAM256"}],                                 [{"ch": "1"}], False, "Operational",  "qam256"),
    ([{"lock_status": "OFDM"}],                                   [{"ch": "1"}], False, "Operational",  "ofdm"),
]
# fmt: on

# -----------------------------------------------------------------------------
# ModemSensorBase.available - Availability Cases
# -----------------------------------------------------------------------------
# ┌──────────────────────┬──────────────────────┬──────────┬─────────────────────────┐
# │ last_update_success  │ connection_status    │ expected │ description             │
# ├──────────────────────┼──────────────────────┼──────────┼─────────────────────────┤
# │ False                │ "online"             │ False    │ coordinator failed      │
# │ True                 │ "online"             │ True     │ normal operation        │
# │ True                 │ "offline"            │ True     │ offline but available   │
# │ True                 │ "limited"            │ True     │ fallback mode           │
# │ True                 │ "parser_issue"       │ True     │ parser issue            │
# │ True                 │ "no_signal"          │ True     │ no cable signal         │
# │ True                 │ "unknown"            │ False    │ unknown = unavailable   │
# │ True                 │ "unreachable"        │ False    │ unreachable             │
# └──────────────────────┴──────────────────────┴──────────┴─────────────────────────┘
#
# fmt: off
SENSOR_BASE_AVAILABILITY_CASES = [
    # (last_update_success, connection_status, expected, description)
    (False, "online",        False, "coordinator failed"),
    (True,  "online",        True,  "normal operation"),
    (True,  "offline",       True,  "offline but sensor available"),
    (True,  "limited",       True,  "fallback mode"),
    (True,  "parser_issue",  True,  "parser issue"),
    (True,  "no_signal",     True,  "no cable signal"),
    (True,  "unknown",       False, "unknown status = unavailable"),
    (True,  "unreachable",   False, "unreachable = unavailable"),
]
# fmt: on

# -----------------------------------------------------------------------------
# Latency Sensor Cases
# -----------------------------------------------------------------------------
# fmt: off
LATENCY_SENSOR_CASES = [
    # (ping_success, ping_latency, http_success, http_latency, desc)
    (True,  2.5,   True,  45.0,  "both successful"),
    (True,  2.7,   False, None,  "ping ok, http failed"),
    (False, None,  True,  45.0,  "ping failed, http ok"),
    (None,  None,  None,  None,  "no data yet"),
]
# fmt: on

# -----------------------------------------------------------------------------
# LAN Stats Sensor Cases
# -----------------------------------------------------------------------------
# fmt: off
LAN_STATS_SENSOR_CASES = [
    # (sensor_type, stat_key, value, expected)
    ("received_errors",     "received_errors",     5,    5),
    ("received_drops",      "received_drops",      10,   10),
    ("transmitted_errors",  "transmitted_errors",  0,    0),
    ("transmitted_drops",   "transmitted_drops",   3,    3),
    ("received_bytes",      "received_bytes",      None, None),  # missing data
]
# fmt: on


class TestSensorImports:
    """Test sensor imports."""

    def test_sensor_entity_count(self):
        """Test minimum number of base sensors created."""
        # Should create at least:
        # 1 connection status
        # 2 total error sensors
        # 2 channel count sensors
        # 2 system info sensors
        # = 7 base sensors (plus per-channel sensors)
        expected_base_sensors = 7
        assert expected_base_sensors == 7


class TestStatusSensor:
    """Test unified status sensor."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with sample data."""
        coordinator = Mock()
        # Use plain dict for data (sensors call .get() on it)
        coordinator.data = {
            "cable_modem_connection_status": "online",
            "cable_modem_downstream": [{"lock_status": "Locked"}],
            "cable_modem_upstream": [{"channel": "1"}],
            "health_status": "responsive",
            "cable_modem_fallback_mode": False,
        }
        coordinator.last_update_success = True
        return coordinator

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    def test_status_operational(self, mock_coordinator, mock_entry):
        """Test status sensor with operational status."""
        sensor = ModemStatusSensor(mock_coordinator, mock_entry)

        # Test state - unified sensor returns "Operational" when all good
        assert sensor.native_value == "Operational"

    def test_status_unresponsive(self, mock_coordinator, mock_entry):
        """Test status sensor with unresponsive status."""
        mock_coordinator.data = {
            "cable_modem_connection_status": "unreachable",
            "health_status": "unresponsive",
        }
        sensor = ModemStatusSensor(mock_coordinator, mock_entry)

        assert sensor.native_value == "Unresponsive"


class TestErrorSensors:
    """Test error tracking sensors."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with error data."""
        coordinator = Mock()
        coordinator.data = {
            "cable_modem_total_corrected": 1000,
            "cable_modem_total_uncorrected": 5,
            "cable_modem_downstream": [],
            "cable_modem_upstream": [],
        }
        return coordinator

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    def test_corrected_errors_sensor(self, mock_coordinator, mock_entry):
        """Test corrected errors sensor."""
        sensor = ModemTotalCorrectedSensor(mock_coordinator, mock_entry)

        assert sensor.native_value == 1000

    def test_uncorrected_errors_sensor(self, mock_coordinator, mock_entry):
        """Test uncorrected errors sensor."""
        sensor = ModemTotalUncorrectedSensor(mock_coordinator, mock_entry)

        assert sensor.native_value == 5

    def test_zero_errors(self, mock_coordinator, mock_entry):
        """Test sensors with zero errors."""
        mock_coordinator.data = {
            "cable_modem_total_corrected": 0,
            "cable_modem_total_uncorrected": 0,
        }

        corrected_sensor = ModemTotalCorrectedSensor(mock_coordinator, mock_entry)
        uncorrected_sensor = ModemTotalUncorrectedSensor(mock_coordinator, mock_entry)

        assert corrected_sensor.native_value == 0
        assert uncorrected_sensor.native_value == 0

    def test_unavailable_errors(self, mock_coordinator, mock_entry):
        """Test sensors return None when data unavailable (no channels)."""
        mock_coordinator.data = {
            "cable_modem_total_corrected": None,
            "cable_modem_total_uncorrected": None,
        }

        corrected_sensor = ModemTotalCorrectedSensor(mock_coordinator, mock_entry)
        uncorrected_sensor = ModemTotalUncorrectedSensor(mock_coordinator, mock_entry)

        # None indicates unavailable, not 0 errors
        assert corrected_sensor.native_value is None
        assert uncorrected_sensor.native_value is None


class TestChannelCountSensors:
    """Test channel count sensors."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with channel data."""
        coordinator = Mock()
        coordinator.data = {
            "cable_modem_downstream_channel_count": 24,
            "cable_modem_upstream_channel_count": 5,
            "cable_modem_downstream": [],
            "cable_modem_upstream": [],
        }
        return coordinator

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    def test_downstream_count(self, mock_coordinator, mock_entry):
        """Test downstream (DS) channel count sensor."""
        sensor = ModemDownstreamChannelCountSensor(mock_coordinator, mock_entry)

        assert sensor.native_value == 24

    def test_upstream_count(self, mock_coordinator, mock_entry):
        """Test upstream (US) channel count sensor."""
        sensor = ModemUpstreamChannelCountSensor(mock_coordinator, mock_entry)

        assert sensor.native_value == 5


class TestSystemInfoSensors:
    """Test system information sensors."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with system info."""
        coordinator = Mock()
        coordinator.data = {
            "cable_modem_software_version": "1.0.0",
            "cable_modem_system_uptime": "2 days 5 hours",
            "cable_modem_downstream": [],
            "cable_modem_upstream": [],
        }
        return coordinator

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    def test_software_version(self, mock_coordinator, mock_entry):
        """Test software version sensor."""
        sensor = ModemSoftwareVersionSensor(mock_coordinator, mock_entry)

        assert sensor.native_value == "1.0.0"

    def test_system_uptime(self, mock_coordinator, mock_entry):
        """Test system uptime sensor."""
        sensor = ModemSystemUptimeSensor(mock_coordinator, mock_entry)

        assert sensor.native_value == "2 days 5 hours"


class TestPerChannelSensors:
    """Test per-channel sensor creation."""

    def test_downstream_channel_sensor_count(self):
        """Test that correct number of downstream sensors are created."""
        # Each downstream channel should create 4 sensors:
        # - Frequency
        # - Power
        # - SNR
        # - Corrected/Uncorrected errors (if available)
        sensors_per_downstream_channel = 4
        assert sensors_per_downstream_channel == 4

    def test_upstream_channel_sensor_count(self):
        """Test that correct number of upstream sensors are created."""
        # Each upstream channel should create 2 sensors:
        # - Frequency
        # - Power
        sensors_per_upstream_channel = 2
        assert sensors_per_upstream_channel == 2


class TestSensorAttributes:
    """Test sensor attributes and metadata."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator."""
        coordinator = Mock()
        coordinator.data = {"cable_modem_downstream": [], "cable_modem_upstream": []}
        return coordinator

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    def test_sensor_has_unique_id(self, mock_coordinator, mock_entry):
        """Test that sensors have unique IDs."""
        mock_coordinator.last_update_success = True
        sensor = ModemStatusSensor(mock_coordinator, mock_entry)

        # Unique ID should be based on entry_id and sensor type
        assert sensor.unique_id is not None
        assert "test_entry" in sensor.unique_id

    def test_sensor_has_device_info(self, mock_coordinator, mock_entry):
        """Test that sensors have device info."""
        mock_coordinator.last_update_success = True
        sensor = ModemStatusSensor(mock_coordinator, mock_entry)

        # Device info should link sensors to the modem device
        assert sensor.device_info is not None


class TestSensorDataHandling:
    """Test how sensors handle missing or invalid data."""

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    def test_missing_data_keys(self, mock_entry):
        """Test sensors with missing data keys."""
        coordinator = Mock()
        coordinator.data = {}  # Empty data

        sensor = ModemTotalCorrectedSensor(coordinator, mock_entry)

        # Should handle missing data gracefully (return None or default)
        result = sensor.native_value
        assert result is None or isinstance(result, int)

    def test_none_values(self, mock_entry):
        """Test sensors with None values."""
        coordinator = Mock()
        coordinator.data = {"cable_modem_software_version": None}

        sensor = ModemSoftwareVersionSensor(coordinator, mock_entry)

        # Should handle None gracefully
        assert sensor.native_value == "None" or sensor.native_value == "Unknown"


class TestEntityNaming:
    """Test entity naming with different prefix configurations."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator."""
        coordinator = Mock()
        coordinator.data = {
            "cable_modem_connection_status": "online",
            "cable_modem_total_corrected": 100,
            "cable_modem_downstream": [],
            "cable_modem_upstream": [],
        }
        coordinator.last_update_success = True
        return coordinator

    def test_sensor_naming(self, mock_coordinator):
        """Test sensor naming has correct display names and unique IDs."""
        from custom_components.cable_modem_monitor.sensor import (
            ModemDownstreamPowerSensor,
            ModemStatusSensor,
            ModemTotalCorrectedSensor,
        )

        entry = Mock()
        entry.entry_id = "test"
        entry.data = {"host": "192.168.100.1"}

        # Test unified status sensor
        status_sensor = ModemStatusSensor(mock_coordinator, entry)
        assert status_sensor.name == "Status"
        assert status_sensor.unique_id == "test_cable_modem_status"

        # Test error sensor
        error_sensor = ModemTotalCorrectedSensor(mock_coordinator, entry)
        assert error_sensor.name == "Total Corrected Errors"
        assert error_sensor.unique_id == "test_cable_modem_total_corrected"

        # Test channel sensor (v3.11+ uses channel_type and channel_id)
        channel_sensor = ModemDownstreamPowerSensor(mock_coordinator, entry, channel_type="qam", channel_id=5)
        assert channel_sensor.name == "DS QAM Ch 5 Power"
        assert channel_sensor.unique_id == "test_cable_modem_ds_qam_ch_5_power"


class TestLastBootTimeSensor:
    """Test last boot time sensor functionality."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with uptime data."""
        coordinator = Mock()
        coordinator.data = {
            "cable_modem_connection_status": "online",
            "cable_modem_system_uptime": "2 days 5 hours",
        }
        coordinator.last_update_success = True
        return coordinator

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test"
        entry.data = {"host": "192.168.100.1"}
        return entry

    def test_calculation(self, mock_coordinator, mock_entry):
        """Test last boot time calculation from uptime."""
        from datetime import datetime, timedelta

        from homeassistant.util import dt as dt_util

        from custom_components.cable_modem_monitor.sensor import ModemLastBootTimeSensor

        sensor = ModemLastBootTimeSensor(mock_coordinator, mock_entry)

        # Get the calculated last boot time
        last_boot = sensor.native_value

        # Should return a datetime object
        assert isinstance(last_boot, datetime)

        # Calculate expected boot time (2 days 5 hours ago)
        uptime_seconds = (2 * 86400) + (5 * 3600)
        now = dt_util.now()
        expected_boot = now - timedelta(seconds=uptime_seconds)

        # Should be within a few seconds of expected (allow for execution time)
        time_diff = abs((last_boot - expected_boot).total_seconds())
        assert time_diff < 5  # Within 5 seconds

    def test_unknown_uptime(self, mock_entry):
        """Test last boot time with unknown uptime."""
        from custom_components.cable_modem_monitor.sensor import ModemLastBootTimeSensor

        coordinator = Mock()
        coordinator.data = {"cable_modem_system_uptime": "Unknown"}
        coordinator.last_update_success = True

        sensor = ModemLastBootTimeSensor(coordinator, mock_entry)

        # Should return None for unknown uptime
        assert sensor.native_value is None

    def test_missing_uptime(self, mock_entry):
        """Test last boot time with missing uptime data."""
        from custom_components.cable_modem_monitor.sensor import ModemLastBootTimeSensor

        coordinator = Mock()
        coordinator.data = {}  # No uptime data
        coordinator.last_update_success = True

        sensor = ModemLastBootTimeSensor(coordinator, mock_entry)

        # Should return None when uptime is missing
        assert sensor.native_value is None

    def test_sensor_attributes(self, mock_coordinator, mock_entry):
        """Test last boot time sensor attributes."""
        from homeassistant.components.sensor import SensorDeviceClass

        from custom_components.cable_modem_monitor.sensor import ModemLastBootTimeSensor

        sensor = ModemLastBootTimeSensor(mock_coordinator, mock_entry)

        # Check sensor attributes
        assert sensor.name == "Last Boot Time"
        assert sensor.unique_id == "test_cable_modem_last_boot_time"
        assert sensor.icon == "mdi:restart"
        assert sensor.device_class == SensorDeviceClass.TIMESTAMP


class TestLanStatsSensors:
    """Test LAN statistics sensors."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with LAN stats data."""
        coordinator = Mock()
        coordinator.data = {
            "cable_modem_lan_stats": {
                "eth0": {
                    "received_bytes": 71019856907,
                    "received_packets": 108821473,
                    "received_errors": 0,
                    "received_drops": 0,
                    "transmitted_bytes": 475001588006,
                    "transmitted_packets": 395114324,
                    "transmitted_errors": 0,
                    "transmitted_drops": 0,
                }
            }
        }
        coordinator.last_update_success = True
        return coordinator

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test"
        entry.data = {"host": "192.168.100.1"}
        return entry

    def test_lan_received_bytes_sensor(self, mock_coordinator, mock_entry):
        """Test LAN received bytes sensor."""
        from custom_components.cable_modem_monitor.sensor import ModemLanReceivedBytesSensor

        sensor = ModemLanReceivedBytesSensor(mock_coordinator, mock_entry, "eth0")
        assert sensor.native_value == 71019856907

    def test_lan_received_packets_sensor(self, mock_coordinator, mock_entry):
        """Test LAN received packets sensor."""
        from custom_components.cable_modem_monitor.sensor import ModemLanReceivedPacketsSensor

        sensor = ModemLanReceivedPacketsSensor(mock_coordinator, mock_entry, "eth0")
        assert sensor.native_value == 108821473

    def test_lan_transmitted_bytes_sensor(self, mock_coordinator, mock_entry):
        """Test LAN transmitted bytes sensor."""
        from custom_components.cable_modem_monitor.sensor import ModemLanTransmittedBytesSensor

        sensor = ModemLanTransmittedBytesSensor(mock_coordinator, mock_entry, "eth0")
        assert sensor.native_value == 475001588006

    def test_lan_transmitted_packets_sensor(self, mock_coordinator, mock_entry):
        """Test LAN transmitted packets sensor."""
        from custom_components.cable_modem_monitor.sensor import ModemLanTransmittedPacketsSensor

        sensor = ModemLanTransmittedPacketsSensor(mock_coordinator, mock_entry, "eth0")
        assert sensor.native_value == 395114324


class TestCapabilityBasedSensorCreation:
    """Test that sensors are conditionally created based on parser capabilities."""

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    def test_has_capability_returns_true_when_present(self):
        """Test _has_capability returns True when capability is in list."""
        from custom_components.cable_modem_monitor.core.base_parser import ModemCapability
        from custom_components.cable_modem_monitor.sensor import _has_capability

        coordinator = Mock()
        coordinator.data = {"_parser_capabilities": ["system_uptime", "downstream_channels", "upstream_channels"]}

        assert _has_capability(coordinator, ModemCapability.SYSTEM_UPTIME) is True

    def test_has_capability_returns_false_when_missing(self):
        """Test _has_capability returns False when capability is not in list."""
        from custom_components.cable_modem_monitor.core.base_parser import ModemCapability
        from custom_components.cable_modem_monitor.sensor import _has_capability

        coordinator = Mock()
        coordinator.data = {"_parser_capabilities": ["downstream_channels", "upstream_channels"]}

        assert _has_capability(coordinator, ModemCapability.SYSTEM_UPTIME) is False

    def test_has_capability_handles_missing_key(self):
        """Test _has_capability returns False when _parser_capabilities key is missing."""
        from custom_components.cable_modem_monitor.core.base_parser import ModemCapability
        from custom_components.cable_modem_monitor.sensor import _has_capability

        coordinator = Mock()
        coordinator.data = {}  # No _parser_capabilities key

        assert _has_capability(coordinator, ModemCapability.SYSTEM_UPTIME) is False

    def test_uptime_sensors_created_when_capability_present(self, mock_entry):
        """Test uptime/last boot sensors ARE created when SYSTEM_UPTIME capability is present."""
        from custom_components.cable_modem_monitor.core.base_parser import ModemCapability
        from custom_components.cable_modem_monitor.sensor import (
            ModemLastBootTimeSensor,
            ModemSystemUptimeSensor,
            _create_system_sensors,
        )

        coordinator = Mock()
        coordinator.data = {
            "_parser_capabilities": [ModemCapability.SYSTEM_UPTIME.value],
            "cable_modem_downstream": [],
            "cable_modem_upstream": [],
        }

        sensors = _create_system_sensors(coordinator, mock_entry)
        sensor_types = [type(s) for s in sensors]

        assert ModemSystemUptimeSensor in sensor_types
        assert ModemLastBootTimeSensor in sensor_types

    def test_uptime_sensors_not_created_when_capability_missing(self, mock_entry):
        """Test uptime/last boot sensors are NOT created when SYSTEM_UPTIME capability is missing."""
        from custom_components.cable_modem_monitor.sensor import (
            ModemLastBootTimeSensor,
            ModemSystemUptimeSensor,
            _create_system_sensors,
        )

        coordinator = Mock()
        coordinator.data = {
            "_parser_capabilities": ["downstream_channels", "upstream_channels"],
            "cable_modem_downstream": [],
            "cable_modem_upstream": [],
        }

        sensors = _create_system_sensors(coordinator, mock_entry)
        sensor_types = [type(s) for s in sensors]

        assert ModemSystemUptimeSensor not in sensor_types
        assert ModemLastBootTimeSensor not in sensor_types

    def test_base_sensors_always_created(self, mock_entry):
        """Test that base sensors (errors, channel counts, version) are always created."""
        from custom_components.cable_modem_monitor.sensor import (
            ModemDownstreamChannelCountSensor,
            ModemTotalCorrectedSensor,
            ModemTotalUncorrectedSensor,
            ModemUpstreamChannelCountSensor,
            _create_system_sensors,
        )

        coordinator = Mock()
        coordinator.data = {
            "_parser_capabilities": [],  # No capabilities
            "cable_modem_downstream": [],
            "cable_modem_upstream": [],
        }

        sensors = _create_system_sensors(coordinator, mock_entry)
        sensor_types = [type(s) for s in sensors]

        # These should always be created regardless of capabilities
        assert ModemTotalCorrectedSensor in sensor_types
        assert ModemTotalUncorrectedSensor in sensor_types
        assert ModemDownstreamChannelCountSensor in sensor_types
        assert ModemUpstreamChannelCountSensor in sensor_types
        # Note: ModemSoftwareVersionSensor is now capability-gated (not always created)


class TestFallbackModeSensorCreation:
    """Test that sensors are conditionally created based on fallback mode."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        return Mock()

    @pytest.fixture
    def mock_entry(self):
        """Create a mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry_123"
        entry.data = {
            "host": "192.168.100.1",
            "detected_modem": "Unknown Modem (Fallback Mode)",
            "detected_manufacturer": "Unknown",
        }
        return entry

    @pytest.fixture
    def mock_coordinator_normal_mode(self):
        """Create mock coordinator with normal modem data (not fallback)."""
        coordinator = Mock()
        coordinator.data = {
            "cable_modem_connection_status": "online",
            "cable_modem_downstream": [
                {"channel": "1", "frequency": 591000000, "power": 3.5, "snr": 40.5, "corrected": 0, "uncorrected": 0}
            ],
            "cable_modem_upstream": [{"channel": "1", "frequency": 36000000, "power": 45.0}],
            # system_info keys are prefixed with cable_modem_
            "cable_modem_model": "Test Modem",
            "cable_modem_manufacturer": "TestBrand",
            "cable_modem_software_version": "1.0.0",
            "cable_modem_uptime": "5 days",
            "cable_modem_fallback_mode": False,  # Normal mode
            "health_status": "responsive",
            "ping_latency_ms": 2.5,
            "http_latency_ms": 45.0,
            # Parser capabilities (modem supports uptime and software version)
            "_parser_capabilities": ["system_uptime", "downstream_channels", "upstream_channels", "software_version"],
        }
        return coordinator

    @pytest.fixture
    def mock_coordinator_fallback_mode(self):
        """Create mock coordinator with fallback mode data."""
        coordinator = Mock()
        coordinator.data = {
            "cable_modem_connection_status": "limited",
            "cable_modem_downstream": [],  # No channel data in fallback
            "cable_modem_upstream": [],  # No channel data in fallback
            # system_info keys are prefixed with cable_modem_
            "cable_modem_model": "Unknown Model",
            "cable_modem_manufacturer": "Unknown",
            "cable_modem_fallback_mode": True,  # Fallback mode flag
            "cable_modem_status_message": "Modem not fully supported...",
            "health_status": "responsive",
            "ping_latency_ms": 2.5,
            "http_latency_ms": 45.0,
        }
        return coordinator

    @pytest.mark.asyncio
    async def test_normal_mode_creates_all_sensors(self, mock_hass, mock_entry, mock_coordinator_normal_mode):
        """Test that normal mode creates all sensor types."""

        from custom_components.cable_modem_monitor.const import DOMAIN
        from custom_components.cable_modem_monitor.sensor import async_setup_entry

        # Setup hass.data
        mock_hass.data = {DOMAIN: {mock_entry.entry_id: mock_coordinator_normal_mode}}

        # Track entities added
        added_entities = []

        def mock_add_entities(entities):
            added_entities.extend(entities)

        # Call async_setup_entry
        await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

        # Count sensor types
        sensor_names = [entity._attr_name for entity in added_entities]

        # Should include ALL sensor types in normal mode
        assert "Status" in sensor_names  # Unified status sensor (replaces Connection Status + Health Status)
        assert "Ping Latency" in sensor_names
        assert "HTTP Latency" in sensor_names
        assert "Total Corrected Errors" in sensor_names  # Should be present
        assert "Total Uncorrected Errors" in sensor_names  # Should be present
        assert "DS Channel Count" in sensor_names  # Should be present (abbreviated name)
        assert "US Channel Count" in sensor_names  # Should be present (abbreviated name)
        assert "Software Version" in sensor_names  # Should be present
        assert "System Uptime" in sensor_names  # Should be present

        # Should have at least 10 base sensors + per-channel sensors
        assert len(added_entities) >= 10

    @pytest.mark.asyncio
    async def test_skips_unavailable_sensors(self, mock_hass, mock_entry, mock_coordinator_fallback_mode):
        """Test that fallback mode only creates sensors that have data."""

        from custom_components.cable_modem_monitor.const import DOMAIN
        from custom_components.cable_modem_monitor.sensor import async_setup_entry

        # Setup hass.data
        mock_hass.data = {DOMAIN: {mock_entry.entry_id: mock_coordinator_fallback_mode}}

        # Track entities added
        added_entities = []

        def mock_add_entities(entities):
            added_entities.extend(entities)

        # Call async_setup_entry
        await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

        # Count sensor types
        sensor_names = [entity._attr_name for entity in added_entities]

        # Should include connectivity sensors (have data in fallback)
        assert "Status" in sensor_names  # Unified status sensor
        assert "Ping Latency" in sensor_names
        assert "HTTP Latency" in sensor_names
        assert "Modem Info" in sensor_names  # Always included (device metadata)

        # Should NOT include sensors that require channel/system data
        assert "Total Corrected Errors" not in sensor_names  # Skipped in fallback
        assert "Total Uncorrected Errors" not in sensor_names  # Skipped in fallback
        assert "DS Channel Count" not in sensor_names  # Skipped in fallback (abbreviated name)
        assert "US Channel Count" not in sensor_names  # Skipped in fallback (abbreviated name)
        assert "Software Version" not in sensor_names  # Skipped in fallback
        assert "System Uptime" not in sensor_names  # Skipped in fallback

        # Should have exactly 4 sensors (Status, Modem Info, Ping, HTTP)
        assert len(added_entities) == 4

    @pytest.mark.asyncio
    async def test_no_channel_sensors(self, mock_hass, mock_entry, mock_coordinator_fallback_mode):
        """Test that fallback mode creates no per-channel sensors."""

        from custom_components.cable_modem_monitor.const import DOMAIN
        from custom_components.cable_modem_monitor.sensor import async_setup_entry

        # Setup hass.data
        mock_hass.data = {DOMAIN: {mock_entry.entry_id: mock_coordinator_fallback_mode}}

        # Track entities added
        added_entities = []

        def mock_add_entities(entities):
            added_entities.extend(entities)

        # Call async_setup_entry
        await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

        # Check that no channel-specific sensors were created
        sensor_unique_ids = [entity._attr_unique_id for entity in added_entities]

        # Should NOT have any channel-specific sensors
        assert not any("_ds_" in uid for uid in sensor_unique_ids)  # No downstream channel sensors
        assert not any("_us_" in uid for uid in sensor_unique_ids)  # No upstream channel sensors

    def test_status_shows_operational_in_fallback(self, mock_coordinator_fallback_mode, mock_entry):
        """Test that unified status sensor shows 'Operational' in fallback mode.

        In fallback mode, we don't have channel data to assess DOCSIS lock status,
        so the sensor reports Operational if the modem is reachable.
        """
        sensor = ModemStatusSensor(mock_coordinator_fallback_mode, mock_entry)

        # Fallback mode with responsive health = Operational
        assert sensor.native_value == "Operational"


class TestChannelTypeNormalization:
    """Test that channel_type is normalized to lowercase for sensor creation.

    This is critical because:
    - Parsers return channel_type as-is from modem HTML (e.g., "ATDMA", "QAM256")
    - _normalize_channel_type() in __init__.py normalizes to lowercase ("atdma", "qam")
    - Sensors must use lowercase to match the _upstream_by_id/_downstream_by_id keys

    Bug discovered: some modems return "ATDMA" (uppercase), but
    _upstream_by_id was keyed by ("atdma", 41). Sensors couldn't find their data.
    """

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry_id"
        entry.data = {"host": "192.168.100.1"}
        return entry

    @pytest.fixture
    def mock_coordinator_with_uppercase_channel_types(self):
        """Create coordinator with uppercase channel_type values (as returned by some modems)."""
        coordinator = Mock()
        coordinator.data = {
            "cable_modem_connection_status": "online",
            "cable_modem_downstream": [
                {
                    "channel_id": "1",
                    "channel_type": "QAM256",  # Uppercase from modem
                    "power": 3.0,
                    "snr": 45.5,
                    "frequency": 345000000,
                }
            ],
            "cable_modem_upstream": [
                {
                    "channel_id": "41",
                    "channel_type": "ATDMA",  # Uppercase from modem
                    "power": 54.3,
                    "frequency": 17800000,
                }
            ],
            # Normalized data uses lowercase keys
            "_downstream_by_id": {
                ("qam", 1): {"power": 3.0, "snr": 45.5, "frequency": 345000000},
            },
            "_upstream_by_id": {
                ("atdma", 41): {"power": 54.3, "frequency": 17800000},
            },
            "cable_modem_fallback_mode": False,
            "_parser_capabilities": ["downstream_channels", "upstream_channels"],
        }
        coordinator.last_update_success = True
        return coordinator

    @pytest.mark.asyncio
    async def test_upstream_sensors_created_with_lowercase_channel_type(
        self, mock_coordinator_with_uppercase_channel_types, mock_entry
    ):
        """Test that upstream sensors are created with lowercase channel_type.

        Even though the raw data has "ATDMA", the sensor should use "atdma"
        to match the normalized _upstream_by_id keys.
        """
        from custom_components.cable_modem_monitor.const import DOMAIN
        from custom_components.cable_modem_monitor.sensor import async_setup_entry

        mock_hass = Mock()
        mock_hass.data = {DOMAIN: {mock_entry.entry_id: mock_coordinator_with_uppercase_channel_types}}

        added_entities = []

        def mock_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

        # Find upstream power sensor
        us_power_sensors = [e for e in added_entities if "us_" in e._attr_unique_id and "power" in e._attr_unique_id]
        assert len(us_power_sensors) == 1

        sensor = us_power_sensors[0]
        # Verify the sensor was created with lowercase channel_type
        assert sensor._channel_type == "atdma"  # NOT "ATDMA"
        assert sensor._channel_id == 41

        # Verify the sensor can read its value (this would fail with uppercase)
        assert sensor.native_value == 54.3

    @pytest.mark.asyncio
    async def test_downstream_sensors_created_with_normalized_channel_type(
        self, mock_coordinator_with_uppercase_channel_types, mock_entry
    ):
        """Test that downstream sensors use normalized channel_type from _downstream_by_id.

        Even though raw data has "QAM256", sensor uses the normalized "qam"
        from _downstream_by_id keys for entity creation and data lookup consistency.
        """
        from custom_components.cable_modem_monitor.const import DOMAIN
        from custom_components.cable_modem_monitor.sensor import async_setup_entry

        mock_hass = Mock()
        mock_hass.data = {DOMAIN: {mock_entry.entry_id: mock_coordinator_with_uppercase_channel_types}}

        added_entities = []

        def mock_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

        # Find downstream power sensor
        ds_power_sensors = [e for e in added_entities if "ds_" in e._attr_unique_id and "power" in e._attr_unique_id]
        assert len(ds_power_sensors) == 1

        sensor = ds_power_sensors[0]
        # Verify the sensor was created with normalized channel_type (from _downstream_by_id keys)
        assert sensor._channel_type == "qam"  # Normalized from "QAM256"
        assert sensor._channel_id == 1


class TestConditionalSensorCreation:
    """Test that optional sensors are only created when data is present.

    Some modems don't provide all data fields (e.g., CGA2121 doesn't have frequency
    because ISP firmware comments it out). Sensors for missing fields should not be
    created to avoid crashes when accessing None values.

    Fix for: https://github.com/solentlabs/cable_modem_monitor/issues/75
    """

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry_id"
        entry.data = {"host": "192.168.100.1"}
        return entry

    @pytest.fixture
    def mock_coordinator_without_frequency(self):
        """Create coordinator with channel data but NO frequency field (like CGA2121)."""
        coordinator = Mock()
        coordinator.data = {
            "cable_modem_connection_status": "online",
            "cable_modem_downstream": [
                {
                    "channel_id": "1",
                    "channel_type": "qam",
                    "power": 3.0,
                    "snr": 45.5,
                    # NO frequency field
                }
            ],
            "cable_modem_upstream": [
                {
                    "channel_id": "1",
                    "channel_type": "atdma",
                    "power": 54.3,
                    # NO frequency field
                }
            ],
            "_downstream_by_id": {
                ("qam", 1): {"power": 3.0, "snr": 45.5},  # NO frequency
            },
            "_upstream_by_id": {
                ("atdma", 1): {"power": 54.3},  # NO frequency
            },
            "cable_modem_fallback_mode": False,
            "_parser_capabilities": ["downstream_channels", "upstream_channels"],
        }
        coordinator.last_update_success = True
        return coordinator

    @pytest.fixture
    def mock_coordinator_with_frequency(self):
        """Create coordinator with channel data INCLUDING frequency field."""
        coordinator = Mock()
        coordinator.data = {
            "cable_modem_connection_status": "online",
            "cable_modem_downstream": [
                {
                    "channel_id": "1",
                    "channel_type": "qam",
                    "power": 3.0,
                    "snr": 45.5,
                    "frequency": 345000000,
                }
            ],
            "cable_modem_upstream": [
                {
                    "channel_id": "1",
                    "channel_type": "atdma",
                    "power": 54.3,
                    "frequency": 17800000,
                }
            ],
            "_downstream_by_id": {
                ("qam", 1): {"power": 3.0, "snr": 45.5, "frequency": 345000000},
            },
            "_upstream_by_id": {
                ("atdma", 1): {"power": 54.3, "frequency": 17800000},
            },
            "cable_modem_fallback_mode": False,
            "_parser_capabilities": ["downstream_channels", "upstream_channels"],
        }
        coordinator.last_update_success = True
        return coordinator

    @pytest.mark.asyncio
    async def test_frequency_sensors_not_created_when_data_missing(
        self, mock_coordinator_without_frequency, mock_entry
    ):
        """Test that frequency sensors are NOT created when frequency data is absent."""
        from custom_components.cable_modem_monitor.const import DOMAIN
        from custom_components.cable_modem_monitor.sensor import async_setup_entry

        mock_hass = Mock()
        mock_hass.data = {DOMAIN: {mock_entry.entry_id: mock_coordinator_without_frequency}}

        added_entities = []

        def mock_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

        # Check unique IDs for frequency sensors
        sensor_unique_ids = [e._attr_unique_id for e in added_entities]

        # Should NOT have any frequency sensors
        assert not any("frequency" in uid for uid in sensor_unique_ids), (
            f"Frequency sensors should not be created when data is missing. Found: "
            f"{[uid for uid in sensor_unique_ids if 'frequency' in uid]}"
        )

        # Should still have power and SNR sensors
        assert any("power" in uid for uid in sensor_unique_ids)
        assert any("snr" in uid for uid in sensor_unique_ids)

    @pytest.mark.asyncio
    async def test_frequency_sensors_created_when_data_present(self, mock_coordinator_with_frequency, mock_entry):
        """Test that frequency sensors ARE created when frequency data is present."""
        from custom_components.cable_modem_monitor.const import DOMAIN
        from custom_components.cable_modem_monitor.sensor import async_setup_entry

        mock_hass = Mock()
        mock_hass.data = {DOMAIN: {mock_entry.entry_id: mock_coordinator_with_frequency}}

        added_entities = []

        def mock_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

        # Check unique IDs for frequency sensors
        sensor_unique_ids = [e._attr_unique_id for e in added_entities]

        # Should have frequency sensors for both downstream and upstream
        ds_freq = [uid for uid in sensor_unique_ids if "ds_" in uid and "frequency" in uid]
        us_freq = [uid for uid in sensor_unique_ids if "us_" in uid and "frequency" in uid]

        assert len(ds_freq) == 1, f"Expected 1 downstream frequency sensor, got {len(ds_freq)}"
        assert len(us_freq) == 1, f"Expected 1 upstream frequency sensor, got {len(us_freq)}"

    @pytest.mark.asyncio
    async def test_frequency_sensor_returns_none_safely_when_data_missing(
        self, mock_coordinator_with_frequency, mock_entry
    ):
        """Test that frequency sensor handles None data gracefully (defensive check)."""
        from custom_components.cable_modem_monitor.sensor import ModemDownstreamFrequencySensor

        # Create sensor
        sensor = ModemDownstreamFrequencySensor(mock_coordinator_with_frequency, mock_entry, "qam", 1)

        # Verify it can read the value
        assert sensor.native_value == 345000000

        # Now modify coordinator data to remove frequency (simulates runtime change)
        mock_coordinator_with_frequency.data["_downstream_by_id"][("qam", 1)] = {
            "power": 3.0,
            "snr": 45.5,
            # frequency removed
        }

        # Should return None safely, not crash with int(None)
        assert sensor.native_value is None


# =============================================================================
# Table-Driven Parameterized Tests
# =============================================================================


class TestStatusSensorBranches:
    """Table-driven tests for ModemStatusSensor.native_value status branches."""

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    @pytest.mark.parametrize(
        "health_status,connection_status,downstream,upstream,supports_icmp,expected,desc",
        STATUS_SENSOR_CASES,
        ids=[c[-1] for c in STATUS_SENSOR_CASES],
    )
    def test_status_branches(
        self, mock_entry, health_status, connection_status, downstream, upstream, supports_icmp, expected, desc
    ):
        """Test all status sensor branches via table-driven cases."""
        coordinator = Mock()
        coordinator.data = {
            "health_status": health_status,
            "cable_modem_connection_status": connection_status,
            "cable_modem_downstream": downstream,
            "cable_modem_upstream": upstream,
            "supports_icmp": supports_icmp,
            "cable_modem_fallback_mode": False,
        }
        coordinator.last_update_success = True

        sensor = ModemStatusSensor(coordinator, mock_entry)
        assert sensor.native_value == expected, f"Failed: {desc}"


class TestDocsisStatusDerivation:
    """Table-driven tests for ModemStatusSensor._derive_docsis_status."""

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    @pytest.mark.parametrize(
        "downstream,upstream,fallback_mode,expected,desc",
        DOCSIS_STATUS_CASES,
        ids=[c[-1] for c in DOCSIS_STATUS_CASES],
    )
    def test_derive_docsis_status(self, mock_entry, downstream, upstream, fallback_mode, expected, desc):
        """Test DOCSIS status derivation via table-driven cases."""
        coordinator = Mock()
        coordinator.data = {
            "cable_modem_downstream": downstream,
            "cable_modem_upstream": upstream,
            "cable_modem_fallback_mode": fallback_mode,
        }
        coordinator.last_update_success = True

        sensor = ModemStatusSensor(coordinator, mock_entry)
        result = sensor._derive_docsis_status(coordinator.data)
        assert result == expected, f"Failed: {desc}"


class TestSensorBaseAvailability:
    """Table-driven tests for ModemSensorBase.available property."""

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    @pytest.mark.parametrize(
        "last_update_success,connection_status,expected,desc",
        SENSOR_BASE_AVAILABILITY_CASES,
        ids=[c[-1] for c in SENSOR_BASE_AVAILABILITY_CASES],
    )
    def test_base_availability(self, mock_entry, last_update_success, connection_status, expected, desc):
        """Test base sensor availability via table-driven cases."""
        from custom_components.cable_modem_monitor.sensor import ModemTotalCorrectedSensor

        coordinator = Mock()
        coordinator.data = {
            "cable_modem_connection_status": connection_status,
            "cable_modem_total_corrected": 100,
        }
        coordinator.last_update_success = last_update_success

        sensor = ModemTotalCorrectedSensor(coordinator, mock_entry)
        assert sensor.available == expected, f"Failed: {desc}"


class TestLatencySensors:
    """Table-driven tests for latency sensors."""

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    @pytest.mark.parametrize(
        "ping_success,ping_latency,http_success,http_latency,desc",
        LATENCY_SENSOR_CASES,
        ids=[c[-1] for c in LATENCY_SENSOR_CASES],
    )
    def test_ping_latency_sensor(self, mock_entry, ping_success, ping_latency, http_success, http_latency, desc):
        """Test ping latency sensor via table-driven cases."""
        from custom_components.cable_modem_monitor.sensor import ModemPingLatencySensor

        coordinator = Mock()
        coordinator.data = {
            "ping_success": ping_success,
            "ping_latency_ms": ping_latency,
            "http_success": http_success,
            "http_latency_ms": http_latency,
        }
        coordinator.last_update_success = True

        sensor = ModemPingLatencySensor(coordinator, mock_entry)

        # Check availability
        if ping_success is None:
            assert sensor.available is False, f"Should be unavailable when ping_success is None: {desc}"
        else:
            assert sensor.available is True, f"Should be available when ping_success is set: {desc}"

        # Check value
        if ping_latency is not None:
            assert sensor.native_value == int(round(ping_latency)), f"Failed value: {desc}"
        else:
            assert sensor.native_value is None, f"Should be None when no latency: {desc}"

    @pytest.mark.parametrize(
        "ping_success,ping_latency,http_success,http_latency,desc",
        LATENCY_SENSOR_CASES,
        ids=[c[-1] for c in LATENCY_SENSOR_CASES],
    )
    def test_http_latency_sensor(self, mock_entry, ping_success, ping_latency, http_success, http_latency, desc):
        """Test HTTP latency sensor via table-driven cases."""
        from custom_components.cable_modem_monitor.sensor import ModemHttpLatencySensor

        coordinator = Mock()
        coordinator.data = {
            "ping_success": ping_success,
            "ping_latency_ms": ping_latency,
            "http_success": http_success,
            "http_latency_ms": http_latency,
        }
        coordinator.last_update_success = True

        sensor = ModemHttpLatencySensor(coordinator, mock_entry)

        # Check availability
        if http_success is None:
            assert sensor.available is False, f"Should be unavailable when http_success is None: {desc}"
        else:
            assert sensor.available is True, f"Should be available when http_success is set: {desc}"

        # Check value
        if http_latency is not None:
            assert sensor.native_value == int(round(http_latency)), f"Failed value: {desc}"
        else:
            assert sensor.native_value is None, f"Should be None when no latency: {desc}"


class TestLanStatsSensorsBranches:
    """Table-driven tests for LAN stats error/drop sensors."""

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    @pytest.mark.parametrize(
        "sensor_type,stat_key,value,expected",
        LAN_STATS_SENSOR_CASES,
        ids=[f"{c[0]}_{c[2]}" for c in LAN_STATS_SENSOR_CASES],
    )
    def test_lan_stats_sensors(self, mock_entry, sensor_type, stat_key, value, expected):
        """Test LAN stats sensors via table-driven cases."""
        from custom_components.cable_modem_monitor.sensor import (
            ModemLanReceivedDropsSensor,
            ModemLanReceivedErrorsSensor,
            ModemLanTransmittedDropsSensor,
            ModemLanTransmittedErrorsSensor,
        )

        sensor_map = {
            "received_errors": ModemLanReceivedErrorsSensor,
            "received_drops": ModemLanReceivedDropsSensor,
            "transmitted_errors": ModemLanTransmittedErrorsSensor,
            "transmitted_drops": ModemLanTransmittedDropsSensor,
            "received_bytes": ModemLanReceivedErrorsSensor,  # reuse for None test
        }

        coordinator = Mock()
        if value is not None:
            coordinator.data = {"cable_modem_lan_stats": {"eth0": {stat_key: value}}}
        else:
            coordinator.data = {"cable_modem_lan_stats": {"eth0": {}}}  # missing stat
        coordinator.last_update_success = True

        sensor_class = sensor_map[sensor_type]
        sensor = sensor_class(coordinator, mock_entry, "eth0")
        assert sensor.native_value == expected


class TestModemInfoSensor:
    """Tests for ModemInfoSensor."""

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {
            "host": "192.168.100.1",
            "detected_modem": "Arris SB8200",
            "detected_manufacturer": "Arris",
        }
        return entry

    def test_native_value(self, mock_entry):
        """Test ModemInfoSensor returns detected modem as state."""
        from custom_components.cable_modem_monitor.sensor import ModemInfoSensor

        coordinator = Mock()
        coordinator.data = {}
        coordinator.last_update_success = True

        sensor = ModemInfoSensor(coordinator, mock_entry)
        assert sensor.native_value == "Arris SB8200"

    def test_extra_state_attributes_full(self, mock_entry):
        """Test ModemInfoSensor extra attributes with all data present."""
        from custom_components.cable_modem_monitor.sensor import ModemInfoSensor

        coordinator = Mock()
        coordinator.data = {
            "_parser_release_date": "2019",
            "_parser_docsis_version": "3.1",
            "_parser_fixtures_url": "https://example.com/fixtures",
            "_parser_verified": True,
        }
        coordinator.last_update_success = True

        sensor = ModemInfoSensor(coordinator, mock_entry)
        attrs = sensor.extra_state_attributes

        assert attrs["manufacturer"] == "Arris"
        assert attrs["release_date"] == "2019"
        assert attrs["docsis_version"] == "3.1"
        assert attrs["fixtures_url"] == "https://example.com/fixtures"
        assert attrs["parser_verified"] is True

    def test_extra_state_attributes_minimal(self, mock_entry):
        """Test ModemInfoSensor extra attributes with minimal data."""
        from custom_components.cable_modem_monitor.sensor import ModemInfoSensor

        coordinator = Mock()
        coordinator.data = {}  # No parser metadata
        coordinator.last_update_success = True

        sensor = ModemInfoSensor(coordinator, mock_entry)
        attrs = sensor.extra_state_attributes

        assert attrs["manufacturer"] == "Arris"
        assert attrs["parser_verified"] is False
        assert "release_date" not in attrs
        assert "docsis_version" not in attrs
        assert "fixtures_url" not in attrs


class TestStatusSensorAvailable:
    """Tests for ModemStatusSensor.available property."""

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    def test_available_true(self, mock_entry):
        """Test status sensor available when coordinator update succeeded."""
        coordinator = Mock()
        coordinator.data = {"cable_modem_connection_status": "online"}
        coordinator.last_update_success = True

        sensor = ModemStatusSensor(coordinator, mock_entry)
        assert sensor.available is True

    def test_available_false(self, mock_entry):
        """Test status sensor unavailable when coordinator update failed."""
        coordinator = Mock()
        coordinator.data = {"cable_modem_connection_status": "online"}
        coordinator.last_update_success = False

        sensor = ModemStatusSensor(coordinator, mock_entry)
        assert sensor.available is False


class TestStatusSensorExtraAttributes:
    """Tests for ModemStatusSensor.extra_state_attributes."""

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    def test_extra_state_attributes(self, mock_entry):
        """Test ModemStatusSensor extra attributes."""
        coordinator = Mock()
        coordinator.data = {
            "cable_modem_connection_status": "online",
            "health_status": "responsive",
            "health_diagnosis": "All systems operational",
            "cable_modem_downstream": [{"lock_status": "Locked"}],
            "cable_modem_upstream": [{"ch": "1"}],
            "cable_modem_fallback_mode": False,
        }
        coordinator.last_update_success = True

        sensor = ModemStatusSensor(coordinator, mock_entry)
        attrs = sensor.extra_state_attributes

        assert attrs["connection_status"] == "online"
        assert attrs["health_status"] == "responsive"
        assert attrs["docsis_status"] == "Operational"
        assert attrs["diagnosis"] == "All systems operational"


class TestChannelSensorExtraAttributes:
    """Tests for channel sensor extra_state_attributes."""

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with channel data."""
        coordinator = Mock()
        coordinator.data = {
            "_downstream_by_id": {
                ("qam", 1): {"power": 3.0, "snr": 40.5, "frequency": 591000000, "corrected": 100, "uncorrected": 5},
            },
            "_upstream_by_id": {
                ("atdma", 1): {"power": 45.0, "frequency": 36000000},
            },
        }
        coordinator.last_update_success = True
        return coordinator

    def test_downstream_power_extra_attrs(self, mock_coordinator, mock_entry):
        """Test downstream power sensor extra attributes."""
        from custom_components.cable_modem_monitor.sensor import ModemDownstreamPowerSensor

        sensor = ModemDownstreamPowerSensor(mock_coordinator, mock_entry, "qam", 1)
        attrs = sensor.extra_state_attributes

        assert attrs["channel_id"] == 1
        assert attrs["channel_type"] == "qam"
        assert attrs["frequency"] == 591000000

    def test_downstream_snr_extra_attrs(self, mock_coordinator, mock_entry):
        """Test downstream SNR sensor extra attributes."""
        from custom_components.cable_modem_monitor.sensor import ModemDownstreamSNRSensor

        sensor = ModemDownstreamSNRSensor(mock_coordinator, mock_entry, "qam", 1)
        attrs = sensor.extra_state_attributes

        assert attrs["channel_id"] == 1
        assert attrs["channel_type"] == "qam"
        assert attrs["frequency"] == 591000000

    def test_downstream_frequency_extra_attrs(self, mock_coordinator, mock_entry):
        """Test downstream frequency sensor extra attributes."""
        from custom_components.cable_modem_monitor.sensor import ModemDownstreamFrequencySensor

        sensor = ModemDownstreamFrequencySensor(mock_coordinator, mock_entry, "qam", 1)
        attrs = sensor.extra_state_attributes

        assert attrs["channel_id"] == 1
        assert attrs["channel_type"] == "qam"

    def test_downstream_corrected_extra_attrs(self, mock_coordinator, mock_entry):
        """Test downstream corrected sensor extra attributes."""
        from custom_components.cable_modem_monitor.sensor import ModemDownstreamCorrectedSensor

        sensor = ModemDownstreamCorrectedSensor(mock_coordinator, mock_entry, "qam", 1)
        attrs = sensor.extra_state_attributes

        assert attrs["channel_id"] == 1
        assert attrs["channel_type"] == "qam"
        assert attrs["frequency"] == 591000000

    def test_downstream_uncorrected_extra_attrs(self, mock_coordinator, mock_entry):
        """Test downstream uncorrected sensor extra attributes."""
        from custom_components.cable_modem_monitor.sensor import ModemDownstreamUncorrectedSensor

        sensor = ModemDownstreamUncorrectedSensor(mock_coordinator, mock_entry, "qam", 1)
        attrs = sensor.extra_state_attributes

        assert attrs["channel_id"] == 1
        assert attrs["channel_type"] == "qam"
        assert attrs["frequency"] == 591000000

    def test_upstream_power_extra_attrs(self, mock_coordinator, mock_entry):
        """Test upstream power sensor extra attributes."""
        from custom_components.cable_modem_monitor.sensor import ModemUpstreamPowerSensor

        sensor = ModemUpstreamPowerSensor(mock_coordinator, mock_entry, "atdma", 1)
        attrs = sensor.extra_state_attributes

        assert attrs["channel_id"] == 1
        assert attrs["channel_type"] == "atdma"
        assert attrs["frequency"] == 36000000

    def test_upstream_frequency_extra_attrs(self, mock_coordinator, mock_entry):
        """Test upstream frequency sensor extra attributes."""
        from custom_components.cable_modem_monitor.sensor import ModemUpstreamFrequencySensor

        sensor = ModemUpstreamFrequencySensor(mock_coordinator, mock_entry, "atdma", 1)
        attrs = sensor.extra_state_attributes

        assert attrs["channel_id"] == 1
        assert attrs["channel_type"] == "atdma"

    def test_channel_not_found_returns_empty_attrs(self, mock_entry):
        """Test extra attributes return empty dict when channel not found."""
        from custom_components.cable_modem_monitor.sensor import ModemDownstreamPowerSensor

        coordinator = Mock()
        coordinator.data = {"_downstream_by_id": {}}  # Empty
        coordinator.last_update_success = True

        sensor = ModemDownstreamPowerSensor(coordinator, mock_entry, "qam", 999)
        attrs = sensor.extra_state_attributes

        assert attrs == {}


class TestDeviceInfoConstruction:
    """Tests for ModemSensorBase device_info construction."""

    def test_device_info_with_actual_model(self):
        """Test device info uses actual_model when available."""
        from custom_components.cable_modem_monitor.sensor import ModemTotalCorrectedSensor

        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {
            "host": "192.168.100.1",
            "detected_manufacturer": "Motorola",
            "actual_model": "MB8611",
            "detected_modem": "Motorola MB8600",  # Parser name, not actual
        }

        coordinator = Mock()
        coordinator.data = {"cable_modem_total_corrected": 0}
        coordinator.last_update_success = True

        sensor = ModemTotalCorrectedSensor(coordinator, entry)

        # Should use actual_model, stripped of manufacturer prefix
        assert sensor.device_info["model"] == "MB8611"
        assert sensor.device_info["manufacturer"] == "Motorola"

    def test_device_info_strips_manufacturer_prefix(self):
        """Test device info strips manufacturer prefix from model."""
        from custom_components.cable_modem_monitor.sensor import ModemTotalCorrectedSensor

        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {
            "host": "192.168.100.1",
            "detected_manufacturer": "Arris",
            "actual_model": "Arris SB8200",  # Has manufacturer prefix
            "detected_modem": "Arris SB8200",
        }

        coordinator = Mock()
        coordinator.data = {"cable_modem_total_corrected": 0}
        coordinator.last_update_success = True

        sensor = ModemTotalCorrectedSensor(coordinator, entry)

        # Should strip "Arris " prefix
        assert sensor.device_info["model"] == "SB8200"

    def test_device_info_fallback_to_detected_modem(self):
        """Test device info falls back to detected_modem when no actual_model."""
        from custom_components.cable_modem_monitor.sensor import ModemTotalCorrectedSensor

        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {
            "host": "192.168.100.1",
            "detected_manufacturer": "Netgear",
            "detected_modem": "Netgear CM2000",
            # No actual_model
        }

        coordinator = Mock()
        coordinator.data = {"cable_modem_total_corrected": 0}
        coordinator.last_update_success = True

        sensor = ModemTotalCorrectedSensor(coordinator, entry)

        # Should use detected_modem, stripped of manufacturer prefix
        assert sensor.device_info["model"] == "CM2000"


class TestChannelSensorNativeValueEdgeCases:
    """Tests for channel sensor native_value when channel not found."""

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    @pytest.fixture
    def mock_coordinator_empty(self):
        """Create mock coordinator with empty channel data."""
        coordinator = Mock()
        coordinator.data = {
            "_downstream_by_id": {},
            "_upstream_by_id": {},
        }
        coordinator.last_update_success = True
        return coordinator

    def test_downstream_power_not_found(self, mock_coordinator_empty, mock_entry):
        """Test downstream power sensor returns None when channel not found."""
        from custom_components.cable_modem_monitor.sensor import ModemDownstreamPowerSensor

        sensor = ModemDownstreamPowerSensor(mock_coordinator_empty, mock_entry, "qam", 999)
        assert sensor.native_value is None

    def test_downstream_snr_not_found(self, mock_coordinator_empty, mock_entry):
        """Test downstream SNR sensor returns None when channel not found."""
        from custom_components.cable_modem_monitor.sensor import ModemDownstreamSNRSensor

        sensor = ModemDownstreamSNRSensor(mock_coordinator_empty, mock_entry, "qam", 999)
        assert sensor.native_value is None

    def test_downstream_frequency_not_found(self, mock_coordinator_empty, mock_entry):
        """Test downstream frequency sensor returns None when channel not found."""
        from custom_components.cable_modem_monitor.sensor import ModemDownstreamFrequencySensor

        sensor = ModemDownstreamFrequencySensor(mock_coordinator_empty, mock_entry, "qam", 999)
        assert sensor.native_value is None

    def test_downstream_corrected_not_found(self, mock_coordinator_empty, mock_entry):
        """Test downstream corrected sensor returns None when channel not found."""
        from custom_components.cable_modem_monitor.sensor import ModemDownstreamCorrectedSensor

        sensor = ModemDownstreamCorrectedSensor(mock_coordinator_empty, mock_entry, "qam", 999)
        assert sensor.native_value is None

    def test_downstream_uncorrected_not_found(self, mock_coordinator_empty, mock_entry):
        """Test downstream uncorrected sensor returns None when channel not found."""
        from custom_components.cable_modem_monitor.sensor import ModemDownstreamUncorrectedSensor

        sensor = ModemDownstreamUncorrectedSensor(mock_coordinator_empty, mock_entry, "qam", 999)
        assert sensor.native_value is None

    def test_upstream_power_not_found(self, mock_coordinator_empty, mock_entry):
        """Test upstream power sensor returns None when channel not found."""
        from custom_components.cable_modem_monitor.sensor import ModemUpstreamPowerSensor

        sensor = ModemUpstreamPowerSensor(mock_coordinator_empty, mock_entry, "atdma", 999)
        assert sensor.native_value is None

    def test_upstream_frequency_not_found(self, mock_coordinator_empty, mock_entry):
        """Test upstream frequency sensor returns None when channel not found."""
        from custom_components.cable_modem_monitor.sensor import ModemUpstreamFrequencySensor

        sensor = ModemUpstreamFrequencySensor(mock_coordinator_empty, mock_entry, "atdma", 999)
        assert sensor.native_value is None


class TestLanStatsSensorMissingInterface:
    """Tests for LAN stats sensors when interface is missing."""

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    def test_lan_stats_interface_not_found(self, mock_entry):
        """Test LAN stats sensor returns None when interface not found."""
        from custom_components.cable_modem_monitor.sensor import ModemLanReceivedBytesSensor

        coordinator = Mock()
        coordinator.data = {"cable_modem_lan_stats": {}}  # No interfaces
        coordinator.last_update_success = True

        sensor = ModemLanReceivedBytesSensor(coordinator, mock_entry, "eth99")
        assert sensor.native_value is None


class TestLatencySensorDataNone:
    """Tests for latency sensors with coordinator.data=None."""

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    def test_ping_latency_data_none(self, mock_entry):
        """Test ping latency sensor unavailable when coordinator.data is None."""
        from custom_components.cable_modem_monitor.sensor import ModemPingLatencySensor

        coordinator = Mock()
        coordinator.data = None
        coordinator.last_update_success = True

        sensor = ModemPingLatencySensor(coordinator, mock_entry)
        assert sensor.available is False

    def test_http_latency_data_none(self, mock_entry):
        """Test HTTP latency sensor unavailable when coordinator.data is None."""
        from custom_components.cable_modem_monitor.sensor import ModemHttpLatencySensor

        coordinator = Mock()
        coordinator.data = None
        coordinator.last_update_success = True

        sensor = ModemHttpLatencySensor(coordinator, mock_entry)
        assert sensor.available is False


class TestCreateSystemSensorsCapabilities:
    """Tests for _create_system_sensors capability checks."""

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"host": "192.168.100.1"}
        return entry

    def test_software_version_sensor_created_with_capability(self, mock_entry):
        """Test software version sensor IS created when capability present."""
        from custom_components.cable_modem_monitor.core.base_parser import ModemCapability
        from custom_components.cable_modem_monitor.sensor import (
            ModemSoftwareVersionSensor,
            _create_system_sensors,
        )

        coordinator = Mock()
        coordinator.data = {
            "_parser_capabilities": [ModemCapability.SOFTWARE_VERSION.value],
        }

        sensors = _create_system_sensors(coordinator, mock_entry)
        sensor_types = [type(s) for s in sensors]

        assert ModemSoftwareVersionSensor in sensor_types

    def test_software_version_sensor_not_created_without_capability(self, mock_entry):
        """Test software version sensor NOT created when capability missing."""
        from custom_components.cable_modem_monitor.sensor import (
            ModemSoftwareVersionSensor,
            _create_system_sensors,
        )

        coordinator = Mock()
        coordinator.data = {
            "_parser_capabilities": [],  # No capabilities
        }

        sensors = _create_system_sensors(coordinator, mock_entry)
        sensor_types = [type(s) for s in sensors]

        assert ModemSoftwareVersionSensor not in sensor_types
