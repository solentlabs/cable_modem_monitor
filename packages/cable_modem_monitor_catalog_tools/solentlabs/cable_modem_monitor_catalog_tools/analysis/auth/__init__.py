"""Phase 2 - Auth strategy detection.

Public API: ``detect_auth()`` dispatches to transport-specific modules
(``hnap``, ``jsonrpc``, ``http``).

Per docs/ONBOARDING_SPEC.md Phase 2.
"""

from __future__ import annotations

from typing import Any

from ..ambiguity import Ambiguity
from ..types import CoreGap
from .hnap import detect_hnap_auth
from .http import detect_http_auth
from .jsonrpc import detect_jsonrpc_auth
from .types import AuthDetail

__all__ = ["AuthDetail", "detect_auth"]


def detect_auth(
    entries: list[dict[str, Any]],
    transport: str,
    warnings: list[str],
    hard_stops: list[str],
    core_gaps: list[CoreGap] | None = None,
    ambiguities: list[Ambiguity] | None = None,
) -> AuthDetail:
    """Detect auth strategy from HAR entries.

    Dispatches to transport-specific detection:

    - HNAP: always ``hnap`` strategy, detect hmac_algorithm
    - JSON-RPC: always ``jsonrpc``; fields from the login call, error
      codes as ambiguities
    - HTTP: walks the Phase 2 decision tree

    Args:
        entries: HAR ``log.entries`` list.
        transport: Detected transport (``http``, ``hnap`` or ``jsonrpc``).
        warnings: Mutable list to append warnings to.
        hard_stops: Mutable list to append hard stops to.
        core_gaps: Mutable list to append core gap items to.
        ambiguities: Mutable list to append ambiguities to.

    Returns:
        AuthDetail with strategy, extracted fields, and confidence.
    """
    if core_gaps is None:
        core_gaps = []
    if ambiguities is None:
        ambiguities = []
    if transport == "hnap":
        return detect_hnap_auth(entries, warnings)
    if transport == "jsonrpc":
        return detect_jsonrpc_auth(entries, warnings, ambiguities)
    return detect_http_auth(entries, warnings, hard_stops, core_gaps)
