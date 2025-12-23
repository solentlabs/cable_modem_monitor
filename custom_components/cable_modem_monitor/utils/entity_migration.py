"""Entity migration utilities for DOCSIS 3.0 modems.

Handles automatic migration of entity IDs when upgrading from pre-v3.11 naming
to the new channel_type-aware naming scheme.

v3.11 added channel_type to entity IDs for DOCSIS 3.1 disambiguation:
- Old: sensor.cable_modem_ds_ch_1_power
- New: sensor.cable_modem_ds_qam_ch_1_power

For DOCSIS 3.0 modems, the mapping is unambiguous:
- Downstream channels are always QAM
- Upstream channels are always ATDMA

For DOCSIS 3.1 modems, we cannot automatically migrate because the old
"ch_1" could have been either QAM or OFDM.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def _find_entities_to_migrate(
    entity_registry: Any,
    entry_id: str,
    old_pattern: re.Pattern,
) -> list[tuple[Any, str, str]]:
    """Find all entities that need migration.

    Returns list of (entity_entry, new_unique_id, new_entity_id) tuples.
    """
    entities_to_migrate: list[tuple[Any, str, str]] = []

    for entity_entry in entity_registry.entities.values():
        if entity_entry.config_entry_id != entry_id:
            continue

        unique_id = entity_entry.unique_id
        if not unique_id:
            continue

        match = old_pattern.match(unique_id)
        if not match:
            continue

        direction = match.group(1)  # "ds" or "us"
        channel_id = match.group(2)  # e.g., "1", "32"
        metric = match.group(3)  # e.g., "power", "snr", "frequency"

        # Determine channel type based on direction (DOCSIS 3.0 only has one type per direction)
        channel_type = "qam" if direction == "ds" else "atdma"

        # Build new unique_id with channel type
        new_unique_id = f"{entry_id}_cable_modem_{direction}_{channel_type}_ch_{channel_id}_{metric}"

        # Build new entity_id (the user-visible part after sensor.)
        old_entity_suffix = f"cable_modem_{direction}_ch_{channel_id}_{metric}"
        new_entity_suffix = f"cable_modem_{direction}_{channel_type}_ch_{channel_id}_{metric}"

        # Only migrate if entity_id follows the expected pattern
        if entity_entry.entity_id.endswith(old_entity_suffix):
            new_entity_id = entity_entry.entity_id.replace(old_entity_suffix, new_entity_suffix)
            entities_to_migrate.append((entity_entry, new_unique_id, new_entity_id))

    return entities_to_migrate


def _migrate_single_entity(
    entity_registry: Any,
    entity_entry: Any,
    new_unique_id: str,
    new_entity_id: str,
) -> bool:
    """Migrate a single entity to new naming scheme.

    Returns True if migration succeeded, False otherwise.
    """
    # Check if an entity with the new unique_id already exists
    existing = entity_registry.async_get_entity_id(entity_entry.domain, entity_entry.platform, new_unique_id)
    if existing:
        _LOGGER.debug(
            "Entity with new unique_id already exists, removing old entity: %s",
            entity_entry.entity_id,
        )
        entity_registry.async_remove(entity_entry.entity_id)
        return True

    # Update unique_id first (this is what HA uses for identity)
    entity_registry.async_update_entity(
        entity_entry.entity_id,
        new_unique_id=new_unique_id,
    )

    # Now update entity_id if it changed and new ID is available
    if new_entity_id != entity_entry.entity_id and not entity_registry.async_get(new_entity_id):
        entity_registry.async_update_entity(
            entity_entry.entity_id,
            new_entity_id=new_entity_id,
        )
        _LOGGER.debug(
            "Migrated entity: %s -> %s (unique_id: %s)",
            entity_entry.entity_id,
            new_entity_id,
            new_unique_id,
        )
    else:
        _LOGGER.debug("Updated unique_id for entity: %s", entity_entry.entity_id)

    return True


def migrate_docsis30_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    docsis_version: str | None,
) -> int:
    """Migrate old entity IDs to new naming scheme for DOCSIS 3.0 modems.

    This function automatically migrates old entity unique_ids and entity_ids
    for DOCSIS 3.0 modems to preserve history and user customizations.

    Args:
        hass: Home Assistant instance
        entry: Config entry for the integration
        docsis_version: DOCSIS version from config entry data (e.g., "3.0", "3.1")

    Returns:
        Number of entities migrated.
    """
    from homeassistant.helpers import entity_registry as er_module

    # Only migrate DOCSIS 3.0 modems (unambiguous mapping)
    # For DOCSIS 3.1+, we can't know if old "ch_1" was QAM or OFDM
    if docsis_version != "3.0":
        if docsis_version:
            _LOGGER.debug(
                "Skipping entity migration for DOCSIS %s modem (only 3.0 is auto-migratable)",
                docsis_version,
            )
        return 0

    entity_registry = er_module.async_get(hass)

    # Pattern to match old-style entity unique_ids without channel type
    # Format: {entry_id}_cable_modem_{ds|us}_ch_{id}_{metric}
    old_pattern = re.compile(rf"^{re.escape(entry.entry_id)}_cable_modem_(ds|us)_ch_(\d+)_(\w+)$")

    entities_to_migrate = _find_entities_to_migrate(entity_registry, entry.entry_id, old_pattern)

    if not entities_to_migrate:
        _LOGGER.debug("No entities need migration for DOCSIS 3.0 modem")
        return 0

    _LOGGER.info(
        "Migrating %d entities to new naming scheme for DOCSIS 3.0 modem",
        len(entities_to_migrate),
    )

    migrated_count = 0
    for entity_entry, new_unique_id, new_entity_id in entities_to_migrate:
        try:
            if _migrate_single_entity(entity_registry, entity_entry, new_unique_id, new_entity_id):
                migrated_count += 1
        except ValueError as err:
            _LOGGER.warning("Failed to migrate entity %s: %s", entity_entry.entity_id, err)

    if migrated_count > 0:
        _LOGGER.info("Successfully migrated %d entities to new naming scheme", migrated_count)

    return migrated_count
