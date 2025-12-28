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
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def _migrate_recorder_history_sync(db_path: str) -> int:
    """Migrate recorder history from old entity IDs to new naming scheme.

    This is a synchronous function meant to be run via executor.
    It updates the states_meta table to rename old entity_ids to new ones,
    preserving all historical data under the new entity names.

    For each old entity:
    - If new entity already exists in states_meta: merge states into new, delete old
    - If new entity doesn't exist: rename old entity_id to new

    Args:
        db_path: Path to the Home Assistant SQLite database.

    Returns:
        Number of entities migrated.
    """
    # Check if database exists
    if not Path(db_path).exists():
        _LOGGER.debug("Recorder database not found at %s, skipping migration", db_path)
        return 0

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Find old-style entity IDs in states_meta
        cursor.execute(
            "SELECT metadata_id, entity_id FROM states_meta "
            "WHERE entity_id LIKE 'sensor.cable_modem_ds_ch_%' "
            "OR entity_id LIKE 'sensor.cable_modem_us_ch_%'"
        )
        old_entities = cursor.fetchall()

        if not old_entities:
            conn.close()
            return 0

        migrated = 0
        for old_id, old_name in old_entities:
            # Build new entity name (skip false positives from SQL LIKE pattern)
            # SQL _ is a single-char wildcard, so ds_ch_% also matches ds_channel_count
            if "_ds_ch_" in old_name:
                new_name = old_name.replace("_ds_ch_", "_ds_qam_ch_")
            elif "_us_ch_" in old_name:
                new_name = old_name.replace("_us_ch_", "_us_atdma_ch_")
            else:
                # False positive (e.g., ds_channel_count) - skip
                continue

            # Check if new entity already exists in states_meta
            cursor.execute(
                "SELECT metadata_id FROM states_meta WHERE entity_id = ?",
                (new_name,),
            )
            row = cursor.fetchone()

            if row:
                # New entity exists - merge old states into new, then delete old
                new_id = row[0]
                cursor.execute(
                    "UPDATE states SET metadata_id = ? WHERE metadata_id = ?",
                    (new_id, old_id),
                )
                count = cursor.rowcount
                cursor.execute(
                    "DELETE FROM states_meta WHERE metadata_id = ?",
                    (old_id,),
                )
                _LOGGER.debug(
                    "Merged recorder history: %s -> %s (%d states)",
                    old_name,
                    new_name,
                    count,
                )
            else:
                # New entity doesn't exist - just rename old entity
                cursor.execute(
                    "UPDATE states_meta SET entity_id = ? WHERE metadata_id = ?",
                    (new_name, old_id),
                )
                _LOGGER.debug(
                    "Renamed recorder history: %s -> %s",
                    old_name,
                    new_name,
                )

            migrated += 1

        conn.commit()
        conn.close()

        if migrated > 0:
            _LOGGER.info(
                "Migrated recorder history for %d entities to new naming scheme",
                migrated,
            )

        return migrated

    except sqlite3.Error as err:
        _LOGGER.error("Failed to migrate recorder history: %s", err)
        return 0


async def _migrate_recorder_history(hass: HomeAssistant) -> int:
    """Migrate recorder history using recorder's database executor.

    Uses the recorder's dedicated thread pool for database operations,
    which is the recommended pattern per Home Assistant guidelines.

    Falls back to hass.async_add_executor_job if recorder is not available.

    Returns number of entities migrated.
    """
    db_path = hass.config.path("home-assistant_v2.db")

    try:
        # Try to use recorder's executor (preferred method)
        from homeassistant.components.recorder import get_instance

        recorder = get_instance(hass)
        result: int = await recorder.async_add_executor_job(_migrate_recorder_history_sync, db_path)
        return result
    except (KeyError, ImportError):
        # Recorder not available - fall back to general executor
        _LOGGER.debug("Recorder not available, using general executor for migration")
        result = await hass.async_add_executor_job(_migrate_recorder_history_sync, db_path)
        return result


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

        direction_long = match.group(1)  # "downstream" or "upstream"
        channel_id = match.group(2)  # e.g., "1", "32"
        metric = match.group(3)  # e.g., "power", "snr", "frequency"

        # Map long direction names to short names
        direction_short = "ds" if direction_long == "downstream" else "us"

        # Determine channel type based on direction (DOCSIS 3.0 only has one type per direction)
        channel_type = "qam" if direction_short == "ds" else "atdma"

        # Build new unique_id with channel type
        # Old: {entry_id}_cable_modem_downstream_1_power
        # New: {entry_id}_cable_modem_ds_qam_ch_1_power
        new_unique_id = f"{entry_id}_cable_modem_{direction_short}_{channel_type}_ch_{channel_id}_{metric}"

        # Build new entity_id (the user-visible part after sensor.)
        # Old: sensor.cable_modem_ds_ch_1_power
        # New: sensor.cable_modem_ds_qam_ch_1_power
        old_entity_suffix = f"cable_modem_{direction_short}_ch_{channel_id}_{metric}"
        new_entity_suffix = f"cable_modem_{direction_short}_{channel_type}_ch_{channel_id}_{metric}"

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


async def async_migrate_docsis30_entities(
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
    # Old format: {entry_id}_cable_modem_downstream_{id}_{metric}
    # New format: {entry_id}_cable_modem_ds_qam_ch_{id}_{metric}
    old_pattern = re.compile(rf"^{re.escape(entry.entry_id)}_cable_modem_(downstream|upstream)_(\d+)_(\w+)$")

    entities_to_migrate = _find_entities_to_migrate(entity_registry, entry.entry_id, old_pattern)

    migrated_count = 0
    if entities_to_migrate:
        _LOGGER.info(
            "Migrating %d entities to new naming scheme for DOCSIS 3.0 modem",
            len(entities_to_migrate),
        )

        for entity_entry, new_unique_id, new_entity_id in entities_to_migrate:
            try:
                if _migrate_single_entity(entity_registry, entity_entry, new_unique_id, new_entity_id):
                    migrated_count += 1
            except ValueError as err:
                _LOGGER.warning("Failed to migrate entity %s: %s", entity_entry.entity_id, err)

        if migrated_count > 0:
            _LOGGER.info("Successfully migrated %d entities to new naming scheme", migrated_count)
    else:
        _LOGGER.debug("No entity registry entries need migration for DOCSIS 3.0 modem")

    # Always migrate recorder history (states_meta table)
    # This preserves historical data under the new entity IDs
    # Runs even if entity registry migration found nothing - handles users
    # who already upgraded but have orphaned history from pre-fix versions
    recorder_migrated = await _migrate_recorder_history(hass)
    if recorder_migrated > 0:
        _LOGGER.info(
            "Migrated recorder history for %d entities",
            recorder_migrated,
        )

    return migrated_count + recorder_migrated
