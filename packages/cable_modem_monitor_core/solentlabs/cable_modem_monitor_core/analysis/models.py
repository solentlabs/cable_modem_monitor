"""Data models for log and diagnostics analysis.

Event types captured from Core logger output, plus the CoreAnalysis
container that aggregates them.  These models are the contracts
between the analysis parsers and any consumer (HA layer, CLI tools,
diagnostics endpoints).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class PollEvent:
    """A single data-collection poll attempt.

    Attributes:
        timestamp: When the poll was recorded.
        model: Modem model tag from the log line.
        duration_s: Wall-clock poll time in seconds.  0.0 when the
            duration source (HA fetch_complete) is unavailable.
        success: Whether the parse stage completed without error.
        ds_channels: Downstream channel count (0 on failure).
        us_channels: Upstream channel count (0 on failure).
    """

    timestamp: datetime
    model: str
    duration_s: float
    success: bool
    ds_channels: int = 0
    us_channels: int = 0


@dataclass
class HealthEvent:
    """A single health-probe result.

    Attributes:
        timestamp: When the health check ran.
        model: Modem model tag.
        status: One of ``"responsive"``, ``"unresponsive"``,
            ``"degraded"``.
        icmp_ms: ICMP round-trip time (0.0 when not measured).
        http_ms: HTTP GET latency (0.0 when not measured).
    """

    timestamp: datetime
    model: str
    status: str
    icmp_ms: float = 0.0
    http_ms: float = 0.0


@dataclass
class BackoffEvent:
    """A connectivity failure that triggered backoff.

    Attributes:
        timestamp: When the failure was logged.
        model: Modem model tag.
        streak: Consecutive failure count at time of log.
        backoff: Number of polls to skip.
    """

    timestamp: datetime
    model: str
    streak: int
    backoff: int


@dataclass
class RecoveryEvent:
    """A recovery or backoff-clear event.

    Attributes:
        timestamp: When recovery was detected.
        model: Modem model tag.
        transition: Recovery type (e.g. ``"backoff_cleared"``).
    """

    timestamp: datetime
    model: str
    transition: str


@dataclass
class CoreAnalysis:
    """Aggregated analysis from Core logger output.

    Produced by :func:`~.log_parser.parse_core_logs` (from log lines)
    or :func:`~.diagnostics.parse_diagnostics` (from a live snapshot).
    Consumers layer HA-specific events on top.

    Attributes:
        polls: Parsed poll events (success and failure).
        health_checks: Health-probe results.
        backoffs: Connectivity failures with backoff info.
        recoveries: Backoff-clear / recovery events.
        transitions: Status-transition descriptions with timestamps.
    """

    polls: list[PollEvent] = field(default_factory=list)
    health_checks: list[HealthEvent] = field(default_factory=list)
    backoffs: list[BackoffEvent] = field(default_factory=list)
    recoveries: list[RecoveryEvent] = field(default_factory=list)
    transitions: list[tuple[datetime, str]] = field(default_factory=list)


def compute_outage_durations(health_checks: list[HealthEvent]) -> list[timedelta]:
    """Walk health events chronologically to find outage windows.

    An outage starts when status transitions to ``"unresponsive"`` and
    ends when status returns to ``"responsive"``.  Open-ended outages
    (unresponsive at end of data) are not included.

    Args:
        health_checks: Health events, in any order (sorted internally).

    Returns:
        Duration of each closed outage window.
    """
    durations: list[timedelta] = []
    outage_start: datetime | None = None
    prev_status = "responsive"

    for h in sorted(health_checks, key=lambda x: x.timestamp):
        if h.status == "unresponsive" and prev_status != "unresponsive":
            outage_start = h.timestamp
        elif h.status == "responsive" and prev_status == "unresponsive":
            if outage_start:
                durations.append(h.timestamp - outage_start)
            outage_start = None
        prev_status = h.status

    return durations
