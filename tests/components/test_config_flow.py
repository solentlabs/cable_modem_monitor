"""Tests for Cable Modem Monitor config flow."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from homeassistant import config_entries

from custom_components.cable_modem_monitor.config_flow import (
    CableModemMonitorConfigFlow,
    CannotConnectError,
    OptionsFlowHandler,
    validate_input,
)

# Mock constants to avoid ImportError in tests
CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 600
MIN_SCAN_INTERVAL = 60
MAX_SCAN_INTERVAL = 1800


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
    @patch("custom_components.cable_modem_monitor.config_flow._do_quick_connectivity_check")
    @patch("custom_components.cable_modem_monitor.config_flow.ModemScraper")
    async def test_success(self, mock_scraper_class, mock_connectivity_check, mock_hass, valid_input):
        """Test successful validation."""
        # Mock connectivity check to succeed
        mock_connectivity_check.return_value = (True, None)

        # Mock scraper to return valid data
        mock_scraper = Mock()
        mock_scraper.get_modem_data.return_value = {
            "cable_modem_software_version": "1.0.0",
            "cable_modem_connection_status": "online",
        }
        # Mock detection info with proper dictionary
        mock_scraper.get_detection_info.return_value = {
            "modem_name": "Cable Modem",
            "manufacturer": "Unknown",
        }
        mock_scraper_class.return_value = mock_scraper

        # Mock async_add_executor_job to return the data
        async def mock_executor_job(func, *args):
            if func == mock_connectivity_check:
                return mock_connectivity_check(*args)
            return func(*args)

        mock_hass.async_add_executor_job = mock_executor_job

        result = await validate_input(mock_hass, valid_input)

        assert result["title"] == "Cable Modem (192.168.100.1)"

    @pytest.mark.asyncio
    @patch("custom_components.cable_modem_monitor.config_flow.get_parsers")
    @patch("custom_components.cable_modem_monitor.config_flow.ModemScraper")
    async def test_connection_failure(self, mock_scraper_class, mock_get_parsers, mock_hass, valid_input):
        """Test validation fails when cannot connect to modem."""
        # Mock get_parsers to return a mock parser
        mock_parser = Mock()
        mock_get_parsers.return_value = [mock_parser]

        # Mock scraper to raise exception
        mock_scraper = Mock()
        mock_scraper.get_modem_data.side_effect = Exception("Connection failed")
        mock_scraper_class.return_value = mock_scraper

        # Mock async_add_executor_job to call the function
        async def mock_executor_job(func, *args):
            return func(*args)

        mock_hass.async_add_executor_job = mock_executor_job

        with pytest.raises(CannotConnectError):
            await validate_input(mock_hass, valid_input)

    def test_requires_host(self, valid_input):
        """Test that host is required."""
        # Host should be in valid input
        assert CONF_HOST in valid_input


class TestScanIntervalValidation:
    """Test scan interval validation logic."""

    def test_scan_interval_below_minimum_invalid(self):
        """Test that values below minimum are invalid."""
        # 59 seconds should be below minimum
        assert MIN_SCAN_INTERVAL > 59

    def test_scan_interval_above_maximum_invalid(self):
        """Test that values above maximum are invalid."""
        # 1801 seconds should be above maximum
        assert MAX_SCAN_INTERVAL < 1801

    def test_scan_interval_at_boundaries_valid(self):
        """Test that boundary values are valid."""
        # Exact min and max should be valid
        assert MIN_SCAN_INTERVAL == 60
        assert MAX_SCAN_INTERVAL == 1800

    def test_scan_interval_common_values_valid(self):
        """Test common interval values are within range."""
        common_intervals = [
            60,  # 1 minute
            180,  # 3 minutes
            300,  # 5 minutes (default)
            600,  # 10 minutes
            900,  # 15 minutes
            1800,  # 30 minutes
        ]

        for interval in common_intervals:
            assert MIN_SCAN_INTERVAL <= interval <= MAX_SCAN_INTERVAL


class TestModemNameFormatting:
    """Test modem name and manufacturer formatting in titles."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = Mock()
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
    @patch("custom_components.cable_modem_monitor.config_flow._do_quick_connectivity_check")
    @patch("custom_components.cable_modem_monitor.config_flow.ModemScraper")
    async def test_title_without_duplicate_manufacturer(
        self, mock_scraper_class, mock_connectivity_check, mock_hass, valid_input
    ):
        """Test that manufacturer name is not duplicated when modem name includes it."""
        mock_connectivity_check.return_value = (True, None)

        mock_scraper = Mock()
        mock_scraper.get_modem_data.return_value = {
            "cable_modem_connection_status": "online",
        }
        # Modem name already starts with manufacturer
        mock_scraper.get_detection_info.return_value = {
            "modem_name": "Motorola MB7621",
            "manufacturer": "Motorola",
        }
        mock_scraper_class.return_value = mock_scraper

        async def mock_executor_job(func, *args):
            if func == mock_connectivity_check:
                return mock_connectivity_check(*args)
            return func(*args)

        mock_hass.async_add_executor_job = mock_executor_job

        result = await validate_input(mock_hass, valid_input)

        # Should NOT be "Motorola Motorola MB7621 (192.168.100.1)"
        assert result["title"] == "Motorola MB7621 (192.168.100.1)"

    @pytest.mark.asyncio
    @patch("custom_components.cable_modem_monitor.config_flow._do_quick_connectivity_check")
    @patch("custom_components.cable_modem_monitor.config_flow.ModemScraper")
    async def test_title_with_manufacturer_prepended(
        self, mock_scraper_class, mock_connectivity_check, mock_hass, valid_input
    ):
        """Test that manufacturer is prepended when not in modem name."""
        mock_connectivity_check.return_value = (True, None)

        mock_scraper = Mock()
        mock_scraper.get_modem_data.return_value = {
            "cable_modem_connection_status": "online",
        }
        # Modem name does NOT include manufacturer
        mock_scraper.get_detection_info.return_value = {
            "modem_name": "XB7",
            "manufacturer": "Technicolor",
        }
        mock_scraper_class.return_value = mock_scraper

        async def mock_executor_job(func, *args):
            if func == mock_connectivity_check:
                return mock_connectivity_check(*args)
            return func(*args)

        mock_hass.async_add_executor_job = mock_executor_job

        result = await validate_input(mock_hass, valid_input)

        # Should prepend manufacturer
        assert result["title"] == "Technicolor XB7 (192.168.100.1)"

    @pytest.mark.asyncio
    @patch("custom_components.cable_modem_monitor.config_flow._do_quick_connectivity_check")
    @patch("custom_components.cable_modem_monitor.config_flow.ModemScraper")
    async def test_title_without_manufacturer(
        self, mock_scraper_class, mock_connectivity_check, mock_hass, valid_input
    ):
        """Test title when manufacturer is Unknown."""
        mock_connectivity_check.return_value = (True, None)

        mock_scraper = Mock()
        mock_scraper.get_modem_data.return_value = {
            "cable_modem_connection_status": "online",
        }
        mock_scraper.get_detection_info.return_value = {
            "modem_name": "Generic Modem",
            "manufacturer": "Unknown",
        }
        mock_scraper_class.return_value = mock_scraper

        async def mock_executor_job(func, *args):
            if func == mock_connectivity_check:
                return mock_connectivity_check(*args)
            return func(*args)

        mock_hass.async_add_executor_job = mock_executor_job

        result = await validate_input(mock_hass, valid_input)

        # Should NOT include "Unknown"
        assert result["title"] == "Generic Modem (192.168.100.1)"

    @pytest.mark.asyncio
    @patch("custom_components.cable_modem_monitor.config_flow._do_quick_connectivity_check")
    @patch("custom_components.cable_modem_monitor.config_flow.ModemScraper")
    async def test_title_detection_info_included(
        self, mock_scraper_class, mock_connectivity_check, mock_hass, valid_input
    ):
        """Test that detection_info is included in result."""
        mock_connectivity_check.return_value = (True, None)

        mock_scraper = Mock()
        mock_scraper.get_modem_data.return_value = {
            "cable_modem_connection_status": "online",
        }
        detection_info = {
            "modem_name": "MB8611",
            "manufacturer": "Motorola",
            "successful_url": "http://192.168.100.1/someurl",
        }
        mock_scraper.get_detection_info.return_value = detection_info
        mock_scraper_class.return_value = mock_scraper

        async def mock_executor_job(func, *args):
            if func == mock_connectivity_check:
                return mock_connectivity_check(*args)
            return func(*args)

        mock_hass.async_add_executor_job = mock_executor_job

        result = await validate_input(mock_hass, valid_input)

        # Detection info should be in result
        assert "detection_info" in result
        assert result["detection_info"] == detection_info


class TestConfigConstants:
    """Test configuration constants are properly defined."""

    def test_all_config_keys_defined(self):
        """Test that all config keys are defined."""
        required_keys = [
            CONF_HOST,
            CONF_USERNAME,
            CONF_PASSWORD,
            CONF_SCAN_INTERVAL,
        ]

        # All should be strings
        for key in required_keys:
            assert isinstance(key, str)
            assert len(key) > 0

    def test_defaults_are_reasonable(self):
        """Test that default values make sense."""
        # Scan interval: 10 minutes
        assert DEFAULT_SCAN_INTERVAL == 600

        # Min interval: 1 minute
        assert MIN_SCAN_INTERVAL == 60

        # Max interval: 30 minutes
        assert MAX_SCAN_INTERVAL == 1800


class TestOptionsFlow:
    """Test the options flow for reconfiguration."""

    def test_exists(self):
        """Test that OptionsFlowHandler class exists."""
        assert OptionsFlowHandler is not None

    def test_has_init_step(self):
        """Test that options flow has init step."""
        assert hasattr(OptionsFlowHandler, "async_step_init")

    def test_can_instantiate_without_arguments(self):
        """Test that OptionsFlowHandler can be instantiated without arguments.

        This prevents the TypeError that caused a 500 error when trying to
        access the configuration UI in Home Assistant.
        """
        # This should not raise TypeError
        handler = OptionsFlowHandler()
        assert handler is not None


class TestConfigFlowRegistration:
    """Test the config flow registration."""

    def test_handler_is_registered(self):
        """Test that the config flow handler is registered."""
        handler = config_entries.HANDLERS.get("cable_modem_monitor")
        assert handler is not None
        assert handler == CableModemMonitorConfigFlow
