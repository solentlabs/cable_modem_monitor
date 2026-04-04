"""Tests for button entities — setup, press handling, availability.

Mocks: orchestrator.restart(), orchestrator.reset_connectivity(),
       config_entries, entity_registry.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from solentlabs.cable_modem_monitor_core.orchestration.models import (
    RestartResult,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import RestartPhase

from custom_components.cable_modem_monitor.button import (
    ResetEntitiesButton,
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
    mock_data_coordinator: MagicMock,
    mock_health_coordinator: MagicMock,
    mock_runtime_data: CableModemRuntimeData,
):
    """Update button refreshes health then data coordinators."""
    entry = _make_entry(mock_runtime_data)
    button = UpdateModemDataButton(entry)
    button.hass = MagicMock()

    mock_data_coordinator.async_request_refresh = AsyncMock()
    mock_health_coordinator.async_request_refresh = AsyncMock()
    mock_data_coordinator.last_update_success = True

    await button.async_press()

    mock_orchestrator.reset_connectivity.assert_called_once()
    mock_health_coordinator.async_request_refresh.assert_awaited_once()
    mock_data_coordinator.async_request_refresh.assert_awaited_once()


async def test_update_button_press_no_health(
    mock_data_coordinator: MagicMock,
    mock_runtime_data: CableModemRuntimeData,
):
    """Update button skips health refresh when no health coordinator."""
    mock_runtime_data.health_coordinator = None
    entry = _make_entry(mock_runtime_data)
    button = UpdateModemDataButton(entry)
    button.hass = MagicMock()

    mock_data_coordinator.async_request_refresh = AsyncMock()
    mock_data_coordinator.last_update_success = True

    await button.async_press()

    mock_data_coordinator.async_request_refresh.assert_awaited_once()


# -----------------------------------------------------------------------
# RestartModemButton
# -----------------------------------------------------------------------


def test_restart_button_available_by_default(
    mock_runtime_data: CableModemRuntimeData,
):
    """Restart button available when created (default state)."""
    entry = _make_entry(mock_runtime_data)
    button = RestartModemButton(entry)
    assert button.available is True


async def test_restart_button_press_success(
    mock_data_coordinator: MagicMock,
    mock_runtime_data: CableModemRuntimeData,
):
    """Successful restart sends notification and refreshes data."""
    entry = _make_entry(mock_runtime_data)
    button = RestartModemButton(entry)
    button.hass = MagicMock()
    button.async_write_ha_state = MagicMock()
    button.hass.async_add_executor_job = AsyncMock(
        return_value=RestartResult(
            success=True,
            phase_reached=RestartPhase.COMPLETE,
            elapsed_seconds=90.0,
        )
    )
    button.hass.services.async_call = AsyncMock()
    mock_data_coordinator.async_request_refresh = AsyncMock()

    await button.async_press()

    # Notification sent
    button.hass.services.async_call.assert_awaited()
    call_args = button.hass.services.async_call.call_args
    assert "Complete" in call_args[0][2]["title"]

    # Data refreshed
    mock_data_coordinator.async_request_refresh.assert_awaited_once()

    # Cancel event cleared
    assert mock_runtime_data.cancel_event is None


async def test_restart_button_press_failure(
    mock_data_coordinator: MagicMock,
    mock_runtime_data: CableModemRuntimeData,
):
    """Failed restart sends failure notification."""
    entry = _make_entry(mock_runtime_data)
    button = RestartModemButton(entry)
    button.hass = MagicMock()
    button.async_write_ha_state = MagicMock()
    button.hass.async_add_executor_job = AsyncMock(
        return_value=RestartResult(
            success=False,
            phase_reached=RestartPhase.COMMAND_SENT,
            elapsed_seconds=5.0,
            error="Command rejected",
        )
    )
    button.hass.services.async_call = AsyncMock()
    mock_data_coordinator.async_request_refresh = AsyncMock()

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


async def test_restart_button_unavailable_during_restart(
    mock_data_coordinator: MagicMock,
    mock_runtime_data: CableModemRuntimeData,
):
    """Button shows unavailable in HA during restart, available after."""
    entry = _make_entry(mock_runtime_data)
    button = RestartModemButton(entry)
    button.hass = MagicMock()
    button.async_write_ha_state = MagicMock()
    button.hass.services.async_call = AsyncMock()
    mock_data_coordinator.async_request_refresh = AsyncMock()

    # Capture _attr_available at the moment restart() runs
    available_during_restart: list[bool] = []

    async def _capture_state(*args, **kwargs):
        available_during_restart.append(button._attr_available)
        return RestartResult(
            success=True,
            phase_reached=RestartPhase.COMPLETE,
            elapsed_seconds=60.0,
        )

    button.hass.async_add_executor_job = AsyncMock(side_effect=_capture_state)

    await button.async_press()

    # During restart: unavailable
    assert available_during_restart == [False]
    # After restart: available again
    assert button._attr_available is True
    # State pushed to HA twice (before + after)
    assert button.async_write_ha_state.call_count == 2


async def test_restart_button_available_restored_on_exception(
    mock_data_coordinator: MagicMock,
    mock_runtime_data: CableModemRuntimeData,
):
    """Button restores availability even when restart raises."""
    entry = _make_entry(mock_runtime_data)
    button = RestartModemButton(entry)
    button.hass = MagicMock()
    button.async_write_ha_state = MagicMock()
    button.hass.services.async_call = AsyncMock()
    mock_data_coordinator.async_request_refresh = AsyncMock()
    button.hass.async_add_executor_job = AsyncMock(
        side_effect=ConnectionError("modem unreachable"),
    )

    with pytest.raises(ConnectionError):
        await button.async_press()

    # finally block restores availability
    assert button._attr_available is True
    assert button.async_write_ha_state.call_count == 2


# -----------------------------------------------------------------------
# ResetEntitiesButton
# -----------------------------------------------------------------------


async def test_reset_button_press_with_probes(
    mock_runtime_data: CableModemRuntimeData,
):
    """Reset button re-detects probes, removes entities, reloads."""
    entry = _make_entry(mock_runtime_data)
    button = ResetEntitiesButton(entry)
    button.hass = MagicMock()
    button.hass.services.async_call = AsyncMock()
    button.hass.config_entries.async_update_entry = MagicMock()
    button.hass.config_entries.async_reload = AsyncMock()

    # Mock entity registry with two entities for this entry
    mock_entity_reg = MagicMock()
    entity_1 = MagicMock()
    entity_1.platform = "cable_modem_monitor"
    entity_1.config_entry_id = "test_entry"
    entity_1.entity_id = "sensor.modem_1"
    entity_2 = MagicMock()
    entity_2.platform = "cable_modem_monitor"
    entity_2.config_entry_id = "test_entry"
    entity_2.entity_id = "sensor.modem_2"
    mock_entity_reg.entities.values.return_value = [entity_1, entity_2]

    # Mock probe detection returning results
    probe_result = {"supports_icmp": True, "supports_head": False}

    with (
        patch(
            "custom_components.cable_modem_monitor.button.er.async_get",
            return_value=mock_entity_reg,
        ),
        patch.object(button, "_redetect_probes", new=AsyncMock(return_value=probe_result)),
    ):
        await button.async_press()

    # Entities removed
    assert mock_entity_reg.async_remove.call_count == 2

    # Config entry updated with new probes
    button.hass.config_entries.async_update_entry.assert_called_once()

    # Integration reloaded
    button.hass.config_entries.async_reload.assert_awaited_once()

    # Notification sent with probe info
    call_args = button.hass.services.async_call.call_args
    assert "ICMP=yes" in call_args[0][2]["message"]
    assert "HEAD=no" in call_args[0][2]["message"]


async def test_reset_button_press_probes_failed(
    mock_runtime_data: CableModemRuntimeData,
):
    """Reset button continues when probe re-detection fails."""
    entry = _make_entry(mock_runtime_data)
    button = ResetEntitiesButton(entry)
    button.hass = MagicMock()
    button.hass.services.async_call = AsyncMock()
    button.hass.config_entries.async_update_entry = MagicMock()
    button.hass.config_entries.async_reload = AsyncMock()

    mock_entity_reg = MagicMock()
    mock_entity_reg.entities.values.return_value = []

    with (
        patch(
            "custom_components.cable_modem_monitor.button.er.async_get",
            return_value=mock_entity_reg,
        ),
        patch.object(button, "_redetect_probes", new=AsyncMock(return_value=None)),
    ):
        await button.async_press()

    # No config entry update when probes failed
    button.hass.config_entries.async_update_entry.assert_not_called()

    # Still reloads
    button.hass.config_entries.async_reload.assert_awaited_once()


async def test_redetect_probes_success(
    mock_runtime_data: CableModemRuntimeData,
):
    """Probe re-detection returns dict on success."""
    entry = _make_entry(mock_runtime_data)
    button = ResetEntitiesButton(entry)
    button.hass = MagicMock()
    button.hass.async_add_executor_job = AsyncMock(
        side_effect=[
            MagicMock(),  # load_modem_config
            {"supports_icmp": True, "supports_head": True},  # detect_probes
        ]
    )

    result = await button._redetect_probes()

    assert result == {"supports_icmp": True, "supports_head": True}


async def test_redetect_probes_config_load_failure(
    mock_runtime_data: CableModemRuntimeData,
):
    """Probe re-detection returns None when config load fails."""
    entry = _make_entry(mock_runtime_data)
    button = ResetEntitiesButton(entry)
    button.hass = MagicMock()
    button.hass.async_add_executor_job = AsyncMock(
        side_effect=FileNotFoundError("modem.yaml not found"),
    )

    result = await button._redetect_probes()

    assert result is None


async def test_redetect_probes_detection_failure(
    mock_runtime_data: CableModemRuntimeData,
):
    """Probe re-detection returns None when probes fail."""
    entry = _make_entry(mock_runtime_data)
    button = ResetEntitiesButton(entry)
    button.hass = MagicMock()
    button.hass.async_add_executor_job = AsyncMock(
        side_effect=[
            MagicMock(),  # load_modem_config succeeds
            ConnectionError("unreachable"),  # detect_probes fails
        ],
    )

    result = await button._redetect_probes()

    assert result is None
