"""Phase 2: Auth strategy detection.

Dispatches to transport-specific modules:
- ``auth_http`` - HTTP decision tree (6 strategies)
- ``auth_hnap`` - HNAP HMAC detection

Per ONBOARDING_SPEC.md Phase 2.
"""

from __future__ import annotations

from typing import Any

from .auth_hnap import detect_hnap_auth
from .auth_http import detect_http_auth
from .types import AuthDetail

# Re-export for backwards compatibility with existing imports
__all__ = ["AuthDetail", "detect_auth"]


def detect_auth(
    entries: list[dict[str, Any]],
    transport: str,
    warnings: list[str],
    hard_stops: list[str],
) -> AuthDetail:
    """Detect auth strategy from HAR entries.

    Dispatches to transport-specific detection:
    - HNAP: always ``hnap`` strategy, detect hmac_algorithm
    - HTTP: walks the Phase 2 decision tree

    Args:
        entries: HAR ``log.entries`` list.
        transport: Detected transport (``http`` or ``hnap``).
        warnings: Mutable list to append warnings to.
        hard_stops: Mutable list to append hard stops to.

    Returns:
        AuthDetail with strategy, extracted fields, and confidence.
    """
    if transport == "hnap":
        return detect_hnap_auth(entries, warnings)
    return detect_http_auth(entries, warnings, hard_stops)
