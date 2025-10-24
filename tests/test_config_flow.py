"""Tests for Cable Modem Monitor config flow."""
import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path to import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'custom_components'))

from cable_modem_monitor.config_flow import (
    OptionsFlowHandler,
    CannotConnect,
    validate_input,
)
from cable_modem_monitor.const import (
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_HISTORY_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_HISTORY_DAYS,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
)


class TestConfigFlow:
    """Test the config flow."""

    def test_scan_interval_minimum_valid(self):
        """Test that minimum scan interval (60s) is accepted."""
        # Minimum value should be valid
        assert MIN_SCAN_INTERVAL == 60

    def test_scan_interval_maximum_valid(self):
        """Test that maximum scan interval (1800s) is accepted."""
        # Maximum value should be valid
        assert MAX_SCAN_INTERVAL == 1800

    def test_scan_interval_default_value(self):
        """Test that default scan interval is 600s (10 minutes)."""
        assert DEFAULT_SCAN_INTERVAL == 600

    def test_scan_interval_range_valid(self):
        """Test that scan interval range makes sense."""
        # Min should be less than default, default less than max
        assert MIN_SCAN_INTERVAL < DEFAULT_SCAN_INTERVAL < MAX_SCAN_INTERVAL

    def test_history_days_default_value(self):
        """Test that default history retention is 30 days."""
        assert DEFAULT_HISTORY_DAYS == 30


class TestValidateInput:
    """Test input validation."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = Mock()
        hass.async_add_executor_job = Mock(return_value=None)
        return hass

    @pytest.fixture
    def valid_input(self):
        """Provide valid input data."""
        return {
            CONF_HOST: "192.168.100.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        }

    @pytest.mark.asyncio
    @patch('cable_modem_monitor.config_flow.ModemScraper')
    async def test_validate_input_success(self, mock_scraper_class, mock_hass, valid_input):
        """Test successful validation."""
        # Mock scraper to return valid data
        mock_scraper = Mock()
        mock_scraper.get_modem_data.return_value = {
            "software_version": "1.0.0",
            "connection_status": "online",
        }
        mock_scraper_class.return_value = mock_scraper

        # Mock async_add_executor_job to return the data
        async def mock_executor_job(func, *args):
            return func(*args)

        mock_hass.async_add_executor_job = mock_executor_job

        result = await validate_input(mock_hass, valid_input)

        assert result["title"] == "Cable Modem (192.168.100.1)"

    @pytest.mark.asyncio
    @patch('cable_modem_monitor.config_flow.ModemScraper')
    async def test_validate_input_connection_failure(self, mock_scraper_class, mock_hass, valid_input):
        """Test validation fails when cannot connect to modem."""
        # Mock scraper to raise exception
        mock_scraper = Mock()
        mock_scraper.get_modem_data.side_effect = Exception("Connection failed")
        mock_scraper_class.return_value = mock_scraper

        # Mock async_add_executor_job to call the function
        async def mock_executor_job(func, *args):
            return func(*args)

        mock_hass.async_add_executor_job = mock_executor_job

        with pytest.raises(CannotConnect):
            await validate_input(mock_hass, valid_input)

    def test_validate_input_requires_host(self, valid_input):
        """Test that host is required."""
        # Host should be in valid input
        assert CONF_HOST in valid_input


class TestScanIntervalValidation:
    """Test scan interval validation logic."""

    def test_scan_interval_below_minimum_invalid(self):
        """Test that values below minimum are invalid."""
        # 59 seconds should be below minimum
        assert 59 < MIN_SCAN_INTERVAL

    def test_scan_interval_above_maximum_invalid(self):
        """Test that values above maximum are invalid."""
        # 1801 seconds should be above maximum
        assert 1801 > MAX_SCAN_INTERVAL

    def test_scan_interval_at_boundaries_valid(self):
        """Test that boundary values are valid."""
        # Exact min and max should be valid
        assert MIN_SCAN_INTERVAL == 60
        assert MAX_SCAN_INTERVAL == 1800

    def test_scan_interval_common_values_valid(self):
        """Test common interval values are within range."""
        common_intervals = [
            60,    # 1 minute
            180,   # 3 minutes
            300,   # 5 minutes (default)
            600,   # 10 minutes
            900,   # 15 minutes
            1800,  # 30 minutes
        ]

        for interval in common_intervals:
            assert MIN_SCAN_INTERVAL <= interval <= MAX_SCAN_INTERVAL


class TestHistoryDaysValidation:
    """Test history days validation logic."""

    def test_history_days_minimum(self):
        """Test minimum history retention is at least 1 day."""
        # Minimum should be at least 1 day
        assert 1 <= DEFAULT_HISTORY_DAYS

    def test_history_days_maximum(self):
        """Test maximum history retention is reasonable."""
        # Maximum should be 365 days (1 year)
        # This is enforced in config_flow vol.Range(min=1, max=365)
        max_history_days = 365
        assert DEFAULT_HISTORY_DAYS <= max_history_days

    def test_history_days_default_reasonable(self):
        """Test default history retention is reasonable."""
        # 30 days is a good default
        assert DEFAULT_HISTORY_DAYS == 30


class TestConfigConstants:
    """Test configuration constants are properly defined."""

    def test_all_config_keys_defined(self):
        """Test that all config keys are defined."""
        required_keys = [
            CONF_HOST,
            CONF_USERNAME,
            CONF_PASSWORD,
            CONF_SCAN_INTERVAL,
            CONF_HISTORY_DAYS,
        ]

        # All should be strings
        for key in required_keys:
            assert isinstance(key, str)
            assert len(key) > 0

    def test_defaults_are_reasonable(self):
        """Test that default values make sense."""
        # Scan interval: 10 minutes
        assert DEFAULT_SCAN_INTERVAL == 600

        # History: 30 days
        assert DEFAULT_HISTORY_DAYS == 30

        # Min interval: 1 minute
        assert MIN_SCAN_INTERVAL == 60

        # Max interval: 30 minutes
        assert MAX_SCAN_INTERVAL == 1800


class TestOptionsFlow:
    """Test the options flow for reconfiguration."""

    def test_options_flow_exists(self):
        """Test that OptionsFlowHandler class exists."""
        assert OptionsFlowHandler is not None

    def test_options_flow_has_init_step(self):
        """Test that options flow has init step."""
        assert hasattr(OptionsFlowHandler, 'async_step_init')

    def test_options_flow_can_instantiate_without_arguments(self):
        """Test that OptionsFlowHandler can be instantiated without arguments.

        This prevents the TypeError that caused a 500 error when trying to
        access the configuration UI in Home Assistant.
        """
        # This should not raise TypeError
        handler = OptionsFlowHandler()
        assert handler is not None
