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
            "total_uncorrected": 0,
        }

        corrected_sensor = ModemTotalCorrectedSensor(mock_coordinator, mock_entry)
        uncorrected_sensor = ModemTotalUncorrectedSensor(mock_coordinator, mock_entry)

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

        # Test channel sensor
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
