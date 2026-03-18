"""HAR analysis phases for modem onboarding.

Pipeline phases:

- Phase 1: ``transport`` - HNAP vs HTTP detection
- Phase 2: ``auth`` - auth strategy detection (HTTP / HNAP)
- Phase 3: ``session`` - cookie, header, and token detection (HTTP only)
- Phase 4: ``actions`` - logout / restart action detection (HTTP / HNAP)
- Phase 5: ``format`` - data page format classification (HTTP / HNAP)
- Phase 6: ``mapping`` - field mapping, channel type, filters, system_info

Shared result types live in ``types``.
"""

from .types import ActionDetail, ActionsDetail, AuthDetail

__all__ = ["ActionDetail", "ActionsDetail", "AuthDetail"]
