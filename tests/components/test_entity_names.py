"""Entity display-name regression guard.

Locks the user-visible name of every entity both platforms create. Entity
names are migrating from ``_attr_name`` literals to ``translation_key``
lookups (Gold ``entity-translations``); this table is the evidence that the
migration renames nothing. Names are what users see in dashboards, history,
and automations, so a silent change here is a user-facing regression even
though entity IDs stay stable via the registry.

``_display_name`` mirrors Home Assistant's resolution for static names: an
explicit ``_attr_name`` wins, otherwise the ``translation_key`` is resolved
against strings.json. That lets the same table assert before and after the
migration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from solentlabs.cable_modem_monitor_core.orchestration.models import ModemSnapshot
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    ConnectionStatus,
    DocsisStatus,
)

from custom_components.cable_modem_monitor.button import (
    async_setup_entry as button_setup,
)
from custom_components.cable_modem_monitor.sensor import (
    async_setup_entry as sensor_setup,
)

from .conftest import MOCK_ENTRY_DATA, MOCK_MODEM_DATA

_STRINGS = Path("custom_components/cable_modem_monitor/strings.json")

# Every entity the two platforms create for the fixture below, as
# (class name, display name). Captured from the running platforms, not
# hand-written. Sorted so the comparison is order-independent.
_EXPECTED_NAMES: list[tuple[str, str]] = [
    ("ChannelSensor", "DS OFDM Ch 2 Corrected"),
    ("ChannelSensor", "DS OFDM Ch 2 Frequency"),
    ("ChannelSensor", "DS OFDM Ch 2 Power"),
    ("ChannelSensor", "DS OFDM Ch 2 SNR"),
    ("ChannelSensor", "DS OFDM Ch 2 Uncorrected"),
    ("ChannelSensor", "DS QAM Ch 1 Corrected"),
    ("ChannelSensor", "DS QAM Ch 1 Frequency"),
    ("ChannelSensor", "DS QAM Ch 1 Power"),
    ("ChannelSensor", "DS QAM Ch 1 SNR"),
    ("ChannelSensor", "DS QAM Ch 1 Uncorrected"),
    ("ChannelSensor", "US ATDMA Ch 1 Frequency"),
    ("ChannelSensor", "US ATDMA Ch 1 Power"),
    ("HttpLatencySensor", "HTTP Latency"),
    ("LanStatsSensor", "LAN eth0 Received Bytes"),
    ("LanStatsSensor", "LAN eth0 Received Drops"),
    ("LanStatsSensor", "LAN eth0 Received Errors"),
    ("LanStatsSensor", "LAN eth0 Received Packets"),
    ("LanStatsSensor", "LAN eth0 Transmitted Bytes"),
    ("LanStatsSensor", "LAN eth0 Transmitted Drops"),
    ("LanStatsSensor", "LAN eth0 Transmitted Errors"),
    ("LanStatsSensor", "LAN eth0 Transmitted Packets"),
    ("ModemChannelCountSensor", "DS Channel Count"),
    ("ModemChannelCountSensor", "US Channel Count"),
    ("ModemErrorRateSensor", "Rate Corrected Errors"),
    ("ModemErrorRateSensor", "Rate Uncorrected Errors"),
    ("ModemErrorTotalSensor", "Total Corrected Errors"),
    ("ModemErrorTotalSensor", "Total Uncorrected Errors"),
    ("ModemInfoSensor", "Modem Info"),
    ("ModemLastBootTimeSensor", "Last Boot Time"),
    ("ModemSoftwareVersionSensor", "Software Version"),
    ("ModemStatusSensor", "Status"),
    ("PingLatencySensor", "Ping Latency"),
    ("ResetEntitiesButton", "Reset Entities"),
    ("RestartModemButton", "Restart Modem"),
    ("TcpLatencySensor", "TCP Latency"),
    ("UpdateModemDataButton", "Update Modem Data"),
]


def _rich_modem_data() -> dict[str, Any]:
    """Fixture exercising system sensors, both channel directions, and LAN stats."""
    data: dict[str, Any] = dict(MOCK_MODEM_DATA)
    data["lan_stats"] = {"eth0": {"received_bytes": 42000, "transmitted_bytes": 1701}}
    return data


def _display_name(entity: Any, platform: str) -> str:
    """Resolve the name HA shows, via _attr_name or the translation_key."""
    explicit = getattr(entity, "_attr_name", None)
    if explicit is not None:
        return str(explicit)

    key = getattr(entity, "_attr_translation_key", None)
    if key is None:
        raise AssertionError(f"{type(entity).__name__} has neither _attr_name nor _attr_translation_key")

    strings = json.loads(_STRINGS.read_text(encoding="utf-8"))
    name = strings["entity"][platform][key]["name"]
    placeholders = getattr(entity, "_attr_translation_placeholders", None)
    return str(name).format(**placeholders) if placeholders else str(name)


async def _collect(mock_runtime_data) -> list[tuple[str, str]]:
    """Instantiate both platforms and return (class, display name) for every entity."""
    mock_runtime_data.data_coordinator.data = ModemSnapshot(
        connection_status=ConnectionStatus.ONLINE,
        docsis_status=DocsisStatus.OPERATIONAL,
        modem_data=_rich_modem_data(),
    )
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {**MOCK_ENTRY_DATA, "supports_icmp": True, "supports_head": True}
    entry.runtime_data = mock_runtime_data

    hass = MagicMock()
    collected: list[tuple[str, str]] = []
    for setup, platform in ((sensor_setup, "sensor"), (button_setup, "button")):
        add_entities = MagicMock()
        await setup(hass, entry, add_entities)
        for call in add_entities.call_args_list:
            for ent in call[0][0]:
                collected.append((type(ent).__name__, _display_name(ent, platform)))
    return sorted(collected)


async def test_entity_display_names_are_unchanged(mock_runtime_data) -> None:
    """Every entity's user-visible name matches the locked table."""
    assert await _collect(mock_runtime_data) == _EXPECTED_NAMES


async def test_no_entity_name_is_blank(mock_runtime_data) -> None:
    """A missing translation key renders blank rather than failing loudly — catch it here."""
    for cls, name in await _collect(mock_runtime_data):
        assert name.strip(), f"{cls} produced an empty display name"


@pytest.mark.parametrize("platform", ["sensor", "button"])
def test_strings_entity_section_matches_translation_keys(platform: str) -> None:
    """Any entity translation_key declared in strings.json must be non-empty.

    Guards the migration's other failure mode: a key added to code but left
    out of strings.json, or added with an empty name.
    """
    strings = json.loads(_STRINGS.read_text(encoding="utf-8"))
    section = strings.get("entity", {}).get(platform, {})
    for key, payload in section.items():
        assert payload.get("name", "").strip(), f"entity.{platform}.{key}.name is empty"
