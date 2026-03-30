"""Shared fixtures for HA adapter component tests.

Mock boundary: Core I/O (orchestrator, health monitor, config loaders).
All fixtures return realistic but deterministic data for reproducible tests.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from solentlabs.cable_modem_monitor_core.orchestration.models import (
    HealthInfo,
    ModemIdentity,
    ModemSnapshot,
    OrchestratorDiagnostics,
    RestartResult,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    CollectorSignal,
    ConnectionStatus,
    DocsisStatus,
    HealthStatus,
    RestartPhase,
)

from custom_components.cable_modem_monitor.const import (
    CONF_ENTITY_PREFIX,
    CONF_HEALTH_CHECK_INTERVAL,
    CONF_LEGACY_SSL,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_MODEM_DIR,
    CONF_PROTOCOL,
    CONF_SCAN_INTERVAL,
    CONF_SUPPORTS_HEAD,
    CONF_SUPPORTS_ICMP,
    CONF_VARIANT,
    ENTITY_PREFIX_NONE,
)
from custom_components.cable_modem_monitor.coordinator import (
    CableModemRuntimeData,
)

# ---------------------------------------------------------------------------
# Canned modem data — realistic minimal set
# ---------------------------------------------------------------------------

MOCK_SYSTEM_INFO: dict[str, Any] = {
    "software_version": "4502.9.016",
    "system_uptime": "2d 5h 30m",
    "downstream_channel_count": 2,
    "upstream_channel_count": 1,
    "total_corrected": 150,
    "total_uncorrected": 3,
}

MOCK_DOWNSTREAM: list[dict[str, Any]] = [
    {
        "channel_id": 1,
        "channel_type": "qam",
        "frequency": 555000000,
        "power": 2.5,
        "snr": 38.0,
        "corrected": 100,
        "uncorrected": 2,
        "modulation": "256QAM",
    },
    {
        "channel_id": 2,
        "channel_type": "ofdm",
        "frequency": 722000000,
        "power": -1.0,
        "snr": 35.5,
        "corrected": 50,
        "uncorrected": 1,
        "modulation": "OFDM",
    },
]

MOCK_UPSTREAM: list[dict[str, Any]] = [
    {
        "channel_id": 1,
        "channel_type": "atdma",
        "frequency": 36400000,
        "power": 42.0,
        "modulation": "64QAM",
    },
]

MOCK_MODEM_DATA: dict[str, Any] = {
    "system_info": MOCK_SYSTEM_INFO,
    "downstream": MOCK_DOWNSTREAM,
    "upstream": MOCK_UPSTREAM,
}

MOCK_ENTRY_DATA: dict[str, Any] = {
    "host": "192.168.100.1",
    "username": "admin",
    "password": "password",
    CONF_MANUFACTURER: "Motorola",
    CONF_MODEL: "MB7621",
    CONF_VARIANT: None,
    CONF_ENTITY_PREFIX: ENTITY_PREFIX_NONE,
    CONF_MODEM_DIR: "motorola/mb7621",
    CONF_PROTOCOL: "http",
    CONF_LEGACY_SSL: False,
    CONF_SUPPORTS_ICMP: True,
    CONF_SUPPORTS_HEAD: True,
    CONF_SCAN_INTERVAL: 600,
    CONF_HEALTH_CHECK_INTERVAL: 30,
}

MOCK_VALIDATION_RESULT: dict[str, Any] = {
    "protocol": "http",
    "legacy_ssl": False,
    "supports_icmp": True,
    "supports_head": True,
}


# ---------------------------------------------------------------------------
# Core model fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_modem_identity() -> ModemIdentity:
    """A realistic ModemIdentity."""
    return ModemIdentity(
        manufacturer="Motorola",
        model="MB7621",
        docsis_version="3.0",
        release_date="2018",
        status="verified",
    )


@pytest.fixture
def mock_health_info() -> HealthInfo:
    """A healthy HealthInfo."""
    return HealthInfo(
        health_status=HealthStatus.RESPONSIVE,
        icmp_latency_ms=2.5,
        http_latency_ms=15.0,
    )


@pytest.fixture
def mock_modem_snapshot(mock_health_info: HealthInfo) -> ModemSnapshot:
    """A complete ModemSnapshot with modem data."""
    return ModemSnapshot(
        connection_status=ConnectionStatus.ONLINE,
        docsis_status=DocsisStatus.OPERATIONAL,
        modem_data=MOCK_MODEM_DATA,
        health_info=mock_health_info,
        collector_signal=CollectorSignal.OK,
    )


@pytest.fixture
def mock_orchestrator_diagnostics() -> OrchestratorDiagnostics:
    """Orchestrator diagnostics snapshot."""
    return OrchestratorDiagnostics(
        poll_duration=1.5,
        auth_failure_streak=0,
        circuit_breaker_open=False,
        session_is_valid=True,
        last_poll_timestamp=1700000000.0,
    )


# ---------------------------------------------------------------------------
# Mock Core components
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_orchestrator(
    mock_modem_snapshot: ModemSnapshot,
    mock_orchestrator_diagnostics: OrchestratorDiagnostics,
) -> MagicMock:
    """A mock Orchestrator that returns canned data."""
    orch = MagicMock()
    orch.get_modem_data.return_value = mock_modem_snapshot
    orch.supports_restart = True
    orch.is_restarting = False
    orch.diagnostics.return_value = mock_orchestrator_diagnostics
    orch.restart.return_value = RestartResult(
        success=True,
        phase_reached=RestartPhase.COMPLETE,
        elapsed_seconds=120.0,
    )
    orch.reset_connectivity.return_value = None
    return orch


@pytest.fixture
def mock_health_monitor(mock_health_info: HealthInfo) -> MagicMock:
    """A mock HealthMonitor that returns canned data."""
    monitor = MagicMock()
    monitor.ping.return_value = mock_health_info
    return monitor


# ---------------------------------------------------------------------------
# HA integration fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_data_coordinator(mock_modem_snapshot: ModemSnapshot) -> MagicMock:
    """A mock DataUpdateCoordinator for modem data."""
    coord = MagicMock()
    coord.data = mock_modem_snapshot
    coord.last_update_success = True
    coord.last_exception = None
    coord.update_interval = "0:10:00"
    return coord


@pytest.fixture
def mock_health_coordinator(mock_health_info: HealthInfo) -> MagicMock:
    """A mock DataUpdateCoordinator for health probes."""
    coord = MagicMock()
    coord.data = mock_health_info
    coord.last_update_success = True
    coord.update_interval = "0:00:30"
    return coord


@pytest.fixture
def mock_runtime_data(
    mock_orchestrator: MagicMock,
    mock_health_monitor: MagicMock,
    mock_modem_identity: ModemIdentity,
    mock_data_coordinator: MagicMock,
    mock_health_coordinator: MagicMock,
) -> CableModemRuntimeData:
    """Runtime data with mock coordinators.

    Coordinators are injected as fixtures so tests can receive them
    directly (typed as MagicMock) for assertions — no type: ignore
    casts needed.
    """
    return CableModemRuntimeData(
        data_coordinator=mock_data_coordinator,
        health_coordinator=mock_health_coordinator,
        orchestrator=mock_orchestrator,
        health_monitor=mock_health_monitor,
        cancel_event=None,
        modem_identity=mock_modem_identity,
    )
