"""Phase 4 - Action detection.

Dispatches to transport-specific modules:
- ``http`` - URL pattern matching for logout/restart
- ``hnap`` - SOAP action scanning

Per docs/ONBOARDING_SPEC.md Phase 4.
"""

from __future__ import annotations

from typing import Any

from ..types import ActionDetail, ActionsDetail
from .hnap import detect_hnap_actions
from .http import detect_http_actions

__all__ = ["detect_actions"]


def detect_actions(
    entries: list[dict[str, Any]],
    transport: str,
) -> ActionsDetail:
    """Detect logout and restart actions from HAR entries.

    Dispatches to transport-specific detection:
    - HNAP: scans SOAP actions
    - HTTP: matches URL patterns

    Args:
        entries: HAR ``log.entries`` list.
        transport: Detected transport (``http`` or ``hnap``).

    Returns:
        ActionsDetail with detected logout and restart actions.
    """
    if transport == "hnap":
        return detect_hnap_actions(entries)
    return detect_http_actions(entries)
