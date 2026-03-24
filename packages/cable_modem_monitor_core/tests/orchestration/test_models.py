"""Tests for orchestration data models."""

from __future__ import annotations

from solentlabs.cable_modem_monitor_core.orchestration.models import (
    HealthInfo,
    ModemResult,
    ModemSnapshot,
    OrchestratorDiagnostics,
    ResourceFetch,
    RestartResult,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    CollectorSignal,
    ConnectionStatus,
    DocsisStatus,
    HealthStatus,
    RestartPhase,
)


class TestModemResult:
    """ModemResult dataclass defaults and construction."""

    def test_success_defaults(self) -> None:
        """Successful result has OK signal and empty error."""
        result = ModemResult(success=True, modem_data={"downstream": []})
        assert result.signal == CollectorSignal.OK
        assert result.error == ""
        assert result.modem_data is not None

    def test_failure_defaults(self) -> None:
        """Failed result has None modem_data by default."""
        result = ModemResult(
            success=False,
            signal=CollectorSignal.AUTH_FAILED,
            error="wrong password",
        )
        assert result.modem_data is None
        assert result.error == "wrong password"

    def test_zero_channels_is_success(self) -> None:
        """Zero channels with system_info is a valid success result."""
        data = {"downstream": [], "upstream": [], "system_info": {"fw": "1.0"}}
        result = ModemResult(success=True, modem_data=data)
        assert result.success is True
        assert result.signal == CollectorSignal.OK


class TestModemSnapshot:
    """ModemSnapshot dataclass defaults and construction."""

    def test_minimal_snapshot(self) -> None:
        """Snapshot with only required fields."""
        snap = ModemSnapshot(
            connection_status=ConnectionStatus.ONLINE,
            docsis_status=DocsisStatus.OPERATIONAL,
        )
        assert snap.modem_data is None
        assert snap.health_info is None
        assert snap.metrics == {}
        assert snap.collector_signal == CollectorSignal.OK
        assert snap.error == ""

    def test_full_snapshot(self) -> None:
        """Snapshot with all fields populated."""
        health = HealthInfo(health_status=HealthStatus.RESPONSIVE)
        snap = ModemSnapshot(
            connection_status=ConnectionStatus.ONLINE,
            docsis_status=DocsisStatus.OPERATIONAL,
            modem_data={"downstream": [{"channel_id": 1}]},
            health_info=health,
            metrics={"total_corrected": 42},
            collector_signal=CollectorSignal.OK,
        )
        assert snap.health_info is not None
        assert snap.metrics["total_corrected"] == 42


class TestResourceFetch:
    """ResourceFetch timing and size."""

    def test_construction(self) -> None:
        fetch = ResourceFetch(path="/status.html", duration_ms=800.0, size_bytes=12480)
        assert fetch.path == "/status.html"
        assert fetch.duration_ms == 800.0
        assert fetch.size_bytes == 12480


class TestHealthInfo:
    """HealthInfo probe results."""

    def test_defaults(self) -> None:
        """Latency fields default to None (not measured)."""
        info = HealthInfo(health_status=HealthStatus.UNKNOWN)
        assert info.icmp_latency_ms is None
        assert info.http_latency_ms is None

    def test_responsive_with_latency(self) -> None:
        info = HealthInfo(
            health_status=HealthStatus.RESPONSIVE,
            icmp_latency_ms=4.0,
            http_latency_ms=12.0,
        )
        assert info.icmp_latency_ms == 4.0
        assert info.http_latency_ms == 12.0


class TestOrchestratorDiagnostics:
    """OrchestratorDiagnostics snapshot."""

    def test_initial_state(self) -> None:
        """Metrics before any poll."""
        metrics = OrchestratorDiagnostics(
            poll_duration=None,
            auth_failure_streak=0,
            circuit_breaker_open=False,
            session_is_valid=False,
        )
        assert metrics.resource_fetches == []
        assert metrics.last_poll_timestamp is None

    def test_after_successful_poll(self) -> None:
        """Metrics after a successful collection."""
        fetches = [
            ResourceFetch("/status.html", 800.0, 12480),
            ResourceFetch("/info.html", 1200.0, 8192),
        ]
        metrics = OrchestratorDiagnostics(
            poll_duration=2.5,
            auth_failure_streak=0,
            circuit_breaker_open=False,
            session_is_valid=True,
            resource_fetches=fetches,
            last_poll_timestamp=1234567.89,
        )
        assert len(metrics.resource_fetches) == 2
        assert metrics.poll_duration == 2.5


class TestRestartResult:
    """RestartResult recovery status."""

    def test_success(self) -> None:
        result = RestartResult(
            success=True,
            phase_reached=RestartPhase.COMPLETE,
            elapsed_seconds=150.0,
        )
        assert result.error == ""

    def test_timeout(self) -> None:
        result = RestartResult(
            success=False,
            phase_reached=RestartPhase.TIMEOUT,
            elapsed_seconds=420.0,
            error="Recovery timed out",
        )
        assert not result.success
        assert result.phase_reached == RestartPhase.TIMEOUT
