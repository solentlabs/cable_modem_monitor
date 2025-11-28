"""Tests for version logging and startup optimizations."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.cable_modem_monitor import async_setup_entry
from custom_components.cable_modem_monitor.const import (
    CONF_HOST,
    CONF_MODEM_CHOICE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_WORKING_URL,
    VERSION,
)


class TestVersionLogging:
    """Test version logging on startup."""

    @pytest.mark.asyncio
    async def test_version_logged_on_startup(self, caplog):
        """Test that version is logged when integration starts."""
        ***REMOVED*** Create a mock HomeAssistant instance
        hass = Mock(spec=HomeAssistant)
        hass.data = {}

        ***REMOVED*** Mock async_add_executor_job to execute the function and return the result
        async def mock_executor(func, *args):
            return func(*args)

        hass.async_add_executor_job = mock_executor

        ***REMOVED*** Mock config_entries
        hass.config_entries = Mock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()

        ***REMOVED*** Mock services
        hass.services = Mock()
        hass.services.has_service = Mock(return_value=False)
        hass.services.async_register = Mock()

        ***REMOVED*** Create a mock config entry
        mock_entry = Mock(spec=ConfigEntry)
        mock_entry.data = {
            CONF_HOST: "192.168.100.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_SCAN_INTERVAL: 600,
            CONF_MODEM_CHOICE: "Motorola MB7621",
            CONF_WORKING_URL: "http://192.168.100.1/MotoConnection.asp",
        }
        mock_entry.entry_id = "test_entry"
        mock_entry.state = ConfigEntryState.SETUP_IN_PROGRESS

        ***REMOVED*** Mock the necessary components
        with (
            patch("custom_components.cable_modem_monitor.parsers.get_parser_by_name") as mock_get_parser,
            patch("custom_components.cable_modem_monitor._create_health_monitor") as mock_health,
            patch("custom_components.cable_modem_monitor.DataUpdateCoordinator") as mock_coordinator,
            patch("custom_components.cable_modem_monitor._update_device_registry"),
            patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups") as mock_forward,
            caplog.at_level(logging.INFO),
        ):
            ***REMOVED*** Setup mocks
            mock_parser_class = Mock()
            mock_parser_class.return_value = Mock()
            mock_get_parser.return_value = mock_parser_class
            mock_health.return_value = Mock()

            ***REMOVED*** Create coordinator mock with async method
            coordinator_instance = Mock()
            coordinator_instance.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator.return_value = coordinator_instance

            mock_forward.return_value = AsyncMock()

            ***REMOVED*** Call async_setup_entry
            await async_setup_entry(hass, mock_entry)

            ***REMOVED*** Check that version was logged
            version_log = f"Cable Modem Monitor version {VERSION} is starting"
            assert any(version_log in record.message for record in caplog.records)

    def test_version_constant_format(self):
        """Test that VERSION constant is in correct format."""
        ***REMOVED*** Version should be semantic versioning format: X.Y.Z
        parts = VERSION.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    def test_current_version(self):
        """Test that version is the correct current version."""
        assert VERSION == "3.8.1"


class TestParserSelectionOptimization:
    """Test parser selection optimization during startup."""

    @pytest.mark.asyncio
    async def test_specific_modem_uses_get_parser_by_name(self):
        """Test that specific modem choice uses fast get_parser_by_name."""
        ***REMOVED*** Create a mock HomeAssistant instance
        hass = Mock(spec=HomeAssistant)
        hass.data = {}

        ***REMOVED*** Mock async_add_executor_job to execute the function and return the result
        async def mock_executor(func, *args):
            return func(*args)

        hass.async_add_executor_job = mock_executor

        ***REMOVED*** Mock config_entries
        hass.config_entries = Mock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()

        ***REMOVED*** Mock services
        hass.services = Mock()
        hass.services.has_service = Mock(return_value=False)
        hass.services.async_register = Mock()

        mock_entry = Mock(spec=ConfigEntry)
        mock_entry.data = {
            CONF_HOST: "192.168.100.1",
            CONF_MODEM_CHOICE: "Motorola MB7621",  ***REMOVED*** Specific choice
            CONF_WORKING_URL: "http://192.168.100.1/MotoConnection.asp",
        }
        mock_entry.entry_id = "test_entry"
        mock_entry.state = ConfigEntryState.SETUP_IN_PROGRESS

        with (
            patch("custom_components.cable_modem_monitor.parsers.get_parser_by_name") as mock_get_parser_by_name,
            patch("custom_components.cable_modem_monitor.parsers.get_parsers") as mock_get_parsers,
            patch("custom_components.cable_modem_monitor._create_health_monitor") as mock_health,
            patch("custom_components.cable_modem_monitor.DataUpdateCoordinator") as mock_coordinator,
            patch("custom_components.cable_modem_monitor._update_device_registry"),
            patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups") as mock_forward,
        ):
            ***REMOVED*** Setup mocks
            mock_parser_class = Mock()
            mock_parser_instance = Mock()
            mock_parser_class.return_value = mock_parser_instance
            mock_get_parser_by_name.return_value = mock_parser_class
            mock_health.return_value = Mock()

            ***REMOVED*** Create coordinator mock with async method
            coordinator_instance = Mock()
            coordinator_instance.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator.return_value = coordinator_instance

            mock_forward.return_value = AsyncMock()

            await async_setup_entry(hass, mock_entry)

            ***REMOVED*** Verify get_parser_by_name was called (fast path)
            mock_get_parser_by_name.assert_called_once_with("Motorola MB7621")

            ***REMOVED*** Verify get_parsers was NOT called (no full discovery)
            mock_get_parsers.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_mode_uses_get_parsers(self):
        """Test that auto mode uses get_parsers for discovery."""
        ***REMOVED*** Create a mock HomeAssistant instance
        hass = Mock(spec=HomeAssistant)
        hass.data = {}

        ***REMOVED*** Mock async_add_executor_job to execute the function and return the result
        async def mock_executor(func, *args):
            return func(*args)

        hass.async_add_executor_job = mock_executor

        ***REMOVED*** Mock config_entries
        hass.config_entries = Mock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()

        ***REMOVED*** Mock services
        hass.services = Mock()
        hass.services.has_service = Mock(return_value=False)
        hass.services.async_register = Mock()

        mock_entry = Mock(spec=ConfigEntry)
        mock_entry.data = {
            CONF_HOST: "192.168.100.1",
            CONF_MODEM_CHOICE: "auto",  ***REMOVED*** Auto mode
        }
        mock_entry.entry_id = "test_entry"
        mock_entry.state = ConfigEntryState.SETUP_IN_PROGRESS

        with (
            patch("custom_components.cable_modem_monitor.parsers.get_parser_by_name") as mock_get_parser_by_name,
            patch("custom_components.cable_modem_monitor.parsers.get_parsers") as mock_get_parsers,
            patch("custom_components.cable_modem_monitor._create_health_monitor") as mock_health,
            patch("custom_components.cable_modem_monitor.DataUpdateCoordinator") as mock_coordinator,
            patch("custom_components.cable_modem_monitor._update_device_registry"),
            patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups") as mock_forward,
        ):
            ***REMOVED*** Setup mocks
            mock_get_parsers.return_value = []
            mock_health.return_value = Mock()

            ***REMOVED*** Create coordinator mock with async method
            coordinator_instance = Mock()
            coordinator_instance.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator.return_value = coordinator_instance

            mock_forward.return_value = AsyncMock()

            await async_setup_entry(hass, mock_entry)

            ***REMOVED*** Verify get_parsers was called (need all parsers for auto)
            mock_get_parsers.assert_called_once()

            ***REMOVED*** Verify get_parser_by_name was NOT called
            mock_get_parser_by_name.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_to_auto_if_parser_not_found(self, caplog):
        """Test fallback to auto mode if specific parser not found."""
        ***REMOVED*** Create a mock HomeAssistant instance
        hass = Mock(spec=HomeAssistant)
        hass.data = {}

        ***REMOVED*** Mock async_add_executor_job to execute the function and return the result
        async def mock_executor(func, *args):
            return func(*args)

        hass.async_add_executor_job = mock_executor

        ***REMOVED*** Mock config_entries
        hass.config_entries = Mock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()

        ***REMOVED*** Mock services
        hass.services = Mock()
        hass.services.has_service = Mock(return_value=False)
        hass.services.async_register = Mock()

        mock_entry = Mock(spec=ConfigEntry)
        mock_entry.data = {
            CONF_HOST: "192.168.100.1",
            CONF_MODEM_CHOICE: "Invalid Parser Name",
        }
        mock_entry.entry_id = "test_entry"
        mock_entry.state = ConfigEntryState.SETUP_IN_PROGRESS

        with (
            patch("custom_components.cable_modem_monitor.parsers.get_parser_by_name") as mock_get_parser_by_name,
            patch("custom_components.cable_modem_monitor.parsers.get_parsers") as mock_get_parsers,
            patch("custom_components.cable_modem_monitor._create_health_monitor") as mock_health,
            patch("custom_components.cable_modem_monitor.DataUpdateCoordinator") as mock_coordinator,
            patch("custom_components.cable_modem_monitor._update_device_registry"),
            patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups") as mock_forward,
            caplog.at_level(logging.WARNING),
        ):
            ***REMOVED*** Setup mocks
            mock_get_parser_by_name.return_value = None  ***REMOVED*** Parser not found
            mock_get_parsers.return_value = []
            mock_health.return_value = Mock()

            ***REMOVED*** Create coordinator mock with async method
            coordinator_instance = Mock()
            coordinator_instance.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator.return_value = coordinator_instance

            mock_forward.return_value = AsyncMock()

            await async_setup_entry(hass, mock_entry)

            ***REMOVED*** Should log warning
            assert any("not found" in record.message for record in caplog.records)

            ***REMOVED*** Should fall back to get_parsers
            mock_get_parsers.assert_called_once()


class TestProtocolOptimizationIntegration:
    """Test protocol optimization integration in startup."""

    @pytest.mark.asyncio
    async def test_cached_url_passed_to_scraper(self):
        """Test that cached working URL is passed to ModemScraper."""
        ***REMOVED*** Create a mock HomeAssistant instance
        hass = Mock(spec=HomeAssistant)
        hass.data = {}

        ***REMOVED*** Mock async_add_executor_job to execute the function and return the result
        async def mock_executor(func, *args):
            return func(*args)

        hass.async_add_executor_job = mock_executor

        ***REMOVED*** Mock config_entries
        hass.config_entries = Mock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()

        ***REMOVED*** Mock services
        hass.services = Mock()
        hass.services.has_service = Mock(return_value=False)
        hass.services.async_register = Mock()

        mock_entry = Mock(spec=ConfigEntry)
        cached_url = "http://192.168.100.1/MotoConnection.asp"
        mock_entry.data = {
            CONF_HOST: "192.168.100.1",
            CONF_MODEM_CHOICE: "Motorola MB7621",
            CONF_WORKING_URL: cached_url,  ***REMOVED*** Cached URL with protocol
        }
        mock_entry.entry_id = "test_entry"
        mock_entry.state = ConfigEntryState.SETUP_IN_PROGRESS

        with (
            patch("custom_components.cable_modem_monitor.parsers.get_parser_by_name") as mock_get_parser,
            patch("custom_components.cable_modem_monitor.ModemScraper") as mock_scraper_class,
            patch("custom_components.cable_modem_monitor._create_health_monitor") as mock_health,
            patch("custom_components.cable_modem_monitor.DataUpdateCoordinator") as mock_coordinator,
            patch("custom_components.cable_modem_monitor._update_device_registry"),
            patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups") as mock_forward,
        ):
            ***REMOVED*** Setup mocks
            mock_parser_class = Mock()
            mock_parser_instance = Mock()
            mock_parser_class.return_value = mock_parser_instance
            mock_get_parser.return_value = mock_parser_class
            mock_scraper_class.return_value = Mock()
            mock_health.return_value = Mock()

            ***REMOVED*** Create coordinator mock with async method
            coordinator_instance = Mock()
            coordinator_instance.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator.return_value = coordinator_instance

            mock_forward.return_value = AsyncMock()

            await async_setup_entry(hass, mock_entry)

            ***REMOVED*** Verify ModemScraper was called with cached_url
            call_args = mock_scraper_class.call_args
            assert call_args is not None
            assert call_args.kwargs.get("cached_url") == cached_url
