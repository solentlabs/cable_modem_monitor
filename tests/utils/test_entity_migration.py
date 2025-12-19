"""Tests for entity migration utilities."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.cable_modem_monitor.utils.entity_migration import (
    migrate_docsis30_entities,
)


class TestMigrateDocsis30Entities:
    """Tests for migrate_docsis30_entities function."""

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

    def test_skips_non_docsis30_modems(self, mock_hass, mock_entry):
        """Test that migration is skipped for non-DOCSIS 3.0 modems."""
        # DOCSIS 3.1
        result = migrate_docsis30_entities(mock_hass, mock_entry, "3.1")
        assert result == 0

        # No version specified
        result = migrate_docsis30_entities(mock_hass, mock_entry, None)
        assert result == 0

        # DOCSIS 4.0
        result = migrate_docsis30_entities(mock_hass, mock_entry, "4.0")
        assert result == 0

    def test_returns_zero_when_no_entities_to_migrate(self, mock_hass, mock_entry):
        """Test that 0 is returned when there are no entities to migrate."""
        with patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get:
            mock_registry = MagicMock()
            mock_registry.entities.values.return_value = []
            mock_async_get.return_value = mock_registry

            result = migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 0

    def test_migrates_downstream_entities(self, mock_hass, mock_entry):
        """Test migration of downstream channel entities."""
        with patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get:
            mock_registry = MagicMock()

            # Create old-style downstream entity
            mock_entity = MagicMock()
            mock_entity.config_entry_id = "test_entry_id"
            mock_entity.unique_id = "test_entry_id_cable_modem_ds_ch_1_power"
            mock_entity.entity_id = "sensor.cable_modem_ds_ch_1_power"
            mock_entity.domain = "sensor"
            mock_entity.platform = "cable_modem_monitor"

            mock_registry.entities.values.return_value = [mock_entity]
            mock_registry.async_get_entity_id.return_value = None  # No existing entity
            mock_registry.async_get.return_value = None  # Entity ID available
            mock_async_get.return_value = mock_registry

            result = migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 1
            mock_registry.async_update_entity.assert_called()

            # Verify the new unique_id contains 'qam' for downstream
            calls = mock_registry.async_update_entity.call_args_list
            assert any("qam" in str(call) for call in calls)

    def test_migrates_upstream_entities(self, mock_hass, mock_entry):
        """Test migration of upstream channel entities."""
        with patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get:
            mock_registry = MagicMock()

            # Create old-style upstream entity
            mock_entity = MagicMock()
            mock_entity.config_entry_id = "test_entry_id"
            mock_entity.unique_id = "test_entry_id_cable_modem_us_ch_3_power"
            mock_entity.entity_id = "sensor.cable_modem_us_ch_3_power"
            mock_entity.domain = "sensor"
            mock_entity.platform = "cable_modem_monitor"

            mock_registry.entities.values.return_value = [mock_entity]
            mock_registry.async_get_entity_id.return_value = None
            mock_registry.async_get.return_value = None
            mock_async_get.return_value = mock_registry

            result = migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 1
            mock_registry.async_update_entity.assert_called()

            # Verify the new unique_id contains 'atdma' for upstream
            calls = mock_registry.async_update_entity.call_args_list
            assert any("atdma" in str(call) for call in calls)

    def test_removes_old_entity_when_new_exists(self, mock_hass, mock_entry):
        """Test that old entity is removed when new unique_id already exists."""
        with patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get:
            mock_registry = MagicMock()

            mock_entity = MagicMock()
            mock_entity.config_entry_id = "test_entry_id"
            mock_entity.unique_id = "test_entry_id_cable_modem_ds_ch_1_power"
            mock_entity.entity_id = "sensor.cable_modem_ds_ch_1_power"
            mock_entity.domain = "sensor"
            mock_entity.platform = "cable_modem_monitor"

            mock_registry.entities.values.return_value = [mock_entity]
            # Simulate new entity already exists
            mock_registry.async_get_entity_id.return_value = "sensor.cable_modem_ds_qam_ch_1_power"
            mock_async_get.return_value = mock_registry

            result = migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 1
            mock_registry.async_remove.assert_called_once_with("sensor.cable_modem_ds_ch_1_power")

    def test_skips_entities_from_other_config_entries(self, mock_hass, mock_entry):
        """Test that entities from other config entries are skipped."""
        with patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get:
            mock_registry = MagicMock()

            mock_entity = MagicMock()
            mock_entity.config_entry_id = "other_entry_id"  # Different entry
            mock_entity.unique_id = "other_entry_id_cable_modem_ds_ch_1_power"
            mock_entity.entity_id = "sensor.cable_modem_ds_ch_1_power"

            mock_registry.entities.values.return_value = [mock_entity]
            mock_async_get.return_value = mock_registry

            result = migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 0

    def test_skips_already_migrated_entities(self, mock_hass, mock_entry):
        """Test that entities with new naming scheme are skipped."""
        with patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get:
            mock_registry = MagicMock()

            # Entity already has new naming scheme with channel type
            mock_entity = MagicMock()
            mock_entity.config_entry_id = "test_entry_id"
            mock_entity.unique_id = "test_entry_id_cable_modem_ds_qam_ch_1_power"
            mock_entity.entity_id = "sensor.cable_modem_ds_qam_ch_1_power"

            mock_registry.entities.values.return_value = [mock_entity]
            mock_async_get.return_value = mock_registry

            result = migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 0

    def test_handles_multiple_entities(self, mock_hass, mock_entry):
        """Test migration of multiple entities at once."""
        with patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get:
            mock_registry = MagicMock()

            entities = []
            # Create 4 entities: ds_ch_1_power, ds_ch_1_snr, us_ch_1_power, us_ch_1_frequency
            test_cases = [
                ("ds", 1, "power"),
                ("ds", 1, "snr"),
                ("us", 1, "power"),
                ("us", 1, "frequency"),
            ]
            for direction, channel, metric in test_cases:
                mock_entity = MagicMock()
                mock_entity.config_entry_id = "test_entry_id"
                mock_entity.unique_id = f"test_entry_id_cable_modem_{direction}_ch_{channel}_{metric}"
                mock_entity.entity_id = f"sensor.cable_modem_{direction}_ch_{channel}_{metric}"
                mock_entity.domain = "sensor"
                mock_entity.platform = "cable_modem_monitor"
                entities.append(mock_entity)

            mock_registry.entities.values.return_value = entities
            mock_registry.async_get_entity_id.return_value = None
            mock_registry.async_get.return_value = None
            mock_async_get.return_value = mock_registry

            result = migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 4

    def test_handles_migration_error_gracefully(self, mock_hass, mock_entry):
        """Test that migration errors are handled gracefully."""
        with patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get:
            mock_registry = MagicMock()

            mock_entity = MagicMock()
            mock_entity.config_entry_id = "test_entry_id"
            mock_entity.unique_id = "test_entry_id_cable_modem_ds_ch_1_power"
            mock_entity.entity_id = "sensor.cable_modem_ds_ch_1_power"
            mock_entity.domain = "sensor"
            mock_entity.platform = "cable_modem_monitor"

            mock_registry.entities.values.return_value = [mock_entity]
            mock_registry.async_get_entity_id.return_value = None
            # Simulate error during update
            mock_registry.async_update_entity.side_effect = ValueError("Test error")
            mock_async_get.return_value = mock_registry

            # Should not raise, should return 0 (failed migration)
            result = migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == 0

    def test_migrates_all_metric_types(self, mock_hass, mock_entry):
        """Test that all metric types are migrated correctly."""
        metrics = ["power", "snr", "frequency", "corrected", "uncorrected"]

        with patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get:
            mock_registry = MagicMock()

            entities = []
            for metric in metrics:
                mock_entity = MagicMock()
                mock_entity.config_entry_id = "test_entry_id"
                mock_entity.unique_id = f"test_entry_id_cable_modem_ds_ch_1_{metric}"
                mock_entity.entity_id = f"sensor.cable_modem_ds_ch_1_{metric}"
                mock_entity.domain = "sensor"
                mock_entity.platform = "cable_modem_monitor"
                entities.append(mock_entity)

            mock_registry.entities.values.return_value = entities
            mock_registry.async_get_entity_id.return_value = None
            mock_registry.async_get.return_value = None
            mock_async_get.return_value = mock_registry

            result = migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            assert result == len(metrics)

    def test_preserves_custom_entity_id(self, mock_hass, mock_entry):
        """Test that custom entity IDs that don't match pattern are preserved."""
        with patch("homeassistant.helpers.entity_registry.async_get") as mock_async_get:
            mock_registry = MagicMock()

            # Entity with custom entity_id (user renamed)
            mock_entity = MagicMock()
            mock_entity.config_entry_id = "test_entry_id"
            mock_entity.unique_id = "test_entry_id_cable_modem_ds_ch_1_power"
            mock_entity.entity_id = "sensor.my_custom_power_sensor"  # User renamed
            mock_entity.domain = "sensor"
            mock_entity.platform = "cable_modem_monitor"

            mock_registry.entities.values.return_value = [mock_entity]
            mock_registry.async_get_entity_id.return_value = None
            mock_registry.async_get.return_value = None
            mock_async_get.return_value = mock_registry

            result = migrate_docsis30_entities(mock_hass, mock_entry, "3.0")

            # Should not migrate entity_id, but unique_id should be updated
            # Since entity_id doesn't end with expected pattern, migration skips
            assert result == 0
