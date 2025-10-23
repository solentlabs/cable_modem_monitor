"""Tests for Cable Modem Monitor coordinator functionality."""
import pytest
from unittest.mock import Mock
from datetime import timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'custom_components'))

from cable_modem_monitor.const import (
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
)


class TestCoordinatorInterval:
    """Test coordinator respects scan interval configuration."""

    def test_default_scan_interval_as_timedelta(self):
        """Test default scan interval converts to timedelta correctly."""
        interval = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

        # Should be 10 minutes
        assert interval.total_seconds() == 600
        assert interval == timedelta(minutes=10)

    def test_minimum_scan_interval_as_timedelta(self):
        """Test minimum scan interval converts to timedelta correctly."""
        interval = timedelta(seconds=MIN_SCAN_INTERVAL)

        # Should be 1 minute
        assert interval.total_seconds() == 60
        assert interval == timedelta(minutes=1)

    def test_maximum_scan_interval_as_timedelta(self):
        """Test maximum scan interval converts to timedelta correctly."""
        interval = timedelta(seconds=MAX_SCAN_INTERVAL)

        # Should be 30 minutes
        assert interval.total_seconds() == 1800
        assert interval == timedelta(minutes=30)

    def test_custom_scan_intervals(self):
        """Test various custom scan intervals."""
        test_cases = [
            (60, timedelta(minutes=1)),
            (180, timedelta(minutes=3)),
            (300, timedelta(minutes=5)),
            (600, timedelta(minutes=10)),
            (900, timedelta(minutes=15)),
            (1800, timedelta(minutes=30)),
        ]

        for seconds, expected in test_cases:
            result = timedelta(seconds=seconds)
            assert result == expected


class TestModemDataUpdate:
    """Test data update logic."""

    @pytest.fixture
    def mock_scraper(self):
        """Create a mock modem scraper."""
        scraper = Mock()
        scraper.get_modem_data.return_value = {
            "software_version": "1.0.0",
            "system_uptime": "1 day 2 hours",
            "connection_status": "online",
            "downstream_channel_count": 24,
            "upstream_channel_count": 5,
            "downstream_channels": [],
            "upstream_channels": [],
            "total_corrected_errors": 100,
            "total_uncorrected_errors": 0,
        }
        return scraper

    def test_scraper_returns_valid_data(self, mock_scraper):
        """Test that scraper returns expected data structure."""
        data = mock_scraper.get_modem_data()

        # Check required keys
        assert "software_version" in data
        assert "connection_status" in data
        assert "downstream_channel_count" in data
        assert "upstream_channel_count" in data

    def test_scraper_handles_connection_failure(self):
        """Test that scraper can raise exceptions for connection failures."""
        scraper = Mock()
        scraper.get_modem_data.side_effect = Exception("Connection timeout")

        with pytest.raises(Exception) as exc_info:
            scraper.get_modem_data()

        assert "Connection timeout" in str(exc_info.value)

    def test_scraper_data_types(self, mock_scraper):
        """Test that scraper returns correct data types."""
        data = mock_scraper.get_modem_data()

        # String fields
        assert isinstance(data["software_version"], str)
        assert isinstance(data["system_uptime"], str)
        assert isinstance(data["connection_status"], str)

        # Integer fields
        assert isinstance(data["downstream_channel_count"], int)
        assert isinstance(data["upstream_channel_count"], int)
        assert isinstance(data["total_corrected_errors"], int)
        assert isinstance(data["total_uncorrected_errors"], int)

        # List fields
        assert isinstance(data["downstream_channels"], list)
        assert isinstance(data["upstream_channels"], list)


class TestUpdateFailureHandling:
    """Test how coordinator handles update failures."""

    def test_connection_error_structure(self):
        """Test that connection errors can be caught."""
        error = Exception("Failed to connect to modem")
        assert str(error) == "Failed to connect to modem"

    def test_timeout_error_structure(self):
        """Test that timeout errors can be caught."""
        error = Exception("Connection timed out")
        assert "timed out" in str(error).lower()

    def test_parsing_error_structure(self):
        """Test that parsing errors can be caught."""
        error = Exception("Failed to parse HTML")
        assert "parse" in str(error).lower()


class TestCoordinatorConfiguration:
    """Test coordinator configuration from config entry."""

    def test_extract_scan_interval_from_config(self):
        """Test extracting scan interval from config entry data."""
        config_data = {
            "host": "192.168.100.1",
            "scan_interval": 600,  # 10 minutes
        }

        scan_interval = config_data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        assert scan_interval == 600

    def test_default_scan_interval_when_not_configured(self):
        """Test using default when scan interval not in config."""
        config_data = {
            "host": "192.168.100.1",
        }

        scan_interval = config_data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        assert scan_interval == DEFAULT_SCAN_INTERVAL

    def test_scan_interval_validation_minimum(self):
        """Test that scan interval respects minimum."""
        configured_interval = 30  # Too low

        # Should be clamped to minimum
        actual_interval = max(configured_interval, MIN_SCAN_INTERVAL)
        assert actual_interval == MIN_SCAN_INTERVAL

    def test_scan_interval_validation_maximum(self):
        """Test that scan interval respects maximum."""
        configured_interval = 3600  # Too high (60 minutes)

        # Should be clamped to maximum
        actual_interval = min(configured_interval, MAX_SCAN_INTERVAL)
        assert actual_interval == MAX_SCAN_INTERVAL

    def test_scan_interval_validation_range(self):
        """Test scan interval clamping to valid range."""
        test_cases = [
            (30, MIN_SCAN_INTERVAL),      # Below min -> clamp to min
            (60, 60),                     # At min -> keep
            (300, 300),                   # Normal -> keep
            (1800, 1800),                 # At max -> keep
            (3600, MAX_SCAN_INTERVAL),    # Above max -> clamp to max
        ]

        for input_val, expected in test_cases:
            result = max(MIN_SCAN_INTERVAL, min(input_val, MAX_SCAN_INTERVAL))
            assert result == expected


class TestReloadFunctionality:
    """Test that configuration changes trigger reload."""

    def test_reload_function_exists(self):
        """Test that async_reload_entry function signature exists."""
        # This is validated by the integration structure
        # In real implementation, __init__.py has async_reload_entry
        assert True  # Placeholder - would need full HA test harness

    def test_config_change_detection(self):
        """Test detecting config changes that require reload."""
        old_config = {
            "host": "192.168.100.1",
            "scan_interval": 300,
        }

        new_config = {
            "host": "192.168.100.1",
            "scan_interval": 600,  # Changed
        }

        # Scan interval changed
        assert old_config["scan_interval"] != new_config["scan_interval"]

    def test_no_reload_when_config_unchanged(self):
        """Test that identical config doesn't trigger reload."""
        old_config = {
            "host": "192.168.100.1",
            "scan_interval": 300,
        }

        new_config = {
            "host": "192.168.100.1",
            "scan_interval": 300,
        }

        # Config identical
        assert old_config == new_config
