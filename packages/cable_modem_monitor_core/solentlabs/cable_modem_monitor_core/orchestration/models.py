"""Data models for the orchestration layer.

Result types, diagnostics, and health info dataclasses. These are the
contracts between orchestration components and consumers.

See ORCHESTRATION_SPEC.md Data Models section.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .signals import (
    CollectorSignal,
    ConnectionStatus,
    DocsisStatus,
    HealthStatus,
    RestartPhase,
)


@dataclass
class ModemResult:
    """Result of a single data collection attempt.

    success=True means the collection pipeline ran without errors.
    It does NOT mean channels were found -- a modem without cable
    signal returns success=True with empty channel lists. The
    orchestrator interprets the data and derives connection status.

    Attributes:
        success: Whether the collection pipeline completed without error.
        modem_data: Parsed channel and system_info data. Present on
            success (may have empty channel lists). None on failure.
        signal: Failure classification when success is False.
            Always OK when success is True.
        error: Human-readable error detail for logging/diagnostics.
            Empty string on success.
    """

    success: bool
    modem_data: dict[str, Any] | None = None
    signal: CollectorSignal = CollectorSignal.OK
    error: str = ""


@dataclass
class ResourceFetch:
    """Timing and size for a single resource fetch.

    Captured by the ResourceLoader during data collection. One entry
    per resource page (e.g., /status.html, /connection.html).

    Attributes:
        path: Resource path (e.g., "/status.html").
        duration_ms: Fetch time in milliseconds.
        size_bytes: Response body size in bytes.
    """

    path: str
    duration_ms: float
    size_bytes: int


@dataclass
class HealthInfo:
    """Result of a health probe cycle.

    Only contains actual probe measurements. The HealthMonitor considers
    collection evidence internally when deriving health_status, but does
    not fabricate probe results -- None means "not measured."

    Attributes:
        health_status: Derived status from probe combination and
            collection evidence.
        icmp_latency_ms: Round-trip time in milliseconds. None if
            ICMP failed, not supported, or not attempted.
        http_latency_ms: HTTP response time in milliseconds. None if
            HTTP failed, not attempted, or suppressed by collection
            evidence.
    """

    health_status: HealthStatus
    icmp_latency_ms: float | None = None
    http_latency_ms: float | None = None


@dataclass
class ModemSnapshot:
    """Point-in-time snapshot of everything the orchestrator knows.

    Top-level result consumers receive from get_modem_data(). Combines
    the ModemDataCollector output, health probe output, and
    orchestrator-derived fields into a single structure.

    Attributes:
        connection_status: Derived from collector signal and data.
        docsis_status: Derived from downstream lock_status fields.
        modem_data: Parsed channel and system_info data. None on
            collection failure.
        health_info: Health probe results. None if no health monitor.
        metrics: Computed aggregate fields (e.g., total_corrected).
            Empty dict if no aggregates configured.
        collector_signal: Raw signal from the collector (for diagnostics).
        error: Human-readable error summary.
    """

    connection_status: ConnectionStatus
    docsis_status: DocsisStatus
    modem_data: dict[str, Any] | None = None
    health_info: HealthInfo | None = None
    metrics: dict[str, int | float] = field(default_factory=dict)
    collector_signal: CollectorSignal = CollectorSignal.OK
    error: str = ""


@dataclass
class OrchestratorDiagnostics:
    """Read-only snapshot of operational diagnostics.

    Returned by diagnostics(). No side effects. Safe to call at any time.

    Attributes:
        poll_duration: Wall-clock time of last get_modem_data() call
            in seconds. None if never polled.
        auth_failure_streak: Current consecutive auth-related failure
            count. 0 when healthy.
        circuit_breaker_open: Whether polling is stopped due to
            persistent auth failures.
        session_is_valid: Current session state from the collector.
        resource_fetches: Per-resource timing and size from the last
            successful collection.
        last_poll_timestamp: Monotonic time of last get_modem_data()
            call. None if never polled.
    """

    poll_duration: float | None
    auth_failure_streak: int
    circuit_breaker_open: bool
    session_is_valid: bool
    resource_fetches: list[ResourceFetch] = field(default_factory=list)
    last_poll_timestamp: float | None = None


@dataclass
class RestartResult:
    """Result of a modem restart and recovery sequence.

    Attributes:
        success: Whether the modem recovered within the timeout.
        phase_reached: Which recovery phase completed.
        elapsed_seconds: Total time from restart command to result.
        error: Human-readable error if recovery failed or timed out.
    """

    success: bool
    phase_reached: RestartPhase
    elapsed_seconds: float
    error: str = ""
