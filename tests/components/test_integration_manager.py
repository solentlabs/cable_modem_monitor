"""Tests for the IntegrationManager lifecycle boundary.

These tests exercise the entry-scoped lifecycle owner directly so the adapter's
policy boundary is covered independently of startup and button call sites.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from custom_components.cable_modem_monitor.const import ChannelIdentity
from custom_components.cable_modem_monitor.integration_manager import (
    CableModemIntegrationManager,
)


def _make_snapshot(upstream: list[dict[str, object]] | None) -> SimpleNamespace:
    """Create a lightweight snapshot object for manager tests."""
    return SimpleNamespace(modem_data=None if upstream is None else {"upstream": upstream})


def _make_entity(
    *,
    config_entry_id: str | None,
    entity_id: str,
    unique_id: str | None,
    domain: str = "sensor",
) -> SimpleNamespace:
    """Create a lightweight entity-registry-like row for manager tests."""
    return SimpleNamespace(
        platform="cable_modem_monitor",
        config_entry_id=config_entry_id,
        entity_id=entity_id,
        unique_id=unique_id,
        domain=domain,
    )


def _make_device(*, device_id: str, identifiers: set[tuple[str, str]]) -> SimpleNamespace:
    """Create a lightweight device-registry-like row for manager tests."""
    return SimpleNamespace(id=device_id, identifiers=identifiers)


def test_reconcile_startup_entities_skips_registry_lookup_outside_id_mode():
    """Startup reconciliation is inactive outside ID mode."""
    manager = CableModemIntegrationManager(MagicMock(), "entry_abc")

    with patch("custom_components.cable_modem_monitor.integration_manager.er.async_get") as mock_get:
        removed = manager.reconcile_startup_entities(
            _make_snapshot([{"channel_type": "qam"}]),
            ChannelIdentity.NUMBER,
        )

    assert removed == []
    mock_get.assert_not_called()


def test_reconcile_startup_entities_skips_when_automatic_mode_disabled():
    """Startup reconciliation is skipped when automatic behavior is disabled."""
    manager = CableModemIntegrationManager(MagicMock(), "entry_abc")

    with patch("custom_components.cable_modem_monitor.integration_manager.er.async_get") as mock_get:
        removed = manager.reconcile_startup_entities(
            _make_snapshot([{"channel_type": "qam", "channel_id": 9}]),
            ChannelIdentity.ID,
            automatic_enabled=False,
        )

    assert removed == []
    mock_get.assert_not_called()


def test_reconcile_startup_entities_removes_obsolete_typed_channel_rows():
    """Startup reconciliation removes stale same-entry typed channel rows."""
    manager = CableModemIntegrationManager(MagicMock(), "entry_abc")

    stale_entity = _make_entity(
        config_entry_id="entry_abc",
        entity_id="sensor.entry_us_atdma_ch_9_power",
        unique_id="entry_abc_cable_modem_us_atdma_ch_9_power",
    )
    current_entity = _make_entity(
        config_entry_id="entry_abc",
        entity_id="sensor.entry_us_qam_ch_9_power",
        unique_id="entry_abc_cable_modem_us_qam_ch_9_power",
    )
    foreign_entity = _make_entity(
        config_entry_id="other_entry",
        entity_id="sensor.other_us_atdma_ch_9_power",
        unique_id="other_entry_cable_modem_us_atdma_ch_9_power",
    )

    entity_registry = MagicMock()
    entity_registry.entities.values.return_value = [
        stale_entity,
        current_entity,
        foreign_entity,
    ]

    snapshot = _make_snapshot(
        [
            {
                "channel_type": "qam",
                "channel_id": 9,
            }
        ]
    )

    with patch(
        "custom_components.cable_modem_monitor.integration_manager.er.async_get",
        return_value=entity_registry,
    ):
        removed = manager.reconcile_startup_entities(snapshot, ChannelIdentity.ID)

    assert removed == ["sensor.entry_us_atdma_ch_9_power"]


def test_reconcile_startup_entities_force_override_bypasses_disabled_automatic_mode():
    """Internal override can force startup reconciliation when auto mode is off."""
    manager = CableModemIntegrationManager(MagicMock(), "entry_abc")

    stale_entity = _make_entity(
        config_entry_id="entry_abc",
        entity_id="sensor.entry_us_atdma_ch_9_power",
        unique_id="entry_abc_cable_modem_us_atdma_ch_9_power",
    )
    entity_registry = MagicMock()
    entity_registry.entities.values.return_value = [stale_entity]

    snapshot = _make_snapshot(
        [
            {
                "channel_type": "qam",
                "channel_id": 9,
            }
        ]
    )

    with patch(
        "custom_components.cable_modem_monitor.integration_manager.er.async_get",
        return_value=entity_registry,
    ):
        removed = manager.reconcile_startup_entities(
            snapshot,
            ChannelIdentity.ID,
            automatic_enabled=False,
            force=True,
        )

    assert removed == ["sensor.entry_us_atdma_ch_9_power"]


def test_cleanup_entities_for_reset_applies_helper_rules():
    """Reset cleanup removes target rows and invalid same-domain rows."""
    hass = MagicMock()
    current_entry = MagicMock()
    current_entry.entry_id = "entry_abc"
    other_entry = MagicMock()
    other_entry.entry_id = "other_entry"
    hass.config_entries.async_entries.return_value = [current_entry, other_entry]

    entity_registry = MagicMock()
    entity_registry.entities.values.return_value = [
        _make_entity(
            config_entry_id="entry_abc",
            entity_id="sensor.attached",
            unique_id="entry_abc_cable_modem_status",
        ),
        _make_entity(
            config_entry_id=None,
            entity_id="sensor.orphan",
            unique_id="entry_abc_cable_modem_downstream_power",
        ),
        _make_entity(
            config_entry_id="other_entry",
            entity_id="sensor.foreign",
            unique_id="other_entry_cable_modem_status",
        ),
        _make_entity(
            config_entry_id=None,
            entity_id="sensor.unattributable",
            unique_id=None,
        ),
    ]

    manager = CableModemIntegrationManager(hass, "entry_abc")

    with patch(
        "custom_components.cable_modem_monitor.integration_manager.er.async_get",
        return_value=entity_registry,
    ):
        summary = manager.cleanup_entities_for_reset()

    assert summary.removed_entity_ids == [
        "sensor.attached",
        "sensor.orphan",
        "sensor.unattributable",
    ]


def test_cleanup_registry_rows_for_removal_applies_entity_and_device_rules():
    """Entry removal cleanup removes target-owned and deleted-owner rows."""
    hass = MagicMock()
    remaining_entry = MagicMock()
    remaining_entry.entry_id = "other_entry"
    hass.config_entries.async_entries.return_value = [remaining_entry]

    entity_registry = MagicMock()
    entity_registry.entities.values.return_value = [
        _make_entity(
            config_entry_id="entry_abc",
            entity_id="sensor.attached",
            unique_id="entry_abc_cable_modem_status",
        ),
        _make_entity(
            config_entry_id=None,
            entity_id="sensor.foreign_orphan",
            unique_id="other_entry_cable_modem_status",
        ),
        _make_entity(
            config_entry_id="deleted_entry",
            entity_id="sensor.deleted",
            unique_id="deleted_entry_cable_modem_status",
        ),
    ]

    device_registry = MagicMock()
    device_registry.devices.values.return_value = [
        _make_device(
            device_id="device-owned",
            identifiers={("cable_modem_monitor", "entry_abc")},
        ),
        _make_device(
            device_id="device-foreign",
            identifiers={("cable_modem_monitor", "other_entry")},
        ),
        _make_device(
            device_id="device-deleted",
            identifiers={("cable_modem_monitor", "deleted_entry")},
        ),
    ]

    manager = CableModemIntegrationManager(hass, "entry_abc")

    with (
        patch(
            "custom_components.cable_modem_monitor.integration_manager.er.async_get",
            return_value=entity_registry,
        ),
        patch(
            "custom_components.cable_modem_monitor.integration_manager.dr.async_get",
            return_value=device_registry,
        ),
    ):
        summary = manager.cleanup_registry_rows_for_removal()

    assert summary.removed_entity_ids == [
        "sensor.attached",
        "sensor.deleted",
    ]
    assert summary.removed_device_ids == ["device-owned", "device-deleted"]
