"""Caller-agnostic entity reconciliation planning.

This module computes entity-reconciliation plans from current registry state
and one or more family descriptors. It stays pure where practical: callers
decide when a plan is built and whether any resulting removals or deferred
creations are applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from .const import ChannelIdentity
from .entity_registry_helpers import target_owned_entity_rows

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.helpers import entity_registry as er
    from solentlabs.cable_modem_monitor_core.orchestration.models import ModemSnapshot


class EntityReconciliationFamily(Protocol):
    """Contract for a reconcilable entity family."""

    @property
    def name(self) -> str: ...

    def expected_unique_ids(self, entry_id: str) -> set[str]: ...

    def manages(self, entry_id: str, unique_id: str | None) -> bool: ...


@dataclass(frozen=True, slots=True)
class EntityReconciliationFamilyPlan:
    """Delta for one reconcilable entity family."""

    name: str
    keep_entity_ids: tuple[str, ...]
    remove_entity_ids: tuple[str, ...]
    create_later_unique_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EntityReconciliationPlan:
    """Combined reconciliation delta across all supplied families."""

    family_plans: tuple[EntityReconciliationFamilyPlan, ...]
    keep_entity_ids: tuple[str, ...]
    remove_entity_ids: tuple[str, ...]
    create_later_unique_ids: tuple[str, ...]
    unmanaged_entity_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TypedMetricEntityFamily:
    """Concrete family for typed channel-metric entities in ID mode."""

    name: str
    dir_code: str
    channels: tuple[Mapping[str, Any], ...]
    metric_fields: tuple[str, ...]
    always_present_fields: frozenset[str]

    def expected_unique_ids(self, entry_id: str) -> set[str]:
        """Return typed-channel metric unique IDs expected from current state."""
        expected: set[str] = set()
        prefix = f"{entry_id}_cable_modem_{self.dir_code}_"

        for channel in self.channels:
            channel_type = channel.get("channel_type")
            channel_id = channel.get("channel_id")
            if channel_type in (None, "") or channel_id in (None, ""):
                continue

            for field in self.metric_fields:
                if field in self.always_present_fields or field in channel:
                    expected.add(f"{prefix}{channel_type}_ch_{channel_id}_{field}")

        return expected

    def manages(self, entry_id: str, unique_id: str | None) -> bool:
        """Return whether the row belongs to this typed direction family."""
        if unique_id is None:
            return False

        return unique_id.startswith(f"{entry_id}_cable_modem_{self.dir_code}_") and "_ch_" in unique_id


def build_channel_metric_entity_families(
    snapshot: ModemSnapshot | None,
    identity_mode: ChannelIdentity,
) -> tuple[EntityReconciliationFamily, ...]:
    """Return real typed channel-metric families from current runtime data."""
    if identity_mode != ChannelIdentity.ID or snapshot is None or snapshot.modem_data is None:
        return ()

    from .sensor import _DS_ALWAYS_FIELDS, _DS_METRICS, _US_ALWAYS_FIELDS, _US_METRICS

    modem_data = snapshot.modem_data
    downstream_fields = tuple(field for field, *_ in _DS_METRICS)
    upstream_fields = tuple(field for field, *_ in _US_METRICS)

    return (
        TypedMetricEntityFamily(
            name="downstream-channel-metrics",
            dir_code="ds",
            channels=tuple(modem_data.get("downstream", [])),
            metric_fields=downstream_fields,
            always_present_fields=_DS_ALWAYS_FIELDS,
        ),
        TypedMetricEntityFamily(
            name="upstream-channel-metrics",
            dir_code="us",
            channels=tuple(modem_data.get("upstream", [])),
            metric_fields=upstream_fields,
            always_present_fields=_US_ALWAYS_FIELDS,
        ),
    )


def build_entity_reconciliation_plan(
    *,
    entry_id: str,
    entity_registry: er.EntityRegistry,
    families: tuple[EntityReconciliationFamily, ...],
) -> EntityReconciliationPlan:
    """Build an entity-reconciliation plan for the target entry and family set."""
    target_rows = target_owned_entity_rows(entity_registry, entry_id)
    unmatched_rows = {row.entity_id: row for row in target_rows}
    family_plans: list[EntityReconciliationFamilyPlan] = []

    keep_entity_ids: set[str] = set()
    remove_entity_ids: set[str] = set()
    create_later_unique_ids: set[str] = set()

    for family in families:
        expected_unique_ids = family.expected_unique_ids(entry_id)
        managed_rows = [row for row in target_rows if family.manages(entry_id, row.unique_id)]
        existing_by_unique_id = {row.unique_id: row for row in managed_rows if row.unique_id is not None}

        family_keep = tuple(
            sorted(
                row.entity_id for unique_id, row in existing_by_unique_id.items() if unique_id in expected_unique_ids
            )
        )
        family_remove = tuple(
            sorted(
                row.entity_id
                for unique_id, row in existing_by_unique_id.items()
                if unique_id not in expected_unique_ids
            )
        )
        family_create = tuple(sorted(expected_unique_ids - set(existing_by_unique_id)))

        keep_entity_ids.update(family_keep)
        remove_entity_ids.update(family_remove)
        create_later_unique_ids.update(family_create)

        for row in managed_rows:
            unmatched_rows.pop(row.entity_id, None)

        family_plans.append(
            EntityReconciliationFamilyPlan(
                name=family.name,
                keep_entity_ids=family_keep,
                remove_entity_ids=family_remove,
                create_later_unique_ids=family_create,
            )
        )

    return EntityReconciliationPlan(
        family_plans=tuple(family_plans),
        keep_entity_ids=tuple(sorted(keep_entity_ids)),
        remove_entity_ids=tuple(sorted(remove_entity_ids)),
        create_later_unique_ids=tuple(sorted(create_later_unique_ids)),
        unmanaged_entity_ids=tuple(sorted(unmatched_rows)),
    )


__all__ = [
    "EntityReconciliationFamily",
    "EntityReconciliationFamilyPlan",
    "EntityReconciliationPlan",
    "TypedMetricEntityFamily",
    "build_channel_metric_entity_families",
    "build_entity_reconciliation_plan",
]
