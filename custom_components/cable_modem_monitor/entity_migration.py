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


def _build_new_name(old_name: str) -> str | None:
    """Build new entity/statistic name from old name.

    Returns None if name doesn't match migration pattern (false positive).
    """
    if "_ds_ch_" in old_name:
        return old_name.replace("_ds_ch_", "_ds_qam_ch_")
    if "_us_ch_" in old_name:
        return old_name.replace("_us_ch_", "_us_atdma_ch_")
    return None


def _migrate_states_meta(cursor: sqlite3.Cursor) -> int:
    """Migrate states_meta table entries to new naming scheme."""
    cursor.execute(
        "SELECT metadata_id, entity_id FROM states_meta "
        "WHERE entity_id LIKE 'sensor.cable_modem_ds_ch_%' "
        "OR entity_id LIKE 'sensor.cable_modem_us_ch_%'"
    )
    old_entities = cursor.fetchall()
    migrated = 0

    for old_id, old_name in old_entities:
        new_name = _build_new_name(old_name)
        if new_name is None:
            continue

        cursor.execute("SELECT metadata_id FROM states_meta WHERE entity_id = ?", (new_name,))
        row = cursor.fetchone()

        if row:
            # Merge old states into new, then delete old
            cursor.execute("UPDATE states SET metadata_id = ? WHERE metadata_id = ?", (row[0], old_id))
            count = cursor.rowcount
            cursor.execute("DELETE FROM states_meta WHERE metadata_id = ?", (old_id,))
            _LOGGER.debug("Merged recorder history: %s -> %s (%d states)", old_name, new_name, count)
        else:
            # Rename old entity
            cursor.execute("UPDATE states_meta SET entity_id = ? WHERE metadata_id = ?", (new_name, old_id))
            _LOGGER.debug("Renamed recorder history: %s -> %s", old_name, new_name)

        migrated += 1

    return migrated


def _migrate_statistics_meta(cursor: sqlite3.Cursor) -> int:
    """Migrate statistics_meta table entries to new naming scheme."""
    # Check if statistics_meta table exists (may not exist in minimal/test DBs)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='statistics_meta'")
    if not cursor.fetchone():
        return 0

    cursor.execute(
        "SELECT id, statistic_id FROM statistics_meta "
        "WHERE statistic_id LIKE 'sensor.cable_modem_ds_ch_%' "
        "OR statistic_id LIKE 'sensor.cable_modem_us_ch_%'"
    )
    old_stats = cursor.fetchall()
    migrated = 0

    for old_id, old_name in old_stats:
        new_name = _build_new_name(old_name)
        if new_name is None:
            continue

        cursor.execute("SELECT id FROM statistics_meta WHERE statistic_id = ?", (new_name,))
        row = cursor.fetchone()

        if row:
            # Merge old stats into new, then delete old
            # First, delete any old entries that conflict with new (same start_ts)
            new_id = row[0]
            cursor.execute(
                "DELETE FROM statistics WHERE metadata_id = ? AND start_ts IN "
                "(SELECT start_ts FROM statistics WHERE metadata_id = ?)",
                (old_id, new_id),
            )
            cursor.execute(
                "DELETE FROM statistics_short_term WHERE metadata_id = ? AND start_ts IN "
                "(SELECT start_ts FROM statistics_short_term WHERE metadata_id = ?)",
                (old_id, new_id),
            )
            # Now merge remaining old entries into new
            cursor.execute("UPDATE statistics SET metadata_id = ? WHERE metadata_id = ?", (new_id, old_id))
            cursor.execute("UPDATE statistics_short_term SET metadata_id = ? WHERE metadata_id = ?", (new_id, old_id))
            cursor.execute("DELETE FROM statistics_meta WHERE id = ?", (old_id,))
            _LOGGER.debug("Merged statistics: %s -> %s", old_name, new_name)
        else:
            # Rename old statistic
            cursor.execute("UPDATE statistics_meta SET statistic_id = ? WHERE id = ?", (new_name, old_id))
            _LOGGER.debug("Renamed statistics: %s -> %s", old_name, new_name)

        migrated += 1

    return migrated


def _migrate_recorder_history_sync(db_path: str) -> int:
    """Migrate recorder history from old entity IDs to new naming scheme.

    This is a synchronous function meant to be run via executor.
    It updates both states_meta and statistics_meta tables to rename old
    entity_ids to new ones, preserving all historical data.

    Args:
        db_path: Path to the Home Assistant SQLite database.

    Returns:
        Number of entities migrated.
    """
    if not Path(db_path).exists():
        _LOGGER.debug("Recorder database not found at %s, skipping migration", db_path)
        return 0

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        migrated = _migrate_states_meta(cursor) + _migrate_statistics_meta(cursor)

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
