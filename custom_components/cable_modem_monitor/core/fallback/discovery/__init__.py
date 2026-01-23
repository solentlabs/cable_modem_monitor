"""Discovery module for modem identification and setup.

This module provides:
- Signal-based discovery for identifying unknown modems
- Discovery pipeline for config flow setup (response-driven, single-pass)
"""

from .pipeline import (
    AuthResult,
    ConnectivityResult,
    DiscoveryPipelineResult,
    ParserResult,
    ValidationResult,
    run_discovery_pipeline,
)
from .signals import DiscoveryResult, DiscoverySignal, SignalType

__all__ = [
    # Pipeline (config flow)
    "run_discovery_pipeline",
    "DiscoveryPipelineResult",
    "ConnectivityResult",
    "AuthResult",
    "ParserResult",
    "ValidationResult",
    # Signals (discovery intelligence)
    "DiscoveryResult",
    "DiscoverySignal",
    "SignalType",
]
