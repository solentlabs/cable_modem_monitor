"""Utility for cleaning up Cable Modem Monitor entities in Home Assistant.

This module helps clean up orphaned entities that may accumulate during
upgrades from v1.x to v2.0 or after multiple integration reinstalls.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

ENTITY_REGISTRY_PATH = Path("/config/.storage/core.entity_registry")
BACKUP_DIR = Path("/config/.storage")

def analyze_entities(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze cable modem entities in Home Assistant.
    
    Args:
        data: The loaded entity registry data

    Returns:
        Dict containing analysis results including:
        - total_entities: Total number of entities in Home Assistant
        - cable_modem_total: Total number of cable modem entities
        - active: List of active cable modem entities
        - orphaned: List of orphaned cable modem entities
        - creation_dates: Entity counts grouped by creation date
    """
    all_entities = data['data']['entities']

    ***REMOVED*** Find all cable modem entities
    cable_modem_entities = [
        e for e in all_entities
        if 'cable_modem' in e.get('unique_id', '').lower() or
           e.get('platform') == 'cable_modem_monitor'
    ]

    ***REMOVED*** Categorize entities
    active = [e for e in cable_modem_entities if e.get('config_entry_id')]
    orphaned = [
        e for e in cable_modem_entities
        if not e.get('config_entry_id') or e.get('orphaned_timestamp')
    ]

    ***REMOVED*** Group by creation date
    creation_dates = {}
    for entity in cable_modem_entities:
        created = entity.get('created_at', 'unknown')[:10]
        if created not in creation_dates:
            creation_dates[created] = {'active': 0, 'orphaned': 0}
        if entity in active:
            creation_dates[created]['active'] += 1
        else:
            creation_dates[created]['orphaned'] += 1

    return {
        'total_entities': len(all_entities),
        'cable_modem_total': len(cable_modem_entities),
        'active': active,
        'orphaned': orphaned,
        'creation_dates': creation_dates
    }

def backup_entity_registry() -> Path:
    """Create a backup of the entity registry.
    
    Returns:
        Path to the backup file
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"core.entity_registry.backup-{timestamp}"

    with open(ENTITY_REGISTRY_PATH, 'r') as src:
        with open(backup_path, 'w') as dst:
            dst.write(src.read())

    return backup_path

def cleanup_orphaned_entities(hass: HomeAssistant) -> bool:
    """Remove orphaned cable modem entities.
    
    Args:
        hass: HomeAssistant instance

    Returns:
        bool: True if cleanup was successful, False otherwise
    """
    try:
        with open(ENTITY_REGISTRY_PATH, 'r') as f:
            data = json.load(f)

        ***REMOVED*** Create backup
        backup_path = backup_entity_registry()

        ***REMOVED*** Analyze and remove orphans
        stats = analyze_entities(data)
        if not stats['orphaned']:
            return True

        all_entities = data['data']['entities']
        entities_to_keep = [e for e in all_entities if e not in stats['orphaned']]
        data['data']['entities'] = entities_to_keep

        ***REMOVED*** Save changes
        with open(ENTITY_REGISTRY_PATH, 'w') as f:
            json.dump(data, f, indent=2)

        return True

    except Exception as ex:
        return False

async def async_cleanup_orphaned_entities(hass: HomeAssistant) -> bool:
    """Async wrapper for cleanup_orphaned_entities."""
    return await hass.async_add_executor_job(cleanup_orphaned_entities, hass)

def remove_all_entities(hass: HomeAssistant) -> bool:
    """Remove ALL cable modem entities (nuclear option).
    
    Args:
        hass: HomeAssistant instance

    Returns:
        bool: True if removal was successful, False otherwise
    """
    try:
        with open(ENTITY_REGISTRY_PATH, 'r') as f:
            data = json.load(f)

        ***REMOVED*** Create backup
        backup_path = backup_entity_registry()

        ***REMOVED*** Remove all cable modem entities
        stats = analyze_entities(data)
        all_entities = data['data']['entities']
        all_cable_modem = stats['active'] + stats['orphaned']
        entities_to_keep = [e for e in all_entities if e not in all_cable_modem]
        data['data']['entities'] = entities_to_keep

        ***REMOVED*** Save changes
        with open(ENTITY_REGISTRY_PATH, 'w') as f:
            json.dump(data, f, indent=2)

        return True

    except Exception as ex:
        return False

async def async_remove_all_entities(hass: HomeAssistant) -> bool:
    """Async wrapper for remove_all_entities."""
    return await hass.async_add_executor_job(remove_all_entities, hass)