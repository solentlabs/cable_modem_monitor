"""Phase 2 - Auth strategy detection.

Public API: ``AuthDetail.detect()`` dispatches to transport-specific
modules (``hnap``, ``http``).

Per docs/ONBOARDING_SPEC.md Phase 2.
"""

from __future__ import annotations

from .types import AuthDetail

__all__ = ["AuthDetail"]
