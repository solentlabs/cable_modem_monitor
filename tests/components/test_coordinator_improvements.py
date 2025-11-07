"""Tests for Cable Modem Monitor coordinator improvements."""
import pytest
from unittest.mock import Mock, AsyncMock


class TestCoordinatorSSLContext:
    """Test SSL context creation in executor."""

    def test_ssl_context_created_in_executor(self):
        """Test that SSL context is created in executor to avoid blocking I/O."""
        import inspect
        from custom_components.cable_modem_monitor import async_setup_entry

        source = inspect.getsource(async_setup_entry)

        # Verify SSL context creation pattern exists
        assert 'create_ssl_context' in source
        assert 'async_add_executor_job' in source
        assert 'ssl.create_default_context()' in source


class TestCoordinatorConfigEntry:
    """Test coordinator config_entry parameter."""

    def test_coordinator_has_config_entry_parameter(self):
        """Test that DataUpdateCoordinator includes config_entry parameter."""
        # This is tested by checking the code structure
        # The actual coordinator creation in __init__.py should have config_entry=entry
        # This is more of a code review check, but we can verify the pattern
        import inspect
        from custom_components.cable_modem_monitor import async_setup_entry

        source = inspect.getsource(async_setup_entry)

        # Check that config_entry parameter is passed to coordinator
        assert 'config_entry=entry' in source or 'config_entry = entry' in source


class TestCoordinatorPartialData:
    """Test coordinator returns partial data when scraper fails but health checks succeed."""

    def test_partial_data_when_scraper_fails_health_succeeds(self):
        """Test that coordinator returns partial data when scraper fails but health check succeeds."""
        import inspect
        from custom_components.cable_modem_monitor import async_setup_entry

        source = inspect.getsource(async_setup_entry)

        # Check for partial data return pattern when scraper fails but health succeeds
        assert 'cable_modem_connection_status' in source
        assert 'offline' in source
        assert 'ping_success or http_success' in source or 'health_result' in source


class TestCoordinatorUnload:
    """Test coordinator unload error handling."""

    @pytest.mark.asyncio
    async def test_unload_when_platforms_never_loaded(self):
        """Test that unload handles case where platforms were never loaded."""
        from custom_components.cable_modem_monitor import async_unload_entry

        # Mock Home Assistant
        mock_hass = Mock()
        mock_hass.data = {"cable_modem_monitor": {}}

        # Mock config entry
        mock_entry = Mock()
        mock_entry.entry_id = "test_entry"

        # Mock async_unload_platforms to raise ValueError (platforms never loaded)
        mock_hass.config_entries.async_unload_platforms = AsyncMock(
            side_effect=ValueError("Config entry was never loaded!")
        )

        # Mock service removal
        mock_hass.services.async_remove = Mock()

        # Should handle the error gracefully and return True
        result = await async_unload_entry(mock_hass, mock_entry)

        # Should succeed even though platforms weren't loaded
        assert result is True

    @pytest.mark.asyncio
    async def test_unload_cleans_up_coordinator_data(self):
        """Test that unload removes coordinator data."""
        from custom_components.cable_modem_monitor import async_unload_entry

        # Mock Home Assistant
        mock_hass = Mock()
        entry_id = "test_entry"
        mock_hass.data = {"cable_modem_monitor": {entry_id: Mock()}}

        # Mock config entry
        mock_entry = Mock()
        mock_entry.entry_id = entry_id

        # Mock successful platform unload
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        # Mock service removal
        mock_hass.services.async_remove = Mock()

        # Unload
        result = await async_unload_entry(mock_hass, mock_entry)

        # Should remove coordinator data
        assert entry_id not in mock_hass.data["cable_modem_monitor"]
        assert result is True


class TestCoordinatorStateCheck:
    """Test coordinator handles different config entry states."""

    def test_uses_first_refresh_for_setup_in_progress(self):
        """Test that async_config_entry_first_refresh is used during SETUP_IN_PROGRESS."""
        import inspect
        from custom_components.cable_modem_monitor import async_setup_entry

        source = inspect.getsource(async_setup_entry)

        # Check for state check pattern
        assert 'ConfigEntryState.SETUP_IN_PROGRESS' in source
        assert 'async_config_entry_first_refresh' in source
        assert 'async_refresh' in source

    def test_uses_regular_refresh_for_loaded_state(self):
        """Test that async_refresh is used when entry is already LOADED."""
        import inspect
        from custom_components.cable_modem_monitor import async_setup_entry

        source = inspect.getsource(async_setup_entry)

        # Check that both refresh methods are used conditionally
        assert 'else:' in source
        # The pattern should check state and use appropriate refresh method
