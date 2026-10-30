"""Migrate config entries from v2.1 to v2.2: clear old channel Frequency statistics.

Channel Frequency sensors no longer have a ``state_class``.  Home
Assistant raises a "no longer has a state class" Repairs warning for
every entity that has long-term statistics but no ``state_class``, so
the statistics recorded under the old class are cleared once.  The
warnings clear on the recorder's next hourly statistics run.

This is a minor-version step, not a ``v{N}_to_v{M}`` file, so the
registry does not discover it; ``async_migrate_entry`` calls it.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.recorder import get_instance

_LOGGER = logging.getLogger(__name__)

# Must match ConfigFlow.MINOR_VERSION in config_flow.py
MINOR_VERSION = 2

# Every channel Frequency sensor's unique_id ends with this, in position
# and ID naming modes alike.
_FREQUENCY_SUFFIX = "_frequency"


async def async_migrate(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Clear the entry's channel Frequency statistics and record minor version 2."""
    registry = er.async_get(hass)
    entity_ids = [
        reg_entry.entity_id
        for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id)
        if reg_entry.domain == "sensor" and reg_entry.unique_id.endswith(_FREQUENCY_SUFFIX)
    ]

    # Without a recorder there are no statistics to clear.
    if entity_ids and "recorder" in hass.config.components:
        _LOGGER.info("Clearing statistics for %d channel Frequency sensors", len(entity_ids))
        get_instance(hass).async_clear_statistics(entity_ids)

    hass.config_entries.async_update_entry(entry, minor_version=MINOR_VERSION)
    return True
