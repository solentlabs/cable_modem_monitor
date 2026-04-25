"""Phase 4 - Action detection.

Public API: ``ActionsDetail.detect()`` dispatches to transport-specific
modules (``hnap``, ``http``) and classifies credential params across
detected actions.

Per docs/ONBOARDING_SPEC.md Phase 4.
"""

from __future__ import annotations

from .types import ActionDetail, ActionsDetail

__all__ = ["ActionDetail", "ActionsDetail"]
