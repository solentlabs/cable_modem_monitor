"""Orchestration layer — runtime poll cycle management.

ModemDataCollector executes a single data collection. Orchestrator
composes the collector with policy logic. HealthMonitor runs lightweight
probes for reachability. RestartMonitor handles two-phase restart
recovery.

See ORCHESTRATION_SPEC.md for interface contracts and
RUNTIME_POLLING_SPEC.md for behavioral rules.
"""

from __future__ import annotations

from .actions import execute_hnap_action, execute_http_action, execute_restart_action
from .channel_stability import ChannelStabilityMonitor
from .collector import LoginLockoutError, ModemDataCollector
from .models import (
    HealthInfo,
    ModemResult,
    ModemSnapshot,
    OrchestratorDiagnostics,
    ResourceFetch,
    RestartResult,
)
from .modem_health import HealthMonitor
from .orchestrator import Orchestrator, RestartNotSupportedError
from .policy import SignalPolicy
from .response_monitor import ResponseMonitor
from .restart import RestartMonitor
from .signals import (
    CollectorSignal,
    ConnectionStatus,
    DocsisStatus,
    HealthStatus,
    RestartPhase,
)
from .status import derive_connection_status, derive_docsis_status

__all__ = [
    "ChannelStabilityMonitor",
    "CollectorSignal",
    "ConnectionStatus",
    "DocsisStatus",
    "HealthInfo",
    "HealthMonitor",
    "HealthStatus",
    "LoginLockoutError",
    "ModemDataCollector",
    "ModemResult",
    "ModemSnapshot",
    "Orchestrator",
    "OrchestratorDiagnostics",
    "ResourceFetch",
    "ResponseMonitor",
    "RestartMonitor",
    "RestartNotSupportedError",
    "RestartPhase",
    "RestartResult",
    "SignalPolicy",
    "derive_connection_status",
    "derive_docsis_status",
    "execute_hnap_action",
    "execute_http_action",
    "execute_restart_action",
]
