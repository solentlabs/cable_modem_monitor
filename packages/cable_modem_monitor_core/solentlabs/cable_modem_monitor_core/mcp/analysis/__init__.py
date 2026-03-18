"""HAR analysis phases for modem onboarding.

Each phase dispatches to transport-specific modules:

- transport: Phase 1 - HNAP vs HTTP detection
- auth: Phase 2 - dispatch to auth_http / auth_hnap
- session: Phase 3 - Cookie, header, and token detection (HTTP only)
- actions: Phase 4 - dispatch to actions_http / actions_hnap

Shared result types live in ``types.py``.
"""

from .types import ActionDetail, ActionsDetail, AuthDetail

__all__ = ["ActionDetail", "ActionsDetail", "AuthDetail"]
