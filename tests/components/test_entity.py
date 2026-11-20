"""The shared entity base, observed through the real sensor and button platforms.

Reads the entity and device registries and live states, so it holds
whichever class builds DeviceInfo or wires coordinator updates (HA
quality scale common-modules). A change that detached entities from
the device, renamed the device, changed entity IDs, dropped
has_entity_name or stopped sensors following their coordinator fails
here.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.util import slugify
from solentlabs.cable_modem_monitor_core.orchestration.models import (
    HealthInfo,
    ModemIdentity,
    ModemSnapshot,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    CollectorSignal,
    ConnectionStatus,
    DocsisStatus,
    HealthStatus,
)

from custom_components.cable_modem_monitor.const import (
    CONF_ENTITY_PREFIX,
    DOMAIN,
    EntityPrefix,
)
from tests.ha_harness import MockConfigEntry

from .conftest import MOCK_ENTRY_DATA, MOCK_MODEM_DATA, MOCK_SYSTEM_INFO

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

_ONLINE = ModemSnapshot(
    connection_status=ConnectionStatus.ONLINE,
    docsis_status=DocsisStatus.OPERATIONAL,
    modem_data=MOCK_MODEM_DATA,
    collector_signal=CollectorSignal.OK,
)
_HEALTHY = HealthInfo(health_status=HealthStatus.RESPONSIVE, icmp_latency_ms=2.5, http_latency_ms=15.0)


async def _set_up(hass: HomeAssistant, prefix: EntityPrefix = EntityPrefix.NONE) -> tuple[Any, MagicMock, MagicMock]:
    """Set up one entry on the real platforms; return entry, orchestrator, health monitor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=2,
        data={**MOCK_ENTRY_DATA, CONF_ENTITY_PREFIX: prefix},
    )
    entry.add_to_hass(hass)

    orchestrator = MagicMock()
    orchestrator.supports_restart = True
    orchestrator.recovery_active = False
    orchestrator.get_modem_data.return_value = _ONLINE
    health_monitor = MagicMock()
    health_monitor.ping.return_value = _HEALTHY
    identity = ModemIdentity(manufacturer="Solent Labs", model="TPS-2000", status="confirmed")

    with patch(
        "custom_components.cable_modem_monitor._create_core_components",
        return_value=(orchestrator, health_monitor, identity, ()),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry, orchestrator, health_monitor


def _state(hass: HomeAssistant, entity_id: str) -> str:
    """Current state string of an entity that must exist."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


def _entity_id(hass: HomeAssistant, entry: Any, unique_suffix: str) -> str:
    """Entity ID registered for ``{entry_id}_{unique_suffix}``."""
    entity_id = er.async_get(hass).async_get_entity_id(Platform.SENSOR, DOMAIN, f"{entry.entry_id}_{unique_suffix}")
    assert entity_id is not None
    return entity_id


# ┌───────────────┬──────────────────────────────────┐
# │ entity prefix │ device name                      │
# ├───────────────┼──────────────────────────────────┤
# │ none          │ Cable Modem                      │
# │ model         │ Cable Modem TPS-2000             │
# │ ip            │ Cable Modem 192.168.100.1        │
# └───────────────┴──────────────────────────────────┘
#
# fmt: off
PREFIX_CASES = [
    # (prefix,            device_name,                 id)
    (EntityPrefix.NONE,   "Cable Modem",               "no_prefix"),
    (EntityPrefix.MODEL,  "Cable Modem TPS-2000",      "model_prefix"),
    (EntityPrefix.IP,     "Cable Modem 192.168.100.1", "ip_prefix"),
]
# fmt: on


@pytest.mark.parametrize("prefix,device_name", [c[:2] for c in PREFIX_CASES], ids=[c[2] for c in PREFIX_CASES])
async def test_every_entity_links_to_the_device(hass: HomeAssistant, prefix: EntityPrefix, device_name: str) -> None:
    """All sensors and buttons attach to one device with the prefix's name."""
    entry, _, _ = await _set_up(hass, prefix)

    # async_get_device is deprecated from HA 2026.10; this lookup exists on the floor too.
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert (DOMAIN, entry.entry_id) in device.identifiers
    assert device.name == device_name

    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    platforms = {e.domain for e in entities}
    assert {Platform.SENSOR, Platform.BUTTON} <= platforms
    assert {e.device_id for e in entities} == {device.id}
    assert all(e.has_entity_name for e in entities)
    # Entity IDs are minted from the device name at first registration.
    assert all(e.entity_id.split(".", 1)[1].startswith(f"{slugify(device_name)}_") for e in entities)

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_sensors_follow_their_coordinators(hass: HomeAssistant) -> None:
    """Data sensors follow polls; health sensors and Status follow probes."""
    entry, orchestrator, health_monitor = await _set_up(hass)
    runtime: Any = entry.runtime_data
    corrected = _entity_id(hass, entry, "cable_modem_total_corrected")
    ping = _entity_id(hass, entry, "cable_modem_ping_latency")
    status = _entity_id(hass, entry, "cable_modem_status")
    status_before = _state(hass, status)

    orchestrator.get_modem_data.return_value = replace(
        _ONLINE,
        modem_data={**MOCK_MODEM_DATA, "system_info": {**MOCK_SYSTEM_INFO, "total_corrected": 175}},
    )
    await runtime.data_coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, corrected) == "175"

    health_monitor.ping.return_value = HealthInfo(health_status=HealthStatus.UNRESPONSIVE, icmp_latency_ms=12.0)
    await runtime.health_coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, ping) == "12"
    assert _state(hass, status) != status_before

    assert await hass.config_entries.async_unload(entry.entry_id)
