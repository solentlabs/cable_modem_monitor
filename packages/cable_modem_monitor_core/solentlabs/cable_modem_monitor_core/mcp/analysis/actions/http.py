"""Phase 4 - HTTP action detection.

Scans HAR entries for HTTP logout and restart endpoints using URL
pattern matching. Patterns are loaded from ``action_patterns.json``.

Per docs/ONBOARDING_SPEC.md Phase 4 (HTTP transport).
"""

from __future__ import annotations

import re
from typing import Any

from ...validation.har_utils import parse_form_params, path_from_url
from ..types import ActionDetail, ActionsDetail, CoreGap
from .patterns import get_logout_patterns, get_restart_patterns

# ---------------------------------------------------------------------------
# Endpoint patterns (loaded from action_patterns.json)
# ---------------------------------------------------------------------------

_LOGOUT_PATTERNS = get_logout_patterns()
_RESTART_PATTERNS = get_restart_patterns()


_ACTION_PARAM_INDICATORS = frozenset({"reboot", "restart", "reset", "logout", "logoff", "action", "security"})


def detect_http_actions(
    entries: list[dict[str, Any]],
    warnings: list[str] | None = None,
    core_gaps: list[CoreGap] | None = None,
) -> ActionsDetail:
    """Detect HTTP logout and restart actions.

    Args:
        entries: HAR ``log.entries`` list.
        warnings: Mutable list to append suggestions to.
        core_gaps: Mutable list to append core gap items to.

    Returns:
        ActionsDetail with detected HTTP logout and restart actions.
    """
    if warnings is None:
        warnings = []
    if core_gaps is None:
        core_gaps = []
    logout = _find_http_action(entries, _LOGOUT_PATTERNS, "logout", warnings)
    restart = _find_http_action(entries, _RESTART_PATTERNS, "restart", warnings)

    # Flag unmatched action-like POSTs as core gaps
    if logout is None or restart is None:
        _detect_unmatched_actions(entries, logout, restart, core_gaps)

    return ActionsDetail(logout=logout, restart=restart)


_PAGE_EXTENSIONS = frozenset({".asp", ".htm", ".html", ".php"})


def _find_http_action(
    entries: list[dict[str, Any]],
    patterns: tuple[re.Pattern[str], ...],
    action_name: str,
    warnings: list[str],
) -> ActionDetail | None:
    """Find an HTTP action matching any of the given URL patterns."""
    for idx, entry in enumerate(entries):
        req = entry["request"]
        url = req.get("url", "")
        method = req.get("method", "")
        path = path_from_url(url)

        if any(p.search(path) for p in patterns):
            params = parse_form_params(req.get("postData", {}))
            _suggest_pre_fetch_url(entries, idx, path, action_name, warnings)
            return ActionDetail(
                type="http",
                method=method,
                endpoint=path,
                params=params,
            )

    return None


def _suggest_pre_fetch_url(
    entries: list[dict[str, Any]],
    action_idx: int,
    action_path: str,
    action_name: str,
    warnings: list[str],
) -> None:
    """Suggest pre_fetch_url when a preceding page GET shares a keyword.

    Some modems require fetching an HTML page before submitting an
    action form (to establish session state or extract a dynamic
    endpoint). This is a heuristic suggestion — the keyword overlap
    is not definitive evidence. The ``/modem-intake`` skill should
    surface this for contributor confirmation.
    """
    # Extract the last path segment as keyword
    parts = action_path.rstrip("/").rsplit("/", 1)
    if len(parts) != 2:
        return
    keyword = parts[1]
    if not keyword or len(keyword) < 4:
        return

    # Scan up to 5 preceding entries for a related GET
    start = max(0, action_idx - 5)
    for i in range(action_idx - 1, start - 1, -1):
        req = entries[i]["request"]
        if req.get("method", "") != "GET":
            continue
        path = path_from_url(req.get("url", ""))
        suffix = path.rsplit(".", 1)[-1] if "." in path else ""
        if f".{suffix}" not in _PAGE_EXTENSIONS:
            continue
        if keyword.lower() in path.lower():
            warnings.append(
                f"SUGGESTION: {action_name} action POST to {action_path} "
                f"was preceded by GET {path} — this may indicate a "
                f"pre_fetch_url requirement. If confirmed, add "
                f'pre_fetch_url: "{path}" and '
                f'endpoint_pattern: "{keyword}" to the action config.'
            )
            return


def _detect_unmatched_actions(
    entries: list[dict[str, Any]],
    found_logout: ActionDetail | None,
    found_restart: ActionDetail | None,
    core_gaps: list[CoreGap],
) -> None:
    """Flag POST requests with action-like params as core gaps.

    Scans entries for POSTs whose param names contain action indicators
    but whose URLs didn't match the pattern lists.
    """
    matched_endpoints = set()
    if found_logout:
        matched_endpoints.add(found_logout.endpoint)
    if found_restart:
        matched_endpoints.add(found_restart.endpoint)

    for entry in entries:
        req = entry["request"]
        if req.get("method", "") != "POST":
            continue
        path = path_from_url(req.get("url", ""))
        if path in matched_endpoints:
            continue

        params = parse_form_params(req.get("postData", {}))
        if not params:
            continue

        indicators = [ind for ind in _ACTION_PARAM_INDICATORS if any(ind in name.lower() for name in params)]
        if not indicators:
            continue

        # Classify as logout-like or restart-like
        logout_indicators = {"logout", "logoff"}
        restart_indicators = {"reboot", "restart", "reset", "action", "security"}

        if not found_logout and indicators and logout_indicators & set(indicators):
            category = "unmatched_logout"
        elif not found_restart and restart_indicators & set(indicators):
            category = "unmatched_restart"
        else:
            continue

        core_gaps.append(
            CoreGap(
                phase="actions",
                category=category,
                summary=f"POST to {path} has action-like params but URL not in patterns",
                evidence={
                    "endpoint": path,
                    "method": "POST",
                    "params": params,
                    "indicators": indicators,
                },
            )
        )
