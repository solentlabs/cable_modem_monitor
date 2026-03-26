"""Runtime data types for the Cable Modem Monitor integration.

Defines ``CableModemRuntimeData`` (stored on ``entry.runtime_data``)
and the ``CableModemConfigEntry`` type alias used by all platform modules.

These types live here — not in ``__init__.py`` (circular import risk)
or ``const.py`` (which should stay a leaf module with no heavy imports).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

if TYPE_CHECKING:
    from solentlabs.cable_modem_monitor_core.orchestration.models import (
        HealthInfo,
        ModemIdentity,
        ModemSnapshot,
    )
    from solentlabs.cable_modem_monitor_core.orchestration.modem_health import (
        HealthMonitor,
    )
    from solentlabs.cable_modem_monitor_core.orchestration.orchestrator import (
        Orchestrator,
    )


@dataclass
class CableModemRuntimeData:
    """All runtime state for one config entry.

    Stored on ``entry.runtime_data``, replacing the v3.13 pattern of
    ``hass.data[DOMAIN][entry.entry_id]``.  HA manages cleanup
    automatically on unload.
    """

    data_coordinator: DataUpdateCoordinator[ModemSnapshot]
    health_coordinator: DataUpdateCoordinator[HealthInfo] | None
    orchestrator: Orchestrator
    health_monitor: HealthMonitor | None
    cancel_event: threading.Event | None
    modem_identity: ModemIdentity


CableModemConfigEntry: TypeAlias = ConfigEntry[CableModemRuntimeData]  # noqa: UP040 — mypy doesn't support PEP 695 yet
