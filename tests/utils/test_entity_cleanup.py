"""Tests for the entity cleanup utility."""

from __future__ import annotations

from unittest.mock import mock_open, patch

import pytest

from custom_components.cable_modem_monitor.utils.entity_cleanup import (
    analyze_entities,
    cleanup_orphaned_entities,
    remove_all_entities,
)


@pytest.fixture
def mock_entity_registry_data():
    """Provide mock entity registry data."""
    return {
        "data": {
            "entities": [
                {
                    "entity_id": "sensor.cable_modem_active_sensor",
                    "config_entry_id": "active_config_entry",
                    "platform": "cable_modem_monitor",
                    "unique_id": "cable_modem_active_sensor",
                },
                {
                    "entity_id": "sensor.cable_modem_orphaned_sensor",
                    "config_entry_id": None,  ***REMOVED*** Orphaned
                    "platform": "cable_modem_monitor",
                    "unique_id": "cable_modem_orphaned_sensor",
                },
                {
                    "entity_id": "switch.other_switch",
                    "config_entry_id": "other_config_entry",
                    "platform": "other_platform",
                    "unique_id": "other_switch",
                },
            ]
        }
    }


def test_analyze_entities(mock_entity_registry_data):
    """Test the analyze_entities function."""
    stats = analyze_entities(mock_entity_registry_data)

    assert stats["total_entities"] == 3
    assert stats["cable_modem_total"] == 2
    assert len(stats["active"]) == 1
    assert len(stats["orphaned"]) == 1
    assert stats["active"][0]["entity_id"] == "sensor.cable_modem_active_sensor"
    assert stats["orphaned"][0]["entity_id"] == "sensor.cable_modem_orphaned_sensor"


@patch("builtins.open", new_callable=mock_open)
@patch("json.dump")
@patch("json.load")
def test_cleanup_orphaned_entities(mock_json_load, mock_json_dump, mock_file, mock_entity_registry_data):
    """Test the cleanup_orphaned_entities function."""
    mock_json_load.return_value = mock_entity_registry_data

    ***REMOVED*** Mock the backup function to avoid filesystem interaction
    with patch("custom_components.cable_modem_monitor.utils.entity_cleanup.backup_entity_registry") as mock_backup:
        result = cleanup_orphaned_entities(None)  ***REMOVED*** Pass None for hass, as it's not used in the sync version

        assert result is True
        mock_backup.assert_called_once()

        ***REMOVED*** Verify that json.dump was called with the correct data (without the orphaned entity)
        args, kwargs = mock_json_dump.call_args
        written_data = args[0]
        assert len(written_data["data"]["entities"]) == 2
        assert "sensor.cable_modem_orphaned_sensor" not in [e["entity_id"] for e in written_data["data"]["entities"]]


@patch("builtins.open", new_callable=mock_open)
@patch("json.dump")
@patch("json.load")
def test_remove_all_entities(mock_json_load, mock_json_dump, mock_file, mock_entity_registry_data):
    """Test the remove_all_entities function."""
    mock_json_load.return_value = mock_entity_registry_data

    ***REMOVED*** Mock the backup function
    with patch("custom_components.cable_modem_monitor.utils.entity_cleanup.backup_entity_registry") as mock_backup:
        result = remove_all_entities(None)  ***REMOVED*** Pass None for hass

        assert result is True
        mock_backup.assert_called_once()

        ***REMOVED*** Verify that json.dump was called with the correct data (without any cable modem entities)
        args, kwargs = mock_json_dump.call_args
        written_data = args[0]
        assert len(written_data["data"]["entities"]) == 1
        assert written_data["data"]["entities"][0]["entity_id"] == "switch.other_switch"
