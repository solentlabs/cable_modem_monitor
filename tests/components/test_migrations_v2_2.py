"""Tests for the v2.2 migration that clears old channel Frequency statistics."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cable_modem_monitor import async_migrate_entry
from custom_components.cable_modem_monitor.const import DOMAIN
from custom_components.cable_modem_monitor.migrations import v2_2_frequency_statistics as v2_2

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

_PATCH_RECORDER = "custom_components.cable_modem_monitor.migrations.v2_2_frequency_statistics.get_instance"

# fmt: off
# ┌───────────────────────────────────┬─────────┬──────────────────────────────────┐
# │ unique_id suffix                  │ cleared │ description                      │
# ├───────────────────────────────────┼─────────┼──────────────────────────────────┤
# │ cable_modem_ds_ch_1_frequency     │ yes     │ position-mode downstream         │
# │ cable_modem_us_ch_2_frequency     │ yes     │ position-mode upstream           │
# │ cable_modem_ds_qam_ch_7_frequency │ yes     │ id-mode downstream               │
# │ cable_modem_ds_ch_1_power         │ no      │ other channel metric             │
# │ cable_modem_status                │ no      │ non-channel sensor               │
# └───────────────────────────────────┴─────────┴──────────────────────────────────┘
FREQUENCY_CASES = [
    ("cable_modem_ds_ch_1_frequency", "sensor.cable_modem_ds_ch_1_frequency", True),
    ("cable_modem_us_ch_2_frequency", "sensor.cable_modem_us_ch_2_frequency", True),
    ("cable_modem_ds_qam_ch_7_frequency", "sensor.cable_modem_ds_qam_ch_7_frequency", True),
    ("cable_modem_ds_ch_1_power", "sensor.cable_modem_ds_ch_1_power", False),
    ("cable_modem_status", "sensor.cable_modem_status", False),
]
# fmt: on


def _entry(minor_version: int) -> MockConfigEntry:
    """Build a v2 config entry at the given minor version."""
    return MockConfigEntry(domain=DOMAIN, version=2, minor_version=minor_version, data={})


def _register(hass: HomeAssistant, entry: MockConfigEntry, suffix: str, entity_id: str) -> None:
    """Register a sensor entity for the entry."""
    entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_{suffix}",
        suggested_object_id=entity_id.removeprefix("sensor."),
        config_entry=entry,
    )


@pytest.mark.parametrize("suffix,entity_id,cleared", FREQUENCY_CASES, ids=[c[0] for c in FREQUENCY_CASES])
async def test_clears_only_channel_frequency_statistics(
    hass: HomeAssistant, suffix: str, entity_id: str, cleared: bool
) -> None:
    """Only per-channel Frequency entities have their statistics cleared."""
    entry = _entry(1)
    _register(hass, entry, suffix, entity_id)
    hass.config.components.add("recorder")

    with patch(_PATCH_RECORDER) as get_instance:
        assert await v2_2.async_migrate(hass, entry) is True

    expected = [entity_id] if cleared else []
    called = [c.args[0] for c in get_instance.return_value.async_clear_statistics.call_args_list]
    assert called == ([expected] if cleared else [])


async def test_ignores_other_config_entries(hass: HomeAssistant) -> None:
    """Another config entry's Frequency sensor keeps its statistics."""
    mine, other = _entry(1), _entry(2)
    _register(hass, mine, "cable_modem_ds_ch_1_frequency", "sensor.cable_modem_ds_ch_1_frequency")
    _register(hass, other, "cable_modem_ds_ch_9_frequency", "sensor.other_ds_ch_9_frequency")
    hass.config.components.add("recorder")

    with patch(_PATCH_RECORDER) as get_instance:
        await v2_2.async_migrate(hass, mine)

    get_instance.return_value.async_clear_statistics.assert_called_once_with(["sensor.cable_modem_ds_ch_1_frequency"])


async def test_records_minor_version(hass: HomeAssistant) -> None:
    """A successful migration stores minor version 2 on the entry."""
    entry = _entry(1)
    entry.add_to_hass(hass)
    hass.config.components.add("recorder")

    with patch(_PATCH_RECORDER):
        await v2_2.async_migrate(hass, entry)

    assert entry.minor_version == 2


async def test_without_recorder_still_records_minor_version(hass: HomeAssistant) -> None:
    """No recorder means no statistics to clear; the migration completes."""
    entry = _entry(1)
    _register(hass, entry, "cable_modem_ds_ch_1_frequency", "sensor.cable_modem_ds_ch_1_frequency")
    assert "recorder" not in hass.config.components

    with patch(_PATCH_RECORDER) as get_instance:
        assert await v2_2.async_migrate(hass, entry) is True

    get_instance.assert_not_called()
    assert entry.minor_version == 2


# fmt: off
# ┌───────┬───────┬─────────┬───────────────────────────────────────────┐
# │ major │ minor │ clears  │ description                               │
# ├───────┼───────┼─────────┼───────────────────────────────────────────┤
# │ 2     │ 1     │ yes     │ existing 3.14 entry runs the migration    │
# │ 2     │ 2     │ no      │ already migrated: nothing to do           │
# │ 2     │ 3     │ no      │ newer minor than this build: left alone   │
# └───────┴───────┴─────────┴───────────────────────────────────────────┘
ENTRY_POINT_CASES = [(1, True), (2, False), (3, False)]
# fmt: on


@pytest.mark.parametrize("minor,clears", ENTRY_POINT_CASES, ids=[f"minor_{c[0]}" for c in ENTRY_POINT_CASES])
async def test_async_migrate_entry_runs_minor_step_once(hass: HomeAssistant, minor: int, clears: bool) -> None:
    """The component hook runs the v2.2 step only for entries below minor 2."""
    entry = _entry(minor)
    entry.add_to_hass(hass)
    migrate = MagicMock()

    async def _migrate(h: HomeAssistant, e: MockConfigEntry) -> bool:
        migrate()
        return True

    with patch.object(v2_2, "async_migrate", _migrate):
        assert await async_migrate_entry(hass, entry) is True

    assert migrate.called is clears


def test_config_flow_declares_minor_version() -> None:
    """New entries are created at the minor version, so they skip the migration."""
    from custom_components.cable_modem_monitor.config_flow import CableModemMonitorConfigFlow

    assert CableModemMonitorConfigFlow.MINOR_VERSION == v2_2.MINOR_VERSION
