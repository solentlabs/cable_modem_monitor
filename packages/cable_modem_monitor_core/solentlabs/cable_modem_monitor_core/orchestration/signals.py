"""Signal and status enums for the orchestration layer.

CollectorSignal classifies infrastructure failures from a data
collection attempt. Status enums represent derived state from
collection outcomes and health probes.

See ORCHESTRATION_SPEC.md for the full signal catalog and status
derivation rules.
"""

from __future__ import annotations

from enum import Enum


class CollectorSignal(Enum):
    """Signals from a data collection attempt.

    These represent infrastructure failures -- the collection pipeline
    could not complete. The orchestrator maps them to policy decisions.

    Notably absent: zero channels. Empty data is a valid collection
    result (signal=OK with empty channel lists), not a failure. The
    orchestrator interprets empty data using session state and modem
    context.
    """

    OK = "ok"
    AUTH_FAILED = "auth_failed"
    AUTH_LOCKOUT = "auth_lockout"
    CONNECTIVITY = "connectivity"
    LOAD_ERROR = "load_error"
    LOAD_AUTH = "load_auth"
    PARSE_ERROR = "parse_error"


class ConnectionStatus(Enum):
    """Modem connection status derived from poll outcome."""

    ONLINE = "online"
    AUTH_FAILED = "auth_failed"
    PARSER_ISSUE = "parser_issue"
    UNREACHABLE = "unreachable"
    NO_SIGNAL = "no_signal"


class DocsisStatus(Enum):
    """DOCSIS lock status derived from downstream channels."""

    OPERATIONAL = "operational"
    PARTIAL_LOCK = "partial_lock"
    NOT_LOCKED = "not_locked"
    UNKNOWN = "unknown"


class HealthStatus(Enum):
    """Modem health derived from probe results."""

    RESPONSIVE = "responsive"
    DEGRADED = "degraded"
    ICMP_BLOCKED = "icmp_blocked"
    UNRESPONSIVE = "unresponsive"
    UNKNOWN = "unknown"


class RestartPhase(Enum):
    """Recovery phases during a modem restart."""

    COMMAND_SENT = "command_sent"
    WAITING_RESPONSE = "waiting"
    CHANNEL_SYNC = "channel_sync"
    COMPLETE = "complete"
    TIMEOUT = "timeout"
