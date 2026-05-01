"""Registry cleanup helpers for Cable Modem Monitor.

Centralizes ownership matching for entity and device registry cleanup so
reset, remove-entry, and diagnostics use the same rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
)

from .const import DOMAIN


@dataclass(slots=True)
class RegistryCleanupSummary:
    """Summary of registry cleanup actions for one config entry."""

    removed_entity_ids: list[str] = field(default_factory=list)
    removed_entity_domains: dict[str, int] = field(default_factory=dict)
    removed_device_ids: list[str] = field(default_factory=list)
    unlinked_device_ids: list[str] = field(default_factory=list)


def _entity_unique_id_prefix(entry_id: str) -> str:
    """Return the stable unique-id prefix for one config entry."""
    return f"{entry_id}_"


def installed_entry_ids(
    hass: HomeAssistant,
    *,
    exclude_entry_id: str | None = None,
) -> set[str]:
    """Return installed Cable Modem Monitor config-entry IDs."""
    return {
        config_entry.entry_id
        for config_entry in hass.config_entries.async_entries(DOMAIN)
        if config_entry.entry_id != exclude_entry_id
    }


def _matching_entry_id_from_unique_id(
    unique_id: str | None,
    candidate_entry_ids: set[str],
) -> str | None:
    """Return the candidate entry ID matched by a stable unique ID prefix."""
    if not unique_id:
        return None

    for entry_id in candidate_entry_ids:
        if unique_id.startswith(_entity_unique_id_prefix(entry_id)):
            return entry_id

    return None


def _entity_should_remove(
    entity_entry: er.RegistryEntry,
    *,
    target_entry_id: str,
    installed_ids: set[str],
) -> bool:
    """Return whether an entity should be removed by domain cleanup."""
    if entity_entry.platform != DOMAIN:
        return False

    candidate_entry_ids = installed_ids | {target_entry_id}
    owner_from_config = (
        entity_entry.config_entry_id
        if entity_entry.config_entry_id in candidate_entry_ids
        else None
    )
    owner_from_unique_id = _matching_entry_id_from_unique_id(
        entity_entry.unique_id,
        candidate_entry_ids,
    )

    if target_entry_id in {owner_from_config, owner_from_unique_id}:
        return True

    return not (
        owner_from_config in installed_ids
        or owner_from_unique_id in installed_ids
    )


def _device_domain_entry_ids(device_entry: dr.DeviceEntry) -> set[str]:
    """Return Cable Modem Monitor entry IDs referenced by one device."""
    return {
        entry_id
        for domain, entry_id in device_entry.identifiers
        if domain == DOMAIN
    }


def _device_should_remove(
    device_entry: dr.DeviceEntry,
    *,
    target_entry_id: str,
    installed_ids: set[str],
) -> bool:
    """Return whether a device should be removed by domain cleanup."""
    domain_entry_ids = _device_domain_entry_ids(device_entry)
    if not domain_entry_ids:
        return False

    if target_entry_id in domain_entry_ids:
        return True

    return not domain_entry_ids <= installed_ids


def cleanup_owned_entities(
    entity_registry: er.EntityRegistry,
    target_entry_id: str,
    installed_ids: set[str],
) -> RegistryCleanupSummary:
    """Remove target-owned and invalid same-domain entity registry rows."""
    summary = RegistryCleanupSummary()

    for entity_entry in entity_registry.entities.values():
        if not _entity_should_remove(
            entity_entry,
            target_entry_id=target_entry_id,
            installed_ids=installed_ids,
        ):
            continue

        entity_registry.async_remove(entity_entry.entity_id)
        summary.removed_entity_ids.append(entity_entry.entity_id)
        summary.removed_entity_domains[entity_entry.domain] = (
            summary.removed_entity_domains.get(entity_entry.domain, 0) + 1
        )

    return summary


def cleanup_owned_devices(
    device_registry: dr.DeviceRegistry,
    target_entry_id: str,
    installed_ids: set[str],
    summary: RegistryCleanupSummary,
) -> RegistryCleanupSummary:
    """Remove target-owned and invalid same-domain device registry rows."""
    for device_entry in list(device_registry.devices.values()):
        if not _device_should_remove(
            device_entry,
            target_entry_id=target_entry_id,
            installed_ids=installed_ids,
        ):
            continue

        device_registry.async_remove_device(device_entry.id)
        summary.removed_device_ids.append(device_entry.id)

    return summary


def cleanup_owned_registry_rows(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry | None,
    target_entry_id: str,
) -> RegistryCleanupSummary:
    """Remove target-owned and invalid same-domain registry rows."""
    active_entry_ids = installed_entry_ids(hass, exclude_entry_id=target_entry_id)
    summary = cleanup_owned_entities(
        entity_registry,
        target_entry_id,
        active_entry_ids,
    )

    if device_registry is not None:
        cleanup_owned_devices(
            device_registry,
            target_entry_id,
            active_entry_ids,
            summary,
        )

    return summary


def _upstream_family_from_unique_id(
    unique_id: str | None,
    target_entry_id: str,
) -> str | None:
    """Return the upstream channel family encoded in an ID-mode unique ID."""
    if not unique_id:
        return None

    prefix = f"{target_entry_id}_cable_modem_us_"
    if not unique_id.startswith(prefix):
        return None

    family, separator, _ = unique_id[len(prefix) :].partition("_ch_")
    if not separator or not family:
        return None

    return family


def cleanup_obsolete_upstream_family_entities(
    entity_registry: er.EntityRegistry,
    *,
    target_entry_id: str,
    current_families: set[str],
) -> list[str]:
    """Remove stale typed-upstream entity rows for one entry.

    This targets only ID-mode upstream entity unique IDs whose encoded
    family no longer appears in the current runtime upstream channel set.
    """
    if not current_families:
        return []

    removed_entity_ids: list[str] = []

    for entity_entry in entity_registry.entities.values():
        if entity_entry.platform != DOMAIN:
            continue

        owner_from_unique_id = _matching_entry_id_from_unique_id(
            entity_entry.unique_id,
            {target_entry_id},
        )
        if owner_from_unique_id != target_entry_id:
            continue

        upstream_family = _upstream_family_from_unique_id(
            entity_entry.unique_id,
            target_entry_id,
        )
        if upstream_family is None or upstream_family in current_families:
            continue

        entity_registry.async_remove(entity_entry.entity_id)
        removed_entity_ids.append(entity_entry.entity_id)

    return removed_entity_ids
