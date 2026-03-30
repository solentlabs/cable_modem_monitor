"""Tests for button entities — setup, press handling, availability.

Mocks: orchestrator.restart(), orchestrator.reset_connectivity(),
       config_entries, entity_registry.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from solentlabs.cable_modem_monitor_core.orchestration.models import (
    RestartResult,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import RestartPhase

from custom_components.cable_modem_monitor.button import (
    RestartModemButton,
    UpdateModemDataButton,
    async_setup_entry,
)
from custom_components.cable_modem_monitor.coordinator import (
    CableModemRuntimeData,
)

from .conftest import MOCK_ENTRY_DATA

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _make_entry(runtime_data: CableModemRuntimeData) -> MagicMock:
    """Create a mock config entry with runtime_data."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = MOCK_ENTRY_DATA
    entry.runtime_data = runtime_data
    return entry


def _collect_entities(target: list):
    """Return an AddEntitiesCallback that appends to *target*."""

    def callback(new_entities, update_before_add=False):
        target.extend(new_entities)

    return callback


# -----------------------------------------------------------------------
# async_setup_entry
# -----------------------------------------------------------------------


async def test_setup_entry_with_restart(
    mock_runtime_data: CableModemRuntimeData,
):
    """Setup creates restart button when orchestrator supports it."""
    hass = MagicMock()
    entry = _make_entry(mock_runtime_data)
    entities: list = []

    await async_setup_entry(hass, entry, _collect_entities(entities))

    names = [e._attr_name for e in entities]
    assert "Restart Modem" in names
    assert "Update Modem Data" in names
    assert "Reset Entities" in names
    assert len(entities) == 3


async def test_setup_entry_without_restart(
    mock_orchestrator: MagicMock,
    mock_runtime_data: CableModemRuntimeData,
):
    """Setup omits restart button when orchestrator doesn't support it."""
    mock_orchestrator.supports_restart = False
    hass = MagicMock()
    entry = _make_entry(mock_runtime_data)
    entities: list = []

    await async_setup_entry(hass, entry, _collect_entities(entities))

    names = [e._attr_name for e in entities]
    assert "Restart Modem" not in names
    assert len(entities) == 2


# -----------------------------------------------------------------------
# UpdateModemDataButton
# -----------------------------------------------------------------------


async def test_update_button_press(
    mock_orchestrator: MagicMock,
    mock_runtime_data: CableModemRuntimeData,
):
    """Update button refreshes health then data coordinators."""
    entry = _make_entry(mock_runtime_data)
    button = UpdateModemDataButton(entry)
    button.hass = MagicMock()

    # Mock async refresh methods
    data_coord: MagicMock = mock_runtime_data.data_coordinator  # type: ignore[assignment]
    health_coord: MagicMock = mock_runtime_data.health_coordinator  # type: ignore[assignment]
    data_coord.async_request_refresh = AsyncMock()
    health_coord.async_request_refresh = AsyncMock()
    data_coord.last_update_success = True

    await button.async_press()

    mock_orchestrator.reset_connectivity.assert_called_once()
    health_coord.async_request_refresh.assert_awaited_once()
    data_coord.async_request_refresh.assert_awaited_once()


async def test_update_button_press_no_health(
    mock_runtime_data: CableModemRuntimeData,
):
    """Update button skips health refresh when no health coordinator."""
    mock_runtime_data.health_coordinator = None
    entry = _make_entry(mock_runtime_data)
    button = UpdateModemDataButton(entry)
    button.hass = MagicMock()

    data_coord: MagicMock = mock_runtime_data.data_coordinator  # type: ignore[assignment]
    data_coord.async_request_refresh = AsyncMock()
    data_coord.last_update_success = True

    await button.async_press()

    data_coord.async_request_refresh.assert_awaited_once()


# -----------------------------------------------------------------------
# RestartModemButton
# -----------------------------------------------------------------------


def test_restart_button_unavailable_during_restart(
    mock_orchestrator: MagicMock,
    mock_runtime_data: CableModemRuntimeData,
):
    """Restart button is unavailable while restart in progress."""
    mock_orchestrator.is_restarting = True
    entry = _make_entry(mock_runtime_data)
    button = RestartModemButton(entry)
    assert button.available is False


def test_restart_button_available_normally(
    mock_orchestrator: MagicMock,
    mock_runtime_data: CableModemRuntimeData,
):
    """Restart button available when not restarting."""
    mock_orchestrator.is_restarting = False
    entry = _make_entry(mock_runtime_data)
    button = RestartModemButton(entry)
    assert button.available is True


async def test_restart_button_press_success(
    mock_runtime_data: CableModemRuntimeData,
):
    """Successful restart sends notification and refreshes data."""
    entry = _make_entry(mock_runtime_data)
    button = RestartModemButton(entry)
    button.hass = MagicMock()
    button.hass.async_add_executor_job = AsyncMock(
        return_value=RestartResult(
            success=True,
            phase_reached=RestartPhase.COMPLETE,
            elapsed_seconds=90.0,
        )
    )
    button.hass.services.async_call = AsyncMock()
    data_coord: MagicMock = mock_runtime_data.data_coordinator  # type: ignore[assignment]
    data_coord.async_request_refresh = AsyncMock()

    await button.async_press()

    # Notification sent
    button.hass.services.async_call.assert_awaited()
    call_args = button.hass.services.async_call.call_args
    assert "Complete" in call_args[0][2]["title"]

    # Data refreshed
    data_coord.async_request_refresh.assert_awaited_once()

    # Cancel event cleared
    assert mock_runtime_data.cancel_event is None


async def test_restart_button_press_failure(
    mock_runtime_data: CableModemRuntimeData,
):
    """Failed restart sends failure notification."""
    entry = _make_entry(mock_runtime_data)
    button = RestartModemButton(entry)
    button.hass = MagicMock()
    button.hass.async_add_executor_job = AsyncMock(
        return_value=RestartResult(
            success=False,
            phase_reached=RestartPhase.COMMAND_SENT,
            elapsed_seconds=5.0,
            error="Command rejected",
        )
    )
    button.hass.services.async_call = AsyncMock()
    data_coord: MagicMock = mock_runtime_data.data_coordinator  # type: ignore[assignment]
    data_coord.async_request_refresh = AsyncMock()

    await button.async_press()

    call_args = button.hass.services.async_call.call_args
    assert "Failed" in call_args[0][2]["title"]


async def test_restart_button_skips_if_already_restarting(
    mock_orchestrator: MagicMock,
    mock_runtime_data: CableModemRuntimeData,
):
    """Restart button press ignored when restart already in progress."""
    mock_orchestrator.is_restarting = True
    entry = _make_entry(mock_runtime_data)
    button = RestartModemButton(entry)
    button.hass = MagicMock()
    button.hass.async_add_executor_job = AsyncMock()

    await button.async_press()

    button.hass.async_add_executor_job.assert_not_awaited()
