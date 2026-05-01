"""Runtime data types for the Cable Modem Monitor integration.

Defines ``CableModemRuntimeData`` (stored on ``entry.runtime_data``)
and the ``CableModemConfigEntry`` type alias used by all platform modules.

These types live here — not in ``__init__.py`` (circular import risk)
or ``const.py`` (which should stay a leaf module with no heavy imports).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, TypeAlias, TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .mapping_manager import ChannelMap

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

# Name of a destructive button operation currently in progress, or
# None when nothing is running. Acts as a mutex between the Restart
# and Reset buttons — a second press while one is in flight is
# refused. Distinct from Core's ``recovery_active`` flag: that one
# is a cadence signal, this one is a short-lived handler gate.
ActiveOperation = Literal["restart", "reset"]


class ProbeSupport(TypedDict):
    """Resolved probe capability state for one config entry."""

    supports_icmp: bool
    supports_head: bool


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
    modem_identity: ModemIdentity
    probe_support: ProbeSupport
    channel_map: ChannelMap = field(default_factory=ChannelMap)
    # Set while a destructive button handler (Restart, Reset) is
    # running; cleared in the handler's ``finally`` block. Read by
    # other buttons that must refuse overlapping presses.
    active_operation: ActiveOperation | None = None


CableModemConfigEntry: TypeAlias = ConfigEntry[CableModemRuntimeData]  # noqa: UP040 — mypy doesn't support PEP 695 yet
