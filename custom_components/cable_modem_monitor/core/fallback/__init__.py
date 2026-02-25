"""Fallback modem subsystem for unknown/unsupported modems.

This module provides the infrastructure for handling modems that don't have
a dedicated parser (modem.yaml). It's isolated from the main orchestrator
to keep the core code clean and simple.

Components:
- FallbackOrchestrator: Extends DataOrchestrator with auth discovery
- UniversalFallbackParser: Minimal parser for HTML capture (import from .parser)
- AuthDiscovery: Response-driven auth detection logic

When to use:
- User selects "Unknown Modem (Fallback Mode)" in config flow
- Auto-detection fails to find a matching parser

The fallback system enables:
- Basic connectivity monitoring (ping/HTTP latency)
- HTML capture for parser development
- Response-driven auth discovery (trying various strategies)

Note:
    UniversalFallbackParser is NOT exported here to avoid early initialization.
    Import directly from .parser when needed (after other parsers are loaded).
"""

from .data_orchestrator import FallbackOrchestrator

__all__ = ["FallbackOrchestrator"]
