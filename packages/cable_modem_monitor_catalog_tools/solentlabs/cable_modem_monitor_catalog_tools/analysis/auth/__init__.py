"""Phase 2 - Auth strategy detection.

Public API: ``detect_auth()`` dispatches to transport-specific modules
(``hnap``, ``json_rpc``, ``cbn``, ``http``).

Per docs/ONBOARDING_SPEC.md Phase 2.
"""

from __future__ import annotations

from typing import Any

from ..ambiguity import Ambiguity
from ..types import CoreGap
from .cbn import detect_cbn_auth
from .hnap import detect_hnap_auth
from .http import detect_http_auth
from .json_rpc import detect_json_rpc_auth
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
    - JSON-RPC: always ``json_rpc``; fields from the login call, error
      codes as ambiguities
    - CBN: always ``form_cbn``; fields from the login call
    - HTTP: walks the Phase 2 decision tree; a JSON login's strategy is
      an ambiguity

    Args:
        entries: HAR ``log.entries`` list.
        transport: Detected transport (``http``, ``hnap``, ``json_rpc`` or ``cbn``).
        warnings: Mutable list to append warnings to.
        hard_stops: Mutable list to append hard stops to.
        core_gaps: Mutable list to append core gap items to.
        ambiguities: Mutable list to append ambiguities to.

    Returns:
        AuthDetail with strategy and extracted fields.
    """
    if core_gaps is None:
        core_gaps = []
    if ambiguities is None:
        ambiguities = []
    if transport == "hnap":
        return detect_hnap_auth(entries, warnings)
    if transport == "json_rpc":
        return detect_json_rpc_auth(entries, warnings, ambiguities)
    if transport == "cbn":
        return detect_cbn_auth(entries, warnings)
    return detect_http_auth(entries, warnings, hard_stops, core_gaps, ambiguities)
