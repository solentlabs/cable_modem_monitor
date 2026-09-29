"""Phase 4 - Action detection.

Public API: ``detect_actions()`` dispatches to transport-specific
modules (``hnap``, ``http``) and classifies credential params across
detected actions.

Per docs/ONBOARDING_SPEC.md Phase 4.
"""

from __future__ import annotations

from typing import Any

from ..types import CoreGap
from .hnap import detect_hnap_actions
from .http import detect_http_actions
from .types import ActionDetail, ActionsDetail

__all__ = ["ActionDetail", "ActionsDetail", "detect_actions"]


def detect_actions(
    entries: list[dict[str, Any]],
    transport: str,
    warnings: list[str] | None = None,
    core_gaps: list[CoreGap] | None = None,
) -> ActionsDetail:
    """Detect logout and restart actions from HAR entries.

    Dispatches to transport-specific detection, then classifies
    credential params across all detected actions.

    Args:
        entries: HAR ``log.entries`` list.
        transport: Detected transport (``http``, ``hnap`` or ``cbn``).
        warnings: Mutable list to append suggestions to.
        core_gaps: Mutable list to append core gap items to.

    Returns:
        ActionsDetail with detected actions and credential annotations.
    """
    if warnings is None:
        warnings = []
    if core_gaps is None:
        core_gaps = []
    if transport == "hnap":
        result = detect_hnap_actions(entries)
    elif transport == "cbn":
        # A CBN action is a setter fun code, not a URL; the HTTP tree would
        # invent an http action that transport cbn rejects.
        result = ActionsDetail()
    else:
        result = detect_http_actions(entries, warnings, core_gaps)
    result._classify_credentials()
    return result
