"""Tests for Cable Modem Monitor services.

Tests the generate_dashboard and clear_history services.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.cable_modem_monitor.const import DOMAIN
from custom_components.cable_modem_monitor.services import (
    create_clear_history_handler,
    create_generate_dashboard_handler,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator with channel data."""
    coordinator = MagicMock()
    coordinator.data = {
        "_downstream_by_id": {
            ("qam", 1): {"channel_id": 1, "power": 1.0},
            ("qam", 2): {"channel_id": 2, "power": 2.0},
        },
        "_upstream_by_id": {
            ("atdma", 1): {"channel_id": 1, "power": 40.0},
        },
    }
    # Coordinator has async_refresh method
    coordinator.async_refresh = MagicMock()
    return coordinator


@pytest.fixture
def mock_log_buffer():
    """Create a mock LogBuffer (has no .data attribute)."""
    log_buffer = MagicMock(spec=["get_entries", "clear"])
    # Explicitly remove .data to simulate real LogBuffer
    del log_buffer.data
    return log_buffer


@pytest.fixture
def mock_hass_with_coordinator(mock_coordinator):
    """Create mock hass with only coordinator in data."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            "test_entry_id": mock_coordinator,
        }
    }
    return hass


@pytest.fixture
def mock_hass_with_log_buffer(mock_coordinator, mock_log_buffer):
    """Create mock hass with both coordinator and log_buffer in data."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            "log_buffer": mock_log_buffer,  # This was causing the bug
            "test_entry_id": mock_coordinator,
        }
    }
    return hass


@pytest.fixture
def mock_hass_empty():
    """Create mock hass with no cable modem data."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    return hass


@pytest.fixture
def mock_hass_only_log_buffer(mock_log_buffer):
    """Create mock hass with only log_buffer (no coordinator)."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            "log_buffer": mock_log_buffer,
        }
    }
    return hass


@pytest.fixture
def mock_service_call():
    """Create a mock service call with default options."""
    call = MagicMock(spec=ServiceCall)
    call.data = {}
    return call


# =============================================================================
# GENERATE DASHBOARD TESTS
# =============================================================================


class TestGenerateDashboard:
    """Tests for generate_dashboard service."""

    def test_finds_coordinator_when_log_buffer_present(self, mock_hass_with_log_buffer, mock_service_call):
        """Service should find coordinator even when log_buffer is in hass.data.

        This was the bug: next(iter(hass.data[DOMAIN])) could return "log_buffer"
        instead of the actual entry_id, causing AttributeError.
        """
        handler = create_generate_dashboard_handler(mock_hass_with_log_buffer)
        result = handler(mock_service_call)

        assert "yaml" in result
        # Check for error comments (not entity names containing "Error")
        assert "# Error:" not in result["yaml"]
        assert "Cable Modem Dashboard" in result["yaml"]

    def test_finds_coordinator_without_log_buffer(self, mock_hass_with_coordinator, mock_service_call):
        """Service works when only coordinator is present."""
        handler = create_generate_dashboard_handler(mock_hass_with_coordinator)
        result = handler(mock_service_call)

        assert "yaml" in result
        # Check for error comments (not entity names containing "Error")
        assert "# Error:" not in result["yaml"]
        assert "Cable Modem Dashboard" in result["yaml"]

    def test_returns_error_when_no_domain_data(self, mock_hass_empty, mock_service_call):
        """Service returns error when DOMAIN not in hass.data."""
        handler = create_generate_dashboard_handler(mock_hass_empty)
        result = handler(mock_service_call)

        assert "yaml" in result
        assert "No cable modem configured" in result["yaml"]

    def test_returns_error_when_only_log_buffer(self, mock_hass_only_log_buffer, mock_service_call):
        """Service returns error when no coordinator exists (only log_buffer)."""
        handler = create_generate_dashboard_handler(mock_hass_only_log_buffer)
        result = handler(mock_service_call)

        assert "yaml" in result
        assert "No cable modem coordinator found" in result["yaml"]

    def test_generates_status_card_by_default(self, mock_hass_with_coordinator, mock_service_call):
        """Status card is included by default."""
        handler = create_generate_dashboard_handler(mock_hass_with_coordinator)
        result = handler(mock_service_call)

        assert "Cable Modem Status" in result["yaml"]

    def test_excludes_status_card_when_disabled(self, mock_hass_with_coordinator, mock_service_call):
        """Status card can be excluded."""
        mock_service_call.data = {"include_status_card": False}
        handler = create_generate_dashboard_handler(mock_hass_with_coordinator)
        result = handler(mock_service_call)

        assert "Cable Modem Status" not in result["yaml"]

    def test_includes_downstream_power_by_default(self, mock_hass_with_coordinator, mock_service_call):
        """Downstream power graphs included by default."""
        handler = create_generate_dashboard_handler(mock_hass_with_coordinator)
        result = handler(mock_service_call)

        # Should have power-related content
        assert "Power" in result["yaml"] or "power" in result["yaml"]

    def test_handles_empty_coordinator_data(self, mock_hass_with_coordinator, mock_service_call):
        """Service handles coordinator with no channel data."""
        mock_hass_with_coordinator.data[DOMAIN]["test_entry_id"].data = {}

        handler = create_generate_dashboard_handler(mock_hass_with_coordinator)
        result = handler(mock_service_call)

        # Should still return valid YAML structure
        assert "yaml" in result
        assert "Cable Modem Dashboard" in result["yaml"]


# =============================================================================
# CLEAR HISTORY TESTS
# =============================================================================


class TestClearHistory:
    """Tests for clear_history service."""

    @pytest.mark.asyncio
    async def test_clears_database_history(self, mock_hass_with_coordinator):
        """Service calls database cleanup for entity history."""
        mock_service_call = MagicMock(spec=ServiceCall)
        mock_service_call.data = {"days_to_keep": 7}

        # Mock entity registry
        mock_entity_entry = MagicMock()
        mock_entity_entry.entity_id = "sensor.cable_modem_status"
        mock_entity_entry.platform = DOMAIN

        mock_entity_registry = MagicMock()
        mock_entity_registry.entities.values.return_value = [mock_entity_entry]

        # Mock async_add_executor_job to track database cleanup calls
        cleanup_called = []

        async def mock_executor_job(func, *args):
            cleanup_called.append((func.__name__, args))
            return 0  # Return 0 records deleted

        mock_hass_with_coordinator.async_add_executor_job = mock_executor_job

        with patch(
            "custom_components.cable_modem_monitor.services.er.async_get",
            return_value=mock_entity_registry,
        ):
            handler = create_clear_history_handler(mock_hass_with_coordinator)
            await handler(mock_service_call)

        # Should have called _clear_db_history via executor
        assert len(cleanup_called) == 1
        assert cleanup_called[0][0] == "_clear_db_history"

    @pytest.mark.asyncio
    async def test_no_entities_found(self, mock_hass_with_coordinator):
        """Service handles case when no cable modem entities exist."""
        mock_service_call = MagicMock(spec=ServiceCall)
        mock_service_call.data = {"days_to_keep": 30}

        # Mock empty entity registry
        mock_entity_registry = MagicMock()
        mock_entity_registry.entities.values.return_value = []

        with patch(
            "custom_components.cable_modem_monitor.services.er.async_get",
            return_value=mock_entity_registry,
        ):
            handler = create_clear_history_handler(mock_hass_with_coordinator)
            # Should not raise, just log warning
            await handler(mock_service_call)
