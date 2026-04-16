"""Log and diagnostics analysis for Cable Modem Monitor Core.

Provides structured event parsing from Core logger output and live
orchestrator diagnostics.

Public API:
    Models: PollEvent, HealthEvent, BackoffEvent, RecoveryEvent, CoreAnalysis
    Parsers: parse_core_logs, parse_diagnostics
    Utilities: parse_ts
"""

from __future__ import annotations

from .diagnostics import parse_diagnostics
from .log_parser import CORE_PATTERNS, parse_core_logs, parse_ts
from .models import (
    BackoffEvent,
    CoreAnalysis,
    HealthEvent,
    PollEvent,
    RecoveryEvent,
)

__all__ = [
    "BackoffEvent",
    "CORE_PATTERNS",
    "CoreAnalysis",
    "HealthEvent",
    "PollEvent",
    "RecoveryEvent",
    "parse_core_logs",
    "parse_diagnostics",
    "parse_ts",
]
