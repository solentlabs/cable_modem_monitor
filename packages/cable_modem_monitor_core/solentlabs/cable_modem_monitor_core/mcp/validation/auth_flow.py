"""Step 2: Auth flow validation.

Checks the first request to determine if the HAR captured a pre-auth
flow (login visible) or is post-auth only (browser had existing session).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..analysis.auth.patterns import get_login_url_patterns
from .har_utils import (
    HARD_STOP_PREFIX,
    has_set_cookie,
    is_hnap_request,
    lower_headers,
)

# Domain-specific: modem session cookie name indicators
_SESSION_COOKIE_INDICATORS: frozenset[str] = frozenset(
    {
        "sessionid",
        "session",
        "phpsessid",
        "jsessionid",
        "sid",
        "uid",
        "token",
        "auth",
    }
)

# Login endpoint patterns (shared via auth_patterns.json)
_LOGIN_URL_PATTERNS: tuple[str, ...] = get_login_url_patterns()


@dataclass
class AuthArtifacts:
    """Auth-related signals found across HAR entries."""

    any: bool = False
    login_post: bool = False
    hnap: bool = False


def validate_auth_flow(entries: list[dict[str, Any]], issues: list[str]) -> bool:
    """Check whether the HAR contains an auth flow. Returns True if detected.

    Appends HARD STOP issues for: session cookies on first request,
    Authorization header on first request (post-auth HAR).
    """
    first_req = entries[0]["request"]
    first_resp = entries[0]["response"]
    first_status = first_resp.get("status", 0)

    # First request carries session cookies -> post-auth HAR
    session_cookie_names = _get_session_cookie_names(first_req.get("cookies", []))
    if session_cookie_names:
        issues.append(
            f"{HARD_STOP_PREFIX} First request carries session cookies "
            f"({', '.join(session_cookie_names)}) — browser had existing session. "
            f"Please recapture using incognito/private browsing."
        )
        return False

    # 401/403 -> pre-auth captured, auth challenge visible
    if first_status in (401, 403):
        return True

    # 301/302 -> redirect to login page
    if first_status in (301, 302):
        return True

    # 200 -> could be no-auth, login page, or post-auth
    if first_status == 200:
        return _classify_first_200(entries, issues)

    # Other statuses (500, etc.) — unusual, not auth flow
    return False


def _classify_first_200(entries: list[dict[str, Any]], issues: list[str]) -> bool:
    """Classify a 200 first response as login page, no-auth, or post-auth."""
    artifacts = _scan_auth_artifacts(entries)

    if not artifacts.any:
        return False

    if artifacts.login_post or artifacts.hnap:
        return True

    # Has auth artifacts but no clear login flow — check for post-auth
    if _has_authorization_on_first_request(entries):
        issues.append(
            f"{HARD_STOP_PREFIX} First request carries Authorization header — "
            "browser had existing session. Please recapture using "
            "incognito/private browsing."
        )
        return False

    return True


def _scan_auth_artifacts(entries: list[dict[str, Any]]) -> AuthArtifacts:
    """Scan all entries for auth-related artifacts."""
    artifacts = AuthArtifacts()

    for i, entry in enumerate(entries):
        req = entry["request"]
        resp = entry["response"]
        method = req.get("method", "")
        url = req.get("url", "")
        req_hdrs = lower_headers(req)

        if is_hnap_request(url, req_hdrs):
            artifacts.hnap = artifacts.any = True

        if method == "POST" and _is_login_url(url):
            artifacts.login_post = artifacts.any = True

        if "authorization" in req_hdrs:
            artifacts.any = True

        if i > 0 and has_set_cookie(resp):
            artifacts.any = True

    return artifacts


def _has_authorization_on_first_request(entries: list[dict[str, Any]]) -> bool:
    """Check if the first request has an Authorization header (post-auth HAR)."""
    all_200 = all(e["response"].get("status") == 200 for e in entries)
    if not all_200:
        return False
    return "authorization" in lower_headers(entries[0]["request"])


def _is_login_url(url: str) -> bool:
    """Check if a URL matches known modem login endpoint patterns."""
    lower = url.lower()
    return any(p in lower for p in _LOGIN_URL_PATTERNS)


def _get_session_cookie_names(cookies: list[dict[str, Any]]) -> list[str]:
    """Return cookie names that suggest a pre-existing session."""
    found = []
    for cookie in cookies:
        name = cookie.get("name", "").lower()
        if any(ind in name for ind in _SESSION_COOKIE_INDICATORS):
            found.append(cookie.get("name", ""))
    return found
