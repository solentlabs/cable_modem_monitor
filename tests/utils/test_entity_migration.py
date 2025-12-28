"""Tests for entity migration utilities."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.cable_modem_monitor.utils.entity_migration import (
    _migrate_recorder_history_sync,
    async_migrate_docsis30_entities,
)


class TestMigrateDocsis30Entities:
    """Tests for async_migrate_docsis30_entities function."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        return MagicMock()

    @pytest.fixture
    def mock_entry(self):
        """Create a mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = {}
        return entry

    @pytest.mark.asyncio
    async def test_skips_non_docsis30_modems(self, mock_hass, mock_entry):
        """Test that migration is skipped for non-DOCSIS 3.0 modems."""
        # DOCSIS 3.1
        result = await async_migrate_docsis30_entities(mock_hass, mock_entry, "3.1")
        assert result == 0

        # No version specified
        result = await async_migrate_docsis30_entities(mock_hass, mock_entry, None)
        assert result == 0

        # DOCSIS 4.0
        result = await async_migrate_docsis30_entities(mock_hass, mock_entry, "4.0")
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_entities_to_migrate(self, mock_hass, mock_entry):
        """Test that 0 is returned when there are no entities to migrate."""
        with (
            patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get,
            patch(
                "custom_components.cable_modem_monitor.utils.entity_migration._migrate_recorder_history",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            mock_registry = MagicMock()
            mock_registry.entities.values.return_value = []
            mock_async_get.return_value = mock_registry

            result = await async_migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 0

    @pytest.mark.asyncio
    async def test_migrates_downstream_entities(self, mock_hass, mock_entry):
        """Test migration of downstream channel entities."""
        with (
            patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get,
            patch(
                "custom_components.cable_modem_monitor.utils.entity_migration._migrate_recorder_history",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            mock_registry = MagicMock()

            # Create old-style downstream entity
            # Old format: unique_id uses "downstream", entity_id uses "ds_ch"
            mock_entity = MagicMock()
            mock_entity.config_entry_id = "test_entry_id"
            mock_entity.unique_id = "test_entry_id_cable_modem_downstream_1_power"
            mock_entity.entity_id = "sensor.cable_modem_ds_ch_1_power"
            mock_entity.domain = "sensor"
            mock_entity.platform = "cable_modem_monitor"

            mock_registry.entities.values.return_value = [mock_entity]
            mock_registry.async_get_entity_id.return_value = None  # No existing entity
            mock_registry.async_get.return_value = None  # Entity ID available
            mock_async_get.return_value = mock_registry

            result = await async_migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 1
            mock_registry.async_update_entity.assert_called()

            # Verify the new unique_id contains 'qam' for downstream
            calls = mock_registry.async_update_entity.call_args_list
            assert any("qam" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_migrates_upstream_entities(self, mock_hass, mock_entry):
        """Test migration of upstream channel entities."""
        with (
            patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get,
            patch(
                "custom_components.cable_modem_monitor.utils.entity_migration._migrate_recorder_history",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            mock_registry = MagicMock()

            # Create old-style upstream entity
            # Old format: unique_id uses "upstream", entity_id uses "us_ch"
            mock_entity = MagicMock()
            mock_entity.config_entry_id = "test_entry_id"
            mock_entity.unique_id = "test_entry_id_cable_modem_upstream_3_power"
            mock_entity.entity_id = "sensor.cable_modem_us_ch_3_power"
            mock_entity.domain = "sensor"
            mock_entity.platform = "cable_modem_monitor"

            mock_registry.entities.values.return_value = [mock_entity]
            mock_registry.async_get_entity_id.return_value = None
            mock_registry.async_get.return_value = None
            mock_async_get.return_value = mock_registry

            result = await async_migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 1
            mock_registry.async_update_entity.assert_called()

            # Verify the new unique_id contains 'atdma' for upstream
            calls = mock_registry.async_update_entity.call_args_list
            assert any("atdma" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_removes_old_entity_when_new_exists(self, mock_hass, mock_entry):
        """Test that old entity is removed when new unique_id already exists."""
        with (
            patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get,
            patch(
                "custom_components.cable_modem_monitor.utils.entity_migration._migrate_recorder_history",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            mock_registry = MagicMock()

            # Old format: unique_id uses "downstream", entity_id uses "ds_ch"
            mock_entity = MagicMock()
            mock_entity.config_entry_id = "test_entry_id"
            mock_entity.unique_id = "test_entry_id_cable_modem_downstream_1_power"
            mock_entity.entity_id = "sensor.cable_modem_ds_ch_1_power"
            mock_entity.domain = "sensor"
            mock_entity.platform = "cable_modem_monitor"

            mock_registry.entities.values.return_value = [mock_entity]
            # Simulate new entity already exists
            mock_registry.async_get_entity_id.return_value = "sensor.cable_modem_ds_qam_ch_1_power"
            mock_async_get.return_value = mock_registry

            result = await async_migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 1
            mock_registry.async_remove.assert_called_once_with("sensor.cable_modem_ds_ch_1_power")

    @pytest.mark.asyncio
    async def test_skips_entities_from_other_config_entries(self, mock_hass, mock_entry):
        """Test that entities from other config entries are skipped."""
        with (
            patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get,
            patch(
                "custom_components.cable_modem_monitor.utils.entity_migration._migrate_recorder_history",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            mock_registry = MagicMock()

            # Entity from different config entry - should be skipped
            mock_entity = MagicMock()
            mock_entity.config_entry_id = "other_entry_id"  # Different entry
            mock_entity.unique_id = "other_entry_id_cable_modem_downstream_1_power"
            mock_entity.entity_id = "sensor.cable_modem_ds_ch_1_power"

            mock_registry.entities.values.return_value = [mock_entity]
            mock_async_get.return_value = mock_registry

            result = await async_migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 0

    @pytest.mark.asyncio
    async def test_skips_already_migrated_entities(self, mock_hass, mock_entry):
        """Test that entities with new naming scheme are skipped."""
        with (
            patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get,
            patch(
                "custom_components.cable_modem_monitor.utils.entity_migration._migrate_recorder_history",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            mock_registry = MagicMock()

            # Entity already has new naming scheme with channel type
            mock_entity = MagicMock()
            mock_entity.config_entry_id = "test_entry_id"
            mock_entity.unique_id = "test_entry_id_cable_modem_ds_qam_ch_1_power"
            mock_entity.entity_id = "sensor.cable_modem_ds_qam_ch_1_power"

            mock_registry.entities.values.return_value = [mock_entity]
            mock_async_get.return_value = mock_registry

            result = await async_migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 0

    @pytest.mark.asyncio
    async def test_handles_multiple_entities(self, mock_hass, mock_entry):
        """Test migration of multiple entities at once."""
        with (
            patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get,
            patch(
                "custom_components.cable_modem_monitor.utils.entity_migration._migrate_recorder_history",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            mock_registry = MagicMock()

            entities = []
            # Create 4 entities with old format
            # Old format: unique_id uses "downstream/upstream", entity_id uses "ds_ch/us_ch"
            test_cases = [
                ("downstream", "ds", 1, "power"),
                ("downstream", "ds", 1, "snr"),
                ("upstream", "us", 1, "power"),
                ("upstream", "us", 1, "frequency"),
            ]
            for direction_long, direction_short, channel, metric in test_cases:
                mock_entity = MagicMock()
                mock_entity.config_entry_id = "test_entry_id"
                mock_entity.unique_id = f"test_entry_id_cable_modem_{direction_long}_{channel}_{metric}"
                mock_entity.entity_id = f"sensor.cable_modem_{direction_short}_ch_{channel}_{metric}"
                mock_entity.domain = "sensor"
                mock_entity.platform = "cable_modem_monitor"
                entities.append(mock_entity)

            mock_registry.entities.values.return_value = entities
            mock_registry.async_get_entity_id.return_value = None
            mock_registry.async_get.return_value = None
            mock_async_get.return_value = mock_registry

            result = await async_migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 4

    @pytest.mark.asyncio
    async def test_handles_migration_error_gracefully(self, mock_hass, mock_entry):
        """Test that migration errors are handled gracefully."""
        with (
            patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get,
            patch(
                "custom_components.cable_modem_monitor.utils.entity_migration._migrate_recorder_history",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            mock_registry = MagicMock()

            # Old format: unique_id uses "downstream", entity_id uses "ds_ch"
            mock_entity = MagicMock()
            mock_entity.config_entry_id = "test_entry_id"
            mock_entity.unique_id = "test_entry_id_cable_modem_downstream_1_power"
            mock_entity.entity_id = "sensor.cable_modem_ds_ch_1_power"
            mock_entity.domain = "sensor"
            mock_entity.platform = "cable_modem_monitor"

            mock_registry.entities.values.return_value = [mock_entity]
            mock_registry.async_get_entity_id.return_value = None
            # Simulate error during update
            mock_registry.async_update_entity.side_effect = ValueError("Test error")
            mock_async_get.return_value = mock_registry

            # Should not raise, should return 0 (failed migration)
            result = await async_migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 0

    @pytest.mark.asyncio
    async def test_migrates_all_metric_types(self, mock_hass, mock_entry):
        """Test that all metric types are migrated correctly."""
        metrics = ["power", "snr", "frequency", "corrected", "uncorrected"]

        with (
            patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get,
            patch(
                "custom_components.cable_modem_monitor.utils.entity_migration._migrate_recorder_history",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            mock_registry = MagicMock()

            entities = []
            for metric in metrics:
                # Old format: unique_id uses "downstream", entity_id uses "ds_ch"
                mock_entity = MagicMock()
                mock_entity.config_entry_id = "test_entry_id"
                mock_entity.unique_id = f"test_entry_id_cable_modem_downstream_1_{metric}"
                mock_entity.entity_id = f"sensor.cable_modem_ds_ch_1_{metric}"
                mock_entity.domain = "sensor"
                mock_entity.platform = "cable_modem_monitor"
                entities.append(mock_entity)

            mock_registry.entities.values.return_value = entities
            mock_registry.async_get_entity_id.return_value = None
            mock_registry.async_get.return_value = None
            mock_async_get.return_value = mock_registry

            result = await async_migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == len(metrics)

    @pytest.mark.asyncio
    async def test_preserves_custom_entity_id(self, mock_hass, mock_entry):
        """Test that custom entity IDs that don't match pattern are preserved."""
        with (
            patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get,
            patch(
                "custom_components.cable_modem_monitor.utils.entity_migration._migrate_recorder_history",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            mock_registry = MagicMock()

            # Entity with old unique_id format but custom entity_id (user renamed)
            mock_entity = MagicMock()
            mock_entity.config_entry_id = "test_entry_id"
            mock_entity.unique_id = "test_entry_id_cable_modem_downstream_1_power"
            mock_entity.entity_id = "sensor.my_custom_power_sensor"  # User renamed
            mock_entity.domain = "sensor"
            mock_entity.platform = "cable_modem_monitor"

            mock_registry.entities.values.return_value = [mock_entity]
            mock_registry.async_get_entity_id.return_value = None
            mock_registry.async_get.return_value = None
            mock_async_get.return_value = mock_registry

            result = await async_migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            # Should not migrate entity_id, but unique_id should be updated
            # Since entity_id doesn't end with expected pattern, migration skips
            assert result == 0


class TestMigrateRecorderHistory:
    """Tests for _migrate_recorder_history_sync function."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database with states_meta table."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "home-assistant_v2.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Create states_meta table
            cursor.execute(
                """
                CREATE TABLE states_meta (
                    metadata_id INTEGER PRIMARY KEY,
                    entity_id TEXT UNIQUE NOT NULL
                )
            """
            )

            # Create states table
            cursor.execute(
                """
                CREATE TABLE states (
                    state_id INTEGER PRIMARY KEY,
                    metadata_id INTEGER,
                    state TEXT,
                    FOREIGN KEY (metadata_id) REFERENCES states_meta(metadata_id)
                )
            """
            )

            conn.commit()
            yield db_path, conn
            conn.close()

    def test_migrates_downstream_entities(self, temp_db):
        """Test migration of downstream entity history."""
        db_path, conn = temp_db
        cursor = conn.cursor()

        # Insert old-style entity
        cursor.execute(
            "INSERT INTO states_meta (entity_id) VALUES (?)",
            ("sensor.cable_modem_ds_ch_1_power",),
        )
        old_id = cursor.lastrowid

        # Insert some states
        cursor.execute(
            "INSERT INTO states (metadata_id, state) VALUES (?, ?)",
            (old_id, "5.0"),
        )
        conn.commit()

        result = _migrate_recorder_history_sync(str(db_path))

        assert result == 1

        # Verify entity was renamed
        cursor.execute("SELECT entity_id FROM states_meta WHERE metadata_id = ?", (old_id,))
        row = cursor.fetchone()
        assert row[0] == "sensor.cable_modem_ds_qam_ch_1_power"

    def test_migrates_upstream_entities(self, temp_db):
        """Test migration of upstream entity history."""
        db_path, conn = temp_db
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO states_meta (entity_id) VALUES (?)",
            ("sensor.cable_modem_us_ch_3_power",),
        )
        old_id = cursor.lastrowid
        conn.commit()

        result = _migrate_recorder_history_sync(str(db_path))

        assert result == 1

        cursor.execute("SELECT entity_id FROM states_meta WHERE metadata_id = ?", (old_id,))
        row = cursor.fetchone()
        assert row[0] == "sensor.cable_modem_us_atdma_ch_3_power"

    def test_merges_when_new_entity_exists(self, temp_db):
        """Test that old states are merged when new entity already exists."""
        db_path, conn = temp_db
        cursor = conn.cursor()

        # Insert old entity with states
        cursor.execute(
            "INSERT INTO states_meta (entity_id) VALUES (?)",
            ("sensor.cable_modem_ds_ch_1_power",),
        )
        old_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO states (metadata_id, state) VALUES (?, ?)",
            (old_id, "old_value"),
        )

        # Insert new entity
        cursor.execute(
            "INSERT INTO states_meta (entity_id) VALUES (?)",
            ("sensor.cable_modem_ds_qam_ch_1_power",),
        )
        new_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO states (metadata_id, state) VALUES (?, ?)",
            (new_id, "new_value"),
        )
        conn.commit()

        result = _migrate_recorder_history_sync(str(db_path))

        assert result == 1

        # Old entity should be deleted
        cursor.execute("SELECT * FROM states_meta WHERE entity_id = ?", ("sensor.cable_modem_ds_ch_1_power",))
        assert cursor.fetchone() is None

        # All states should now reference new entity
        cursor.execute("SELECT COUNT(*) FROM states WHERE metadata_id = ?", (new_id,))
        assert cursor.fetchone()[0] == 2  # Both old and new states

    def test_returns_zero_when_no_old_entities(self, temp_db):
        """Test that 0 is returned when there are no old entities."""
        db_path, _ = temp_db
        result = _migrate_recorder_history_sync(str(db_path))
        assert result == 0

    def test_handles_missing_database_gracefully(self):
        """Test that missing database is handled gracefully."""
        result = _migrate_recorder_history_sync("/nonexistent/path/db.db")
        assert result == 0

    def test_migrates_all_metric_types(self, temp_db):
        """Test migration of all metric types."""
        db_path, conn = temp_db
        cursor = conn.cursor()

        metrics = ["power", "snr", "frequency", "corrected", "uncorrected"]
        for metric in metrics:
            cursor.execute(
                "INSERT INTO states_meta (entity_id) VALUES (?)",
                (f"sensor.cable_modem_ds_ch_1_{metric}",),
            )
        conn.commit()

        result = _migrate_recorder_history_sync(str(db_path))

        assert result == len(metrics)

        # Verify all were renamed
        cursor.execute("SELECT entity_id FROM states_meta WHERE entity_id LIKE '%qam%'")
        assert len(cursor.fetchall()) == len(metrics)

    def test_skips_already_migrated_entities(self, temp_db):
        """Test that already-migrated entities are skipped."""
        db_path, conn = temp_db
        cursor = conn.cursor()

        # Insert entity with new naming scheme
        cursor.execute(
            "INSERT INTO states_meta (entity_id) VALUES (?)",
            ("sensor.cable_modem_ds_qam_ch_1_power",),
        )
        conn.commit()

        result = _migrate_recorder_history_sync(str(db_path))

        assert result == 0
