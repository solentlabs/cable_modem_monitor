"""Orchestration layer — runtime poll cycle management.

ModemDataCollector executes a single data collection. Orchestrator
composes the collector with policy logic. HealthMonitor runs
lightweight probes for reachability. Recovery owns the polling-cadence
window triggered by a restart command, observed outage, or a
reboot-signal vote. ``run_restart`` dispatches the reboot command as
a one-shot operation.

See ORCHESTRATION_SPEC.md for interface contracts and
RUNTIME_POLLING_SPEC.md for behavioral rules.
"""

from __future__ import annotations

from .actions import ActionResult, execute_action, execute_hnap_action, execute_http_action
from .collector import LoginLockoutError, ModemDataCollector
from .event_payload import (
    SCHEMA_VERSION,
    ChannelPayload,
    HealthInfoPayload,
    ModemDataPayload,
    SnapshotEventPayload,
)
from .factory import (
    apply_credential_encoding,
    create_collector,
    create_orchestrator,
)
from .models import (
    HealthInfo,
    ModemResult,
    ModemSnapshot,
    OrchestratorDiagnostics,
    ResourceFetch,
    RestartResult,
)
from .modem_health import HealthMonitor
from .orchestrator import Orchestrator
from .policy import SignalPolicy
from .recovery import Recovery
from .restart import RestartNotSupportedError, run_restart
from .signals import (
    CollectorSignal,
    ConnectionStatus,
    DocsisStatus,
    HealthStatus,
)
from .status import derive_connection_status, enrich_docsis_status

__all__ = [
    "ActionResult",
    "ChannelPayload",
    "HealthInfoPayload",
    "ModemDataPayload",
    "SCHEMA_VERSION",
    "SnapshotEventPayload",
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
    "Recovery",
    "ResourceFetch",
    "RestartNotSupportedError",
    "RestartResult",
    "SignalPolicy",
    "apply_credential_encoding",
    "create_collector",
    "create_orchestrator",
    "derive_connection_status",
    "enrich_docsis_status",
    "execute_action",
    "execute_hnap_action",
    "execute_http_action",
    "run_restart",
]
