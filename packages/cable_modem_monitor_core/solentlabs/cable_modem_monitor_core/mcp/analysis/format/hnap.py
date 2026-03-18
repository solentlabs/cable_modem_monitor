"""Phase 5 - HNAP format detection (stub).

This stub produces a hard stop when HNAP transport is detected.
HNAP format detection is not yet implemented.

Per docs/ONBOARDING_SPEC.md Phase 5 (HNAP transport).
"""

from __future__ import annotations

from typing import Any

from ...validation.har_utils import HARD_STOP_PREFIX


def detect_hnap_sections(
    entries: list[dict[str, Any]],
    warnings: list[str],
    hard_stops: list[str],
) -> dict[str, Any]:
    """Detect HNAP format and field mappings.

    Currently a stub -- returns a hard stop.

    Args:
        entries: HAR ``log.entries`` list.
        warnings: Mutable list to append warnings to.
        hard_stops: Mutable list to append hard stops to.

    Returns:
        Empty dict (analysis cannot proceed).
    """
    hard_stops.append(
        f"{HARD_STOP_PREFIX} HNAP format detection is not yet implemented. "
        "See ONBOARDING_SPEC.md Phase 5 (HNAP transport). "
        "Phases 5-6 cannot proceed for HNAP modems."
    )
    return {}
