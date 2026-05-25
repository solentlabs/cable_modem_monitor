"""Tests for orchestration/status.py event emission."""

from __future__ import annotations

from solentlabs.cable_modem_monitor_core.orchestration.events import ZeroChannelsNoSystemInfo
from solentlabs.cable_modem_monitor_core.orchestration.signals import ConnectionStatus
from solentlabs.cable_modem_monitor_core.orchestration.status import derive_connection_status

from .event_capture import assert_event_emitted, capture_events


def test_zero_channels_no_system_info_emits_event():
    with capture_events() as events:
        result = derive_connection_status({}, model="SB8200")

    assert result == ConnectionStatus.NO_SIGNAL
    assert_event_emitted(events, ZeroChannelsNoSystemInfo, model="SB8200")


def test_has_channels_no_event():
    modem_data = {"downstream": [{"channel_number": 1}], "upstream": []}
    with capture_events() as events:
        result = derive_connection_status(modem_data, model="SB8200")

    assert result == ConnectionStatus.ONLINE
    assert not any(isinstance(e, ZeroChannelsNoSystemInfo) for e in events)


def test_has_system_info_no_event():
    modem_data = {"system_info": {"uptime": "1 day"}}
    with capture_events() as events:
        result = derive_connection_status(modem_data, model="SB8200")

    assert result == ConnectionStatus.NO_SIGNAL
    assert not any(isinstance(e, ZeroChannelsNoSystemInfo) for e in events)
