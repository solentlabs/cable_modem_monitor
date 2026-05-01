"""Tests for entity-reconciliation plan generation.

These tests validate the pure planning surface directly, including the real
typed-channel family provider used by runtime startup reconciliation.
"""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.cable_modem_monitor.const import ChannelIdentity
from custom_components.cable_modem_monitor.entity_reconciliation import (
    TypedMetricEntityFamily,
    build_channel_metric_entity_families,
    build_entity_reconciliation_plan,
)


def _make_entity(
    *,
    config_entry_id: str | None,
    entity_id: str,
    unique_id: str | None,
    domain: str = "sensor",
) -> SimpleNamespace:
    """Create a lightweight entity-registry-like row for entity-reconciliation tests."""
    return SimpleNamespace(
        platform="cable_modem_monitor",
        config_entry_id=config_entry_id,
        entity_id=entity_id,
        unique_id=unique_id,
        domain=domain,
    )


def _make_snapshot(
    *,
    downstream: list[dict[str, object]] | None = None,
    upstream: list[dict[str, object]] | None = None,
) -> SimpleNamespace:
    """Create a lightweight snapshot object for entity-reconciliation tests."""
    return SimpleNamespace(
        modem_data={
            "downstream": downstream or [],
            "upstream": upstream or [],
        }
    )


def test_build_entity_reconciliation_plan_computes_keep_remove_create_and_unmanaged():
    """Plan generation computes a full delta from real typed-channel families."""
    entity_registry = SimpleNamespace(
        entities=SimpleNamespace(
            values=lambda: [
                _make_entity(
                    config_entry_id="entry_abc",
                    entity_id="sensor.ds_qam_power",
                    unique_id="entry_abc_cable_modem_ds_qam_ch_29_power",
                ),
                _make_entity(
                    config_entry_id="entry_abc",
                    entity_id="sensor.ds_ofdm_old_power",
                    unique_id="entry_abc_cable_modem_ds_scqam_ch_159_power",
                ),
                _make_entity(
                    config_entry_id="entry_abc",
                    entity_id="sensor.us_atdma_old_power",
                    unique_id="entry_abc_cable_modem_us_atdma_ch_9_power",
                ),
                _make_entity(
                    config_entry_id="entry_abc",
                    entity_id="sensor.status",
                    unique_id="entry_abc_cable_modem_status",
                ),
                _make_entity(
                    config_entry_id="other_entry",
                    entity_id="sensor.foreign_ds",
                    unique_id="other_entry_cable_modem_ds_qam_ch_29_power",
                ),
            ]
        )
    )

    snapshot = _make_snapshot(
        downstream=[
            {"channel_type": "qam", "channel_id": 29, "power": 1.2, "snr": 38.0},
            {"channel_type": "ofdm", "channel_id": 159, "power": 2.3},
        ],
        upstream=[{"channel_type": "qam", "channel_id": 9, "power": 42.0}],
    )
    families = build_channel_metric_entity_families(snapshot, ChannelIdentity.ID)

    plan = build_entity_reconciliation_plan(
        entry_id="entry_abc",
        entity_registry=entity_registry,
        families=families,
    )

    assert plan.keep_entity_ids == ("sensor.ds_qam_power",)
    assert plan.remove_entity_ids == (
        "sensor.ds_ofdm_old_power",
        "sensor.us_atdma_old_power",
    )
    assert plan.create_later_unique_ids == (
        "entry_abc_cable_modem_ds_ofdm_ch_159_power",
        "entry_abc_cable_modem_ds_ofdm_ch_159_snr",
        "entry_abc_cable_modem_ds_qam_ch_29_snr",
        "entry_abc_cable_modem_us_qam_ch_9_power",
    )
    assert plan.unmanaged_entity_ids == ("sensor.status",)


def test_build_channel_metric_entity_families_returns_runtime_families_only_in_id_mode():
    """Runtime family providers are gated by identity mode and snapshot data."""
    snapshot = _make_snapshot(
        downstream=[{"channel_type": "qam", "channel_id": 29, "power": 1.2}],
        upstream=[{"channel_type": "qam", "channel_id": 9, "power": 42.0}],
    )

    assert build_channel_metric_entity_families(snapshot, ChannelIdentity.NUMBER) == ()

    families = build_channel_metric_entity_families(snapshot, ChannelIdentity.ID)

    assert tuple(family.name for family in families) == (
        "downstream-channel-metrics",
        "upstream-channel-metrics",
    )


def test_typed_metric_entity_family_skips_channels_without_typed_identity():
    """Typed families ignore channels that do not expose type and ID."""
    family = TypedMetricEntityFamily(
        name="downstream-channel-metrics",
        dir_code="ds",
        channels=(
            {"channel_type": "qam", "channel_id": 29, "power": 1.2},
            {"channel_type": None, "channel_id": 30, "power": 1.3},
            {"channel_type": "ofdm", "channel_id": None, "power": 1.4},
        ),
        metric_fields=("power",),
        always_present_fields=frozenset({"power"}),
    )

    assert family.expected_unique_ids("entry_abc") == {"entry_abc_cable_modem_ds_qam_ch_29_power"}
