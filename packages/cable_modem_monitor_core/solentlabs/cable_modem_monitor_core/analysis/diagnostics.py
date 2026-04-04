"""Create a CoreAnalysis snapshot from live orchestrator diagnostics.

Bridges the gap between the structured
:class:`~..orchestration.models.OrchestratorDiagnostics` and the
analysis event model, so consumers can use the same analysis types
regardless of whether the data came from log lines or a live
orchestrator.
"""

from __future__ import annotations

from datetime import datetime

from ..orchestration.models import OrchestratorDiagnostics
from .models import BackoffEvent, CoreAnalysis


def parse_diagnostics(diag: OrchestratorDiagnostics) -> CoreAnalysis:
    """Derive a CoreAnalysis from a live diagnostics snapshot.

    Only fields that map cleanly to analysis events are populated.
    Poll history and health-check history are not available from a
    point-in-time snapshot, so those lists remain empty.

    Args:
        diag: Current orchestrator diagnostics.

    Returns:
        CoreAnalysis with backoff state (if active).
    """
    backoffs: list[BackoffEvent] = []
    if diag.connectivity_streak > 0:
        backoffs.append(
            BackoffEvent(
                timestamp=datetime.min,
                model="",
                streak=diag.connectivity_streak,
                backoff=diag.connectivity_backoff_remaining,
            )
        )

    return CoreAnalysis(backoffs=backoffs)
