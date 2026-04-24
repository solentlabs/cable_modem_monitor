"""Tests for channel_bond_storage — Store-backed baseline persistence.

Verifies the load/save round-trip contract and removal. The Store
implementation is HA's; these tests pin the payload shape and the
module's own serialization so a refactor of ``BondState`` breaks
loudly instead of silently corrupting persisted data.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.cable_modem_monitor.channel_bond_storage import (
    BondState,
    async_load_bond_state,
    async_remove_bond_state,
    async_save_bond_state,
)

_MODULE = "custom_components.cable_modem_monitor.channel_bond_storage"


async def test_load_returns_none_when_store_empty():
    """First-call load returns None so the caller can branch on fresh vs stored."""
    hass = MagicMock()
    mock_store = MagicMock()
    mock_store.async_load = AsyncMock(return_value=None)

    with patch(f"{_MODULE}.Store", return_value=mock_store):
        result = await async_load_bond_state(hass, "entry_abc")

    assert result is None


async def test_save_then_load_round_trip():
    """``async_save`` writes a dict that ``async_load`` reconstructs into BondState."""
    hass = MagicMock()
    captured: dict[str, int] = {}

    mock_store = MagicMock()
    mock_store.async_save = AsyncMock(side_effect=captured.update)
    mock_store.async_load = AsyncMock(side_effect=lambda: dict(captured) if captured else None)

    with patch(f"{_MODULE}.Store", return_value=mock_store):
        await async_save_bond_state(hass, "entry_abc", BondState(baseline_downstream=24, baseline_upstream=4))
        loaded = await async_load_bond_state(hass, "entry_abc")

    assert loaded == BondState(baseline_downstream=24, baseline_upstream=4)


async def test_remove_delegates_to_store():
    """``async_remove`` calls Store.async_remove so ``async_remove_entry`` cleans up."""
    hass = MagicMock()
    mock_store = MagicMock()
    mock_store.async_remove = AsyncMock()

    with patch(f"{_MODULE}.Store", return_value=mock_store):
        await async_remove_bond_state(hass, "entry_abc")

    mock_store.async_remove.assert_awaited_once()


@pytest.mark.parametrize(
    "entry_id,expected_key",
    [
        ("abc", "cable_modem_monitor.abc.channel_bond"),
        ("config_entry_9fd4", "cable_modem_monitor.config_entry_9fd4.channel_bond"),
    ],
)
async def test_storage_key_is_entry_scoped(entry_id, expected_key):
    """Storage key includes the entry ID so multi-modem installs don't collide."""
    hass = MagicMock()
    mock_store = MagicMock()
    mock_store.async_load = AsyncMock(return_value=None)

    with patch(f"{_MODULE}.Store", return_value=mock_store) as mock_store_cls:
        await async_load_bond_state(hass, entry_id)

    args, _ = mock_store_cls.call_args
    # Store(hass, version, key)
    assert args[2] == expected_key
