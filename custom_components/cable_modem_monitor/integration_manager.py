"""Entry-scoped lifecycle ownership for the HA adapter.

This manager owns shared entity lifecycle policy for one config entry. It
routes startup reconciliation and destructive cleanup through helper-level
registry mechanics without letting those helpers become policy owners.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
)

from .const import ChannelIdentity
from .entity_reconciliation import (
    EntityReconciliationFamily,
    EntityReconciliationPlan,
    build_channel_metric_entity_families,
    build_entity_reconciliation_plan,
)
from .entity_registry_helpers import (
    RegistryCleanupSummary,
    cleanup_owned_entities,
    cleanup_owned_registry_rows,
    installed_entry_ids,
)

if TYPE_CHECKING:
    from solentlabs.cable_modem_monitor_core.orchestration.models import ModemSnapshot


class CableModemIntegrationManager:
    """Own shared entry-scoped lifecycle policy for one config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the lifecycle owner for one config entry."""
        self.hass = hass
        self.entry_id = entry_id

    def reconcile_startup_entities(
        self,
        snapshot: ModemSnapshot | None,
        identity_mode: ChannelIdentity,
        *,
        automatic_enabled: bool = True,
        force: bool = False,
    ) -> list[str]:
        """Remove stale same-entry typed channel rows before platform setup."""
        if not automatic_enabled and not force:
            return []

        if identity_mode != ChannelIdentity.ID:
            return []

        families = build_channel_metric_entity_families(snapshot, identity_mode)
        if not families:
            return []

        plan = self.build_entity_reconciliation_plan(families=families)

        if not plan.remove_entity_ids:
            return []

        entity_registry = er.async_get(self.hass)
        for entity_id in plan.remove_entity_ids:
            entity_registry.async_remove(entity_id)

        return list(plan.remove_entity_ids)

    def cleanup_entities_for_reset(self) -> RegistryCleanupSummary:
        """Remove target-owned and invalid same-domain entities for reset."""
        return cleanup_owned_entities(
            er.async_get(self.hass),
            self.entry_id,
            installed_entry_ids(self.hass),
        )

    def cleanup_registry_rows_for_removal(self) -> RegistryCleanupSummary:
        """Remove target-owned and invalid same-domain rows for entry deletion."""
        return cleanup_owned_registry_rows(
            self.hass,
            er.async_get(self.hass),
            dr.async_get(self.hass),
            self.entry_id,
        )

    def build_entity_reconciliation_plan(
        self,
        *,
        families: tuple[EntityReconciliationFamily, ...],
    ) -> EntityReconciliationPlan:
        """Build an entity-reconciliation plan for the target entry."""
        return build_entity_reconciliation_plan(
            entry_id=self.entry_id,
            entity_registry=er.async_get(self.hass),
            families=families,
        )
