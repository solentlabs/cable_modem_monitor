"""Tests for helper-level registry cleanup mechanics.

These tests validate the low-level matching and removal rules directly,
separate from adapter call sites.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.cable_modem_monitor.entity_registry_helpers import (
    device_should_remove,
    entity_should_remove,
)


def _make_entity(
    *,
    platform: str = "cable_modem_monitor",
    config_entry_id: str | None,
    unique_id: str | None,
) -> SimpleNamespace:
    """Create a lightweight entity-registry-like row for tests."""
    return SimpleNamespace(
        platform=platform,
        config_entry_id=config_entry_id,
        unique_id=unique_id,
    )


def _make_device(*, identifiers: set[tuple[str, str]]) -> SimpleNamespace:
    """Create a lightweight device-registry-like row for tests."""
    return SimpleNamespace(identifiers=identifiers)


ENTITY_REMOVAL_CASES = [
    (
        "current_entry_row",
        _make_entity(
            config_entry_id="entry_abc",
            unique_id="entry_abc_cable_modem_status",
        ),
        {"other_entry"},
        True,
    ),
    (
        "target_owned_orphan_row",
        _make_entity(
            config_entry_id=None,
            unique_id="entry_abc_cable_modem_downstream_power",
        ),
        {"other_entry"},
        True,
    ),
    (
        "live_foreign_row",
        _make_entity(
            config_entry_id="other_entry",
            unique_id="other_entry_cable_modem_status",
        ),
        {"other_entry"},
        False,
    ),
    (
        "unattributable_orphan_row",
        _make_entity(config_entry_id=None, unique_id=None),
        {"other_entry"},
        True,
    ),
    (
        "deleted_entry_row",
        _make_entity(
            config_entry_id="deleted_entry",
            unique_id="deleted_entry_cable_modem_status",
        ),
        {"other_entry"},
        True,
    ),
    (
        "live_foreign_orphan_row",
        _make_entity(
            config_entry_id=None,
            unique_id="other_entry_cable_modem_downstream_power",
        ),
        {"other_entry"},
        False,
    ),
    (
        "other_platform_row",
        _make_entity(
            platform="sensor",
            config_entry_id="entry_abc",
            unique_id="entry_abc_cable_modem_status",
        ),
        {"other_entry"},
        False,
    ),
]


@pytest.mark.parametrize(
    ("desc", "entity_entry", "installed_ids", "expected"),
    ENTITY_REMOVAL_CASES,
    ids=[case[0] for case in ENTITY_REMOVAL_CASES],
)
def test_entity_should_remove(desc, entity_entry, installed_ids, expected):
    """Entity removal rules match target ownership and live-owner checks."""
    del desc
    assert (
        entity_should_remove(
            entity_entry,
            target_entry_id="entry_abc",
            installed_ids=installed_ids,
        )
        is expected
    )


DEVICE_REMOVAL_CASES = [
    (
        "current_entry_device",
        _make_device(identifiers={("cable_modem_monitor", "entry_abc")}),
        {"other_entry"},
        True,
    ),
    (
        "live_foreign_device",
        _make_device(identifiers={("cable_modem_monitor", "other_entry")}),
        {"other_entry"},
        False,
    ),
    (
        "deleted_entry_device",
        _make_device(identifiers={("cable_modem_monitor", "deleted_entry")}),
        {"other_entry"},
        True,
    ),
    (
        "multi_owner_live_device",
        _make_device(
            identifiers={
                ("cable_modem_monitor", "entry_abc"),
                ("cable_modem_monitor", "other_entry"),
            }
        ),
        {"other_entry"},
        True,
    ),
    (
        "other_domain_device",
        _make_device(identifiers={("other_domain", "entry_abc")}),
        {"other_entry"},
        False,
    ),
]


@pytest.mark.parametrize(
    ("desc", "device_entry", "installed_ids", "expected"),
    DEVICE_REMOVAL_CASES,
    ids=[case[0] for case in DEVICE_REMOVAL_CASES],
)
def test_device_should_remove(desc, device_entry, installed_ids, expected):
    """Device removal rules match target ownership and live-owner checks."""
    del desc
    assert (
        device_should_remove(
            device_entry,
            target_entry_id="entry_abc",
            installed_ids=installed_ids,
        )
        is expected
    )
