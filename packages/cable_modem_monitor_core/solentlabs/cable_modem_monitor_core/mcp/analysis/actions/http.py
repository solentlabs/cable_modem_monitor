"""Phase 4 - HTTP action detection.

Scans HAR entries for HTTP logout and restart endpoints using URL
pattern matching.

Per docs/ONBOARDING_SPEC.md Phase 4 (HTTP transport).
"""

from __future__ import annotations

import re
from typing import Any

from ...validation.har_utils import parse_form_params, path_from_url
from ..types import ActionDetail, ActionsDetail

# ---------------------------------------------------------------------------
# Endpoint patterns (domain-specific)
# ---------------------------------------------------------------------------

_LOGOUT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"/logout", re.IGNORECASE),
    re.compile(r"/goform/logout", re.IGNORECASE),
    re.compile(r"/api/.*/logout", re.IGNORECASE),
    re.compile(r"/api/.*/session/logout", re.IGNORECASE),
)

_RESTART_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"/reboot", re.IGNORECASE),
    re.compile(r"/restart", re.IGNORECASE),
    re.compile(r"/goform/.*[Ss]ecurity", re.IGNORECASE),
    re.compile(r"/goform/.*[Rr]eboot", re.IGNORECASE),
    re.compile(r"/api/.*/device/reboot", re.IGNORECASE),
)


def detect_http_actions(entries: list[dict[str, Any]]) -> ActionsDetail:
    """Detect HTTP logout and restart actions.

    Args:
        entries: HAR ``log.entries`` list.

    Returns:
        ActionsDetail with detected HTTP logout and restart actions.
    """
    logout = _find_http_action(entries, _LOGOUT_PATTERNS)
    restart = _find_http_action(entries, _RESTART_PATTERNS)
    return ActionsDetail(logout=logout, restart=restart)


def _find_http_action(
    entries: list[dict[str, Any]],
    patterns: tuple[re.Pattern[str], ...],
) -> ActionDetail | None:
    """Find an HTTP action matching any of the given URL patterns."""
    for entry in entries:
        req = entry["request"]
        url = req.get("url", "")
        method = req.get("method", "")
        path = path_from_url(url)

        if any(p.search(path) for p in patterns):
            params = parse_form_params(req.get("postData", {}))
            return ActionDetail(
                type="http",
                method=method,
                endpoint=path,
                params=params,
            )

    return None
