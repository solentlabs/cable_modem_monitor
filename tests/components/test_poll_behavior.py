"""What one data poll does, observed from outside the integration.

Each poll must: log availability once per change, start reauth when the
auth breaker opens, rebuild the channel map, run channel-bond
onboarding, and fire the data-updated event. The jobs have unit tests
in test_init.py; this test pins that a real poll runs all five. It
drives polls through the entry's data coordinator and patches only the
Core factory and HA's platform forwarding, so it holds no matter where
the poll code lives.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_mock_service,
)
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

from custom_components.cable_modem_monitor.const import (
    CONF_CHANNEL_ONBOARDING_ELIGIBLE,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

from .conftest import MOCK_DOWNSTREAM, MOCK_ENTRY_DATA, MOCK_MODEM_DATA

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

_ONLINE = ModemSnapshot(
    connection_status=ConnectionStatus.ONLINE,
    docsis_status=DocsisStatus.OPERATIONAL,
    modem_data=MOCK_MODEM_DATA,
    collector_signal=CollectorSignal.OK,
)
# A third downstream channel bonds in, so the channel map must grow.
_REBONDED = ModemSnapshot(
    connection_status=ConnectionStatus.ONLINE,
    docsis_status=DocsisStatus.OPERATIONAL,
    modem_data={**MOCK_MODEM_DATA, "downstream": [*MOCK_DOWNSTREAM, {**MOCK_DOWNSTREAM[0], "channel_id": 3}]},
    collector_signal=CollectorSignal.OK,
)
_AUTH_FAILED = ModemSnapshot(
    connection_status=ConnectionStatus.AUTH_FAILED,
    docsis_status=DocsisStatus.UNKNOWN,
    modem_data=None,
    collector_signal=CollectorSignal.AUTH_FAILED,
    error="auth failed",
)
_BREAKER_OPEN = OrchestratorDiagnostics(
    poll_duration=1.0,
    auth_failure_streak=1,
    circuit_breaker_open=True,
    circuit_trip_signal=CollectorSignal.AUTH_FAILED,
    session_is_valid=False,
    last_poll_at="2026-05-01T12:00:00+00:00",
)


async def test_poll_runs_every_job(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Online, rebonded, auth failure, online again: each poll runs all five jobs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=2,
        # Manual polling: no interval timer outlives the test.
        data={**MOCK_ENTRY_DATA, CONF_SCAN_INTERVAL: 0, CONF_CHANNEL_ONBOARDING_ELIGIBLE: True},
    )
    entry.add_to_hass(hass)

    orchestrator = MagicMock()
    orchestrator.get_modem_data.side_effect = [_ONLINE, _REBONDED, _AUTH_FAILED, _ONLINE]
    orchestrator.diagnostics.return_value = _BREAKER_OPEN
    orchestrator.recovery_active = False
    identity = ModemIdentity(manufacturer="Solent Labs", model="TPS-2000", status="confirmed")

    notifications = async_mock_service(hass, "persistent_notification", "create")
    events = async_capture_events(hass, "cable_modem_monitor_data_updated")

    with (
        patch(
            "custom_components.cable_modem_monitor._create_core_components",
            return_value=(orchestrator, None, identity, ()),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
        caplog.at_level(logging.DEBUG, logger="custom_components.cable_modem_monitor"),
    ):
        # Poll 1 (setup's first refresh): online.
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        runtime: Any = entry.runtime_data
        assert len(runtime.channel_map.downstream) == 2

        # Poll 2: a channel bonds in.
        await runtime.data_coordinator.async_refresh()
        assert len(runtime.channel_map.downstream) == 3

        # Poll 3: login rejected and the breaker is open.
        await runtime.data_coordinator.async_refresh()
        await hass.async_block_till_done()

        # Poll 4: back online.
        await runtime.data_coordinator.async_refresh()
        await hass.async_block_till_done()

    # Availability is logged once per change, not once per poll.
    assert caplog.text.count("Modem unavailable") == 1
    assert caplog.text.count("Modem available again") == 1
    # The open breaker started reauthentication.
    assert len(list(entry.async_get_active_flows(hass, {config_entries.SOURCE_REAUTH}))) == 1
    # Channel-bond onboarding announced the modem once.
    onboarding = [c for c in notifications if "onboarding" in c.data["notification_id"]]
    assert len(onboarding) == 1
    # Every poll fired the data-updated event.
    assert len(events) == 4
    # Poll lines, HA's own fetch timing included, log under the
    # integration's package logger: user log filters, the diagnostics
    # log buffer and analyze_logs.py all key on it.
    poll_markers = ("Modem unavailable", "Modem available again", "Auth circuit breaker", "Finished fetching")
    poll_records = [r for r in caplog.records if r.getMessage().startswith(poll_markers)]
    assert len(poll_records) >= 4
    assert {r.name for r in poll_records} == {"custom_components.cable_modem_monitor"}
