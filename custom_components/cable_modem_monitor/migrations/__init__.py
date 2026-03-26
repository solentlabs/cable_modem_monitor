"""Config entry migration registry with auto-discovery.

Manages version-keyed migration handlers.  When HA detects a config
entry whose stored version is lower than ``ConfigFlow.VERSION``, it
calls ``async_migrate_entry`` which delegates here.

**Convention:** Drop a file named ``v{N}_to_v{M}.py`` in this
directory.  It must export an ``async_migrate(hass, entry) -> bool``
function.  The registry discovers it automatically — no manual
registration needed.

Handlers are chained in sequence for multi-version jumps::

    stored v1 → v1_to_v2.async_migrate() → v2_to_v3.async_migrate() → current v3
"""

from __future__ import annotations

import importlib
import logging
import re
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

MigrationFunc = Callable[[HomeAssistant, ConfigEntry], Coroutine[Any, Any, bool]]

_FILENAME_PATTERN = re.compile(r"^v(\d+)_to_v(\d+)$")


def _discover_migrations() -> dict[int, MigrationFunc]:
    """Scan this directory for migration modules.

    Looks for files matching ``v{from}_to_v{to}.py``.  Each must
    export ``async_migrate(hass, entry) -> bool``.

    Returns:
        Dict mapping target version → migration function.
    """
    registry: dict[int, MigrationFunc] = {}
    migrations_dir = Path(__file__).parent

    for py_file in sorted(migrations_dir.glob("v*_to_v*.py")):
        match = _FILENAME_PATTERN.match(py_file.stem)
        if not match:
            continue

        from_ver = int(match.group(1))
        to_ver = int(match.group(2))

        if to_ver != from_ver + 1:
            _LOGGER.warning(
                "Skipping %s: migrations must be sequential " "(expected v%d_to_v%d)",
                py_file.name,
                from_ver,
                from_ver + 1,
            )
            continue

        module = importlib.import_module(f".{py_file.stem}", package=__package__)
        func = getattr(module, "async_migrate", None)
        if func is None:
            _LOGGER.warning(
                "Skipping %s: no async_migrate function found",
                py_file.name,
            )
            continue

        registry[to_ver] = func

    return registry


MIGRATIONS: dict[int, MigrationFunc] = _discover_migrations()


async def async_run_migrations(
    hass: HomeAssistant,
    entry: ConfigEntry,
    target_version: int,
) -> bool:
    """Chain migration handlers from entry.version to target_version.

    Applies each discovered handler in version order.  Stops and
    returns False on the first failure.

    Args:
        hass: Home Assistant instance.
        entry: Config entry to migrate.
        target_version: The ConfigFlow.VERSION to migrate to.

    Returns:
        True if all migrations succeeded, False otherwise.
    """
    current = entry.version

    for version in sorted(MIGRATIONS):
        if current < version <= target_version:
            _LOGGER.info(
                "Migrating config entry %s from version %d to %d",
                entry.entry_id,
                current,
                version,
            )
            try:
                success = await MIGRATIONS[version](hass, entry)
            except Exception:
                _LOGGER.exception(
                    "Migration to version %d failed for entry %s",
                    version,
                    entry.entry_id,
                )
                return False

            if not success:
                _LOGGER.error(
                    "Migration to version %d returned failure for " "entry %s — user must reconfigure",
                    version,
                    entry.entry_id,
                )
                return False

            current = version

    return True
