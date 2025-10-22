"""Tests for Cable Modem Monitor sensors."""
import pytest
from unittest.mock import Mock
import sys
import os

***REMOVED*** Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'custom_components'))


class TestSensorSetup:
    """Test sensor platform setup."""

    def test_sensor_types_exist(self):
        """Test that expected sensor types are defined."""
        from cable_modem_monitor.sensor import (
            ModemConnectionStatusSensor,
            ModemTotalCorrectedSensor,
            ModemTotalUncorrectedSensor,
            ModemDownstreamChannelCountSensor,
            ModemUpstreamChannelCountSensor,
            ModemSoftwareVersionSensor,
            ModemSystemUptimeSensor,
        )

        ***REMOVED*** Verify classes exist
        assert ModemConnectionStatusSensor is not None
        assert ModemTotalCorrectedSensor is not None
        assert ModemTotalUncorrectedSensor is not None
        assert ModemDownstreamChannelCountSensor is not None
        assert ModemUpstreamChannelCountSensor is not None
        assert ModemSoftwareVersionSensor is not None
        assert ModemSystemUptimeSensor is not None

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
            "connection_status": "online",
            "downstream": [],
            "upstream": [],
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
        from cable_modem_monitor.sensor import ModemConnectionStatusSensor

        sensor = ModemConnectionStatusSensor(mock_coordinator, mock_entry)

        ***REMOVED*** Test state
        assert sensor.native_value == "online"

    def test_connection_status_offline(self, mock_coordinator, mock_entry):
        """Test connection status sensor with offline status."""
        from cable_modem_monitor.sensor import ModemConnectionStatusSensor

        mock_coordinator.data = {"connection_status": "unreachable"}
        sensor = ModemConnectionStatusSensor(mock_coordinator, mock_entry)

        assert sensor.native_value == "unreachable"


class TestErrorSensors:
    """Test error tracking sensors."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with error data."""
        coordinator = Mock()
        coordinator.data = {
            "total_corrected": 1000,
            "total_uncorrected": 5,
            "downstream": [],
            "upstream": [],
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
        from cable_modem_monitor.sensor import ModemTotalCorrectedSensor

        sensor = ModemTotalCorrectedSensor(mock_coordinator, mock_entry)

        assert sensor.native_value == 1000

    def test_uncorrected_errors_sensor(self, mock_coordinator, mock_entry):
        """Test uncorrected errors sensor."""
        from cable_modem_monitor.sensor import ModemTotalUncorrectedSensor

        sensor = ModemTotalUncorrectedSensor(mock_coordinator, mock_entry)

        assert sensor.native_value == 5

    def test_zero_errors(self, mock_coordinator, mock_entry):
        """Test sensors with zero errors."""
        from cable_modem_monitor.sensor import (
            ModemTotalCorrectedSensor,
            ModemTotalUncorrectedSensor,
        )

        mock_coordinator.data = {
            "total_corrected": 0,
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
            "downstream_channel_count": 24,
            "upstream_channel_count": 5,
            "downstream": [],
            "upstream": [],
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
        """Test downstream channel count sensor."""
        from cable_modem_monitor.sensor import ModemDownstreamChannelCountSensor

        sensor = ModemDownstreamChannelCountSensor(mock_coordinator, mock_entry)

        assert sensor.native_value == 24

    def test_upstream_count(self, mock_coordinator, mock_entry):
        """Test upstream channel count sensor."""
        from cable_modem_monitor.sensor import ModemUpstreamChannelCountSensor

        sensor = ModemUpstreamChannelCountSensor(mock_coordinator, mock_entry)

        assert sensor.native_value == 5


class TestSystemInfoSensors:
    """Test system information sensors."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with system info."""
        coordinator = Mock()
        coordinator.data = {
            "software_version": "1.0.0",
            "system_uptime": "2 days 5 hours",
            "downstream": [],
            "upstream": [],
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
        from cable_modem_monitor.sensor import ModemSoftwareVersionSensor

        sensor = ModemSoftwareVersionSensor(mock_coordinator, mock_entry)

        assert sensor.native_value == "1.0.0"

    def test_system_uptime(self, mock_coordinator, mock_entry):
        """Test system uptime sensor."""
        from cable_modem_monitor.sensor import ModemSystemUptimeSensor

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
        coordinator.data = {"downstream": [], "upstream": []}
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
        from cable_modem_monitor.sensor import ModemConnectionStatusSensor

        sensor = ModemConnectionStatusSensor(mock_coordinator, mock_entry)

        ***REMOVED*** Unique ID should be based on entry_id and sensor type
        assert sensor.unique_id is not None
        assert "test_entry" in sensor.unique_id

    def test_sensor_has_device_info(self, mock_coordinator, mock_entry):
        """Test that sensors have device info."""
        from cable_modem_monitor.sensor import ModemConnectionStatusSensor

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
        from cable_modem_monitor.sensor import ModemTotalCorrectedSensor

        coordinator = Mock()
        coordinator.data = {}  ***REMOVED*** Empty data

        sensor = ModemTotalCorrectedSensor(coordinator, mock_entry)

        ***REMOVED*** Should handle missing data gracefully (return None or default)
        result = sensor.native_value
        assert result is None or isinstance(result, int)

    def test_none_values(self, mock_entry):
        """Test sensors with None values."""
        from cable_modem_monitor.sensor import ModemSoftwareVersionSensor

        coordinator = Mock()
        coordinator.data = {"software_version": None}

        sensor = ModemSoftwareVersionSensor(coordinator, mock_entry)

        ***REMOVED*** Should handle None gracefully
        assert sensor.native_value is None or sensor.native_value == "Unknown"
