"""Channel frequency registers in a running Home Assistant on every supported version.

Frequency is stored in Hz (FIELD_REGISTRY base SI) and suggested in MHz
where Home Assistant can convert frequency units (2026.5 and later).
Older versions reject a suggested unit they cannot convert, so there the
sensor must suggest nothing and stay in Hz. This test runs on both the
floor and the pinned current Home Assistant (ENTITY_MODEL_SPEC § Unit
metadata).
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.sensor.const import UNIT_CONVERTERS, SensorDeviceClass
from homeassistant.core import HomeAssistant
from solentlabs.cable_modem_monitor_core.orchestration.models import (
    ModemIdentity,
    ModemSnapshot,
    OrchestratorDiagnostics,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    CollectorSignal,
    ConnectionStatus,
    DocsisStatus,
)

from custom_components.cable_modem_monitor.const import CONF_SCAN_INTERVAL, DOMAIN
from tests.ha_harness import MockConfigEntry

from .conftest import MOCK_ENTRY_DATA, MOCK_MODEM_DATA

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

_ONLINE = ModemSnapshot(
    connection_status=ConnectionStatus.ONLINE,
    docsis_status=DocsisStatus.OPERATIONAL,
    modem_data=MOCK_MODEM_DATA,
    collector_signal=CollectorSignal.OK,
)
_DIAGNOSTICS = OrchestratorDiagnostics(
    poll_duration=1.0,
    auth_failure_streak=0,
    circuit_breaker_open=False,
    circuit_trip_signal=None,
    session_is_valid=True,
    last_poll_at="2026-05-01T12:00:00+00:00",
)


async def test_frequency_sensor_registers_with_its_display_unit(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """MHz where Home Assistant converts frequency, Hz elsewhere, and no unit error either way."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=2,
        # Manual polling: no interval timer outlives the test.
        data={**MOCK_ENTRY_DATA, CONF_SCAN_INTERVAL: 0},
    )
    entry.add_to_hass(hass)

    orchestrator = MagicMock()
    orchestrator.get_modem_data.return_value = _ONLINE
    orchestrator.diagnostics.return_value = _DIAGNOSTICS
    orchestrator.recovery_active = False
    identity = ModemIdentity(manufacturer="Solent Labs", model="TPS-2000", status="confirmed")

    with (
        patch(
            "custom_components.cable_modem_monitor._create_core_components",
            return_value=(orchestrator, None, identity, ()),
        ),
        caplog.at_level(logging.WARNING),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    frequency_states = [s for s in hass.states.async_all("sensor") if s.entity_id.endswith("_frequency")]
    expected = "MHz" if SensorDeviceClass.FREQUENCY in UNIT_CONVERTERS else "Hz"

    assert frequency_states, "no frequency sensors registered"
    assert {s.attributes.get("unit_of_measurement") for s in frequency_states} == {expected}
    assert "incorrect unit of measurement" not in caplog.text
