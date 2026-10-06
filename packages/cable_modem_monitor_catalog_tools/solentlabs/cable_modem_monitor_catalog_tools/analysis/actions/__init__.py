"""Phase 4 - Action detection.

Public API: ``detect_actions()`` dispatches to transport-specific
modules (``hnap``, ``http``) and classifies credential params across
detected actions.

Per docs/ONBOARDING_SPEC.md Phase 4.
"""

from __future__ import annotations

from typing import Any

from ..ambiguity import Ambiguity
from .hnap import detect_hnap_actions
from .http import detect_http_actions
from .types import ActionDetail, ActionsDetail

__all__ = ["ActionDetail", "ActionsDetail", "detect_actions"]


def detect_actions(
    entries: list[dict[str, Any]],
    transport: str,
    warnings: list[str] | None = None,
    ambiguities: list[Ambiguity] | None = None,
) -> ActionsDetail:
    """Detect logout and restart actions from HAR entries.

    Dispatches to transport-specific detection, then classifies
    credential params across all detected actions.

    Args:
        entries: HAR ``log.entries`` list.
        transport: Detected transport (``http``, ``hnap`` or ``cbn``).
        warnings: Mutable list to append suggestions to.
        ambiguities: Mutable list to append action endpoint candidates to.

    Returns:
        ActionsDetail with detected actions and credential annotations.
    """
    if warnings is None:
        warnings = []
    if ambiguities is None:
        ambiguities = []
    if transport == "hnap":
        result = detect_hnap_actions(entries)
    elif transport == "cbn":
        # A CBN action is a setter fun code, not a URL; the HTTP tree would
        # invent an http action that transport cbn rejects.
        result = ActionsDetail()
    else:
        result = detect_http_actions(entries, warnings, ambiguities)
    result._classify_credentials()
    return result
