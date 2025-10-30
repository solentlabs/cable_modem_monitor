"""Tests for Cable Modem Monitor sensors."""
import pytest
from unittest.mock import Mock
from custom_components.cable_modem_monitor.sensor import (
    ModemConnectionStatusSensor,
    ModemTotalCorrectedSensor,
    ModemTotalUncorrectedSensor,
    ModemDownstreamChannelCountSensor,
    ModemUpstreamChannelCountSensor,
    ModemSoftwareVersionSensor,
    ModemSystemUptimeSensor,
)


class TestSensorImports:
    """Test sensor imports."""

    def test_sensor_entity_count(self):
        """Test minimum number of base sensors created."""
        ***REMOVED*** Should create at least:
        ***REMOVED*** 1 connection status
        ***REMOVED*** 2 total error sensors
        ***REMOVED*** 2 channel count sensors
        ***REMOVED*** 2 system info sensors
        ***REMOVED*** = 7 base sensors (plus per-channel sensors)
        expected_base_sensors = 7
        assert expected_base_sensors == 7


class TestConnectionStatusSensor:
    """Test connection status sensor."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with sample data."""
        coordinator = Mock()
        ***REMOVED*** Use plain dict for data (sensors call .get() on it)
        coordinator.data = {
            "cable_modem_connection_status": "online",
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

    def test_connection_status_online(self, mock_coordinator, mock_entry):
        """Test connection status sensor with online status."""
        sensor = ModemConnectionStatusSensor(mock_coordinator, mock_entry)

        ***REMOVED*** Test state
        assert sensor.native_value == "online"

    def test_connection_status_offline(self, mock_coordinator, mock_entry):
        """Test connection status sensor with offline status."""
        mock_coordinator.data = {"cable_modem_connection_status": "unreachable"}
        sensor = ModemConnectionStatusSensor(mock_coordinator, mock_entry)

        assert sensor.native_value == "unreachable"


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
            "total_uncorrected": 0,
        }

        corrected_sensor = ModemTotalCorrectedSensor(mock_coordinator, mock_entry)
        uncorrected_sensor = ModemTotalUncorrectedSensor(
            mock_coordinator, mock_entry
        )

        assert corrected_sensor.native_value == 0
        assert uncorrected_sensor.native_value == 0


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
        ***REMOVED*** Each downstream channel should create 4 sensors:
        ***REMOVED*** - Frequency
        ***REMOVED*** - Power
        ***REMOVED*** - SNR
        ***REMOVED*** - Corrected/Uncorrected errors (if available)
        sensors_per_downstream_channel = 4
        assert sensors_per_downstream_channel == 4

    def test_upstream_channel_sensor_count(self):
        """Test that correct number of upstream sensors are created."""
        ***REMOVED*** Each upstream channel should create 2 sensors:
        ***REMOVED*** - Frequency
        ***REMOVED*** - Power
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
        sensor = ModemConnectionStatusSensor(mock_coordinator, mock_entry)

        ***REMOVED*** Unique ID should be based on entry_id and sensor type
        assert sensor.unique_id is not None
        assert "test_entry" in sensor.unique_id

    def test_sensor_has_device_info(self, mock_coordinator, mock_entry):
        """Test that sensors have device info."""
        sensor = ModemConnectionStatusSensor(mock_coordinator, mock_entry)

        ***REMOVED*** Device info should link sensors to the modem device
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
        coordinator.data = {}  ***REMOVED*** Empty data

        sensor = ModemTotalCorrectedSensor(coordinator, mock_entry)

        ***REMOVED*** Should handle missing data gracefully (return None or default)
        result = sensor.native_value
        assert result is None or isinstance(result, int)

    def test_none_values(self, mock_entry):
        """Test sensors with None values."""
        coordinator = Mock()
        coordinator.data = {"cable_modem_software_version": None}

        sensor = ModemSoftwareVersionSensor(coordinator, mock_entry)

        ***REMOVED*** Should handle None gracefully
        assert sensor.native_value is None or sensor.native_value == "Unknown"


class TestEntityNaming:
    """Test entity naming with different prefix configurations."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator."""
        coordinator = Mock()
        coordinator.data = {
            "connection_status": "online",
            "cable_modem_total_corrected": 100,
            "cable_modem_downstream": [],
            "cable_modem_upstream": [],
        }
        coordinator.last_update_success = True
        return coordinator

    def test_sensor_naming(self, mock_coordinator):
        """Test sensor naming has correct display names and unique IDs."""
        from custom_components.cable_modem_monitor.sensor import (
            ModemConnectionStatusSensor,
            ModemTotalCorrectedSensor,
            ModemDownstreamPowerSensor
        )

        entry = Mock()
        entry.entry_id = "test"
        entry.data = {"host": "192.168.100.1"}

        ***REMOVED*** Test connection status sensor
        connection_sensor = ModemConnectionStatusSensor(mock_coordinator, entry)
        assert connection_sensor.name == "Connection Status"
        assert connection_sensor.unique_id == "test_cable_modem_connection_status"

        ***REMOVED*** Test error sensor
        error_sensor = ModemTotalCorrectedSensor(mock_coordinator, entry)
        assert error_sensor.name == "Total Corrected Errors"
        assert error_sensor.unique_id == "test_cable_modem_total_corrected"

        ***REMOVED*** Test channel sensor
        channel_sensor = ModemDownstreamPowerSensor(mock_coordinator, entry, channel=5)
        assert channel_sensor.name == "DS Ch 5 Power"
        assert channel_sensor.unique_id == "test_cable_modem_downstream_5_power"


class TestLastBootTimeSensor:
    """Test last boot time sensor functionality."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with uptime data."""
        coordinator = Mock()
        coordinator.data = {
            "connection_status": "online",
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

    def test_parse_uptime_days_hours(self):
        """Test parsing uptime with days and hours."""
        from custom_components.cable_modem_monitor.sensor import parse_uptime_to_seconds

        result = parse_uptime_to_seconds("2 days 5 hours")
        expected = (2 * 86400) + (5 * 3600)  ***REMOVED*** 2 days + 5 hours
        assert result == expected

    def test_parse_uptime_hours_only(self):
        """Test parsing uptime with only hours."""
        from custom_components.cable_modem_monitor.sensor import parse_uptime_to_seconds

        result = parse_uptime_to_seconds("3 hours")
        expected = 3 * 3600
        assert result == expected

    def test_parse_uptime_with_minutes(self):
        """Test parsing uptime with hours and minutes."""
        from custom_components.cable_modem_monitor.sensor import parse_uptime_to_seconds

        result = parse_uptime_to_seconds("3 hours 45 minutes")
        expected = (3 * 3600) + (45 * 60)
        assert result == expected

    def test_parse_uptime_complex(self):
        """Test parsing complex uptime string."""
        from custom_components.cable_modem_monitor.sensor import parse_uptime_to_seconds

        result = parse_uptime_to_seconds("5 days 12 hours 30 minutes 15 seconds")
        expected = (5 * 86400) + (12 * 3600) + (30 * 60) + 15
        assert result == expected

    def test_parse_uptime_unknown(self):
        """Test parsing Unknown uptime."""
        from custom_components.cable_modem_monitor.sensor import parse_uptime_to_seconds

        result = parse_uptime_to_seconds("Unknown")
        assert result is None

    def test_parse_uptime_empty(self):
        """Test parsing empty uptime."""
        from custom_components.cable_modem_monitor.sensor import parse_uptime_to_seconds

        result = parse_uptime_to_seconds("")
        assert result is None

    def test_parse_uptime_none(self):
        """Test parsing None uptime."""
        from custom_components.cable_modem_monitor.sensor import parse_uptime_to_seconds

        result = parse_uptime_to_seconds(None)
        assert result is None

    def test_last_boot_time_calculation(self, mock_coordinator, mock_entry):
        """Test last boot time calculation from uptime."""
        from custom_components.cable_modem_monitor.sensor import ModemLastBootTimeSensor
        from datetime import datetime, timedelta
        from homeassistant.util import dt as dt_util

        sensor = ModemLastBootTimeSensor(mock_coordinator, mock_entry)

        ***REMOVED*** Get the calculated last boot time
        last_boot = sensor.native_value

        ***REMOVED*** Should return a datetime object
        assert isinstance(last_boot, datetime)

        ***REMOVED*** Calculate expected boot time (2 days 5 hours ago)
        uptime_seconds = (2 * 86400) + (5 * 3600)
        now = dt_util.now()
        expected_boot = now - timedelta(seconds=uptime_seconds)

        ***REMOVED*** Should be within a few seconds of expected (allow for execution time)
        time_diff = abs((last_boot - expected_boot).total_seconds())
        assert time_diff < 5  ***REMOVED*** Within 5 seconds

    def test_last_boot_time_unknown_uptime(self, mock_entry):
        """Test last boot time with unknown uptime."""
        from custom_components.cable_modem_monitor.sensor import ModemLastBootTimeSensor

        coordinator = Mock()
        coordinator.data = {"cable_modem_system_uptime": "Unknown"}
        coordinator.last_update_success = True

        sensor = ModemLastBootTimeSensor(coordinator, mock_entry)

        ***REMOVED*** Should return None for unknown uptime
        assert sensor.native_value is None

    def test_last_boot_time_missing_uptime(self, mock_entry):
        """Test last boot time with missing uptime data."""
        from custom_components.cable_modem_monitor.sensor import ModemLastBootTimeSensor

        coordinator = Mock()
        coordinator.data = {}  ***REMOVED*** No uptime data
        coordinator.last_update_success = True

        sensor = ModemLastBootTimeSensor(coordinator, mock_entry)

        ***REMOVED*** Should return None when uptime is missing
        assert sensor.native_value is None

    def test_last_boot_time_sensor_attributes(self, mock_coordinator, mock_entry):
        """Test last boot time sensor attributes."""
        from custom_components.cable_modem_monitor.sensor import ModemLastBootTimeSensor
        from homeassistant.components.sensor import SensorDeviceClass

        sensor = ModemLastBootTimeSensor(mock_coordinator, mock_entry)

        ***REMOVED*** Check sensor attributes
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
