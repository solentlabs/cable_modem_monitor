"""Phase 3 - Session detection.

Examines post-login HAR entries for session artifacts: cookies, static
headers (e.g., X-Requested-With), and URL token prefixes.

``max_concurrent`` cannot be determined from HAR (requires live testing)
and is always flagged as unknown.

HNAP transport has implicit session (``uid`` + ``PrivateKey`` cookies,
``HNAP_AUTH`` header) -- this phase returns an empty session for HNAP.
The auth manager sets both cookies from the challenge-response flow;
no session config is needed in modem.yaml.

Per docs/ONBOARDING_SPEC.md Phase 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..validation.har_utils import is_static_resource, lower_headers
from .auth.patterns import get_session_cookie_indicators

# Cookie names that indicate a session (case-insensitive substring match).
# Loaded from auth_patterns.json — single source of truth.
_SESSION_COOKIE_INDICATORS: frozenset[str] = get_session_cookie_indicators()


@dataclass
class SessionDetail:
    """Result of Phase 3 session detection.

    ``cookie_name`` and ``token_prefix`` are detected here but belong
    on the auth strategy in modem.yaml (auth owns the cookie it
    produces). The MCP config generator places them on the auth block.
    """

    cookie_name: str = ""
    max_concurrent: int | None = None
    max_concurrent_confidence: str = "unknown"
    headers: dict[str, str] = field(default_factory=dict)
    token_prefix: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for MCP tool output."""
        return {
            "cookie_name": self.cookie_name,
            "max_concurrent": self.max_concurrent,
            "max_concurrent_confidence": self.max_concurrent_confidence,
            "headers": self.headers,
            "token_prefix": self.token_prefix,
        }


def detect_session(
    entries: list[dict[str, Any]],
    transport: str,
    auth_strategy: str,
    warnings: list[str],
) -> SessionDetail:
    """Detect session configuration from HAR entries.

    Args:
        entries: HAR ``log.entries`` list.
        transport: Detected transport (``http`` or ``hnap``).
        auth_strategy: Detected auth strategy name.
        warnings: Mutable list to append warnings to.

    Returns:
        SessionDetail with detected session configuration.
    """
    # HNAP session is implicit -- the auth manager sets both cookies
    # (uid + PrivateKey) and signs requests via HNAP_AUTH header.
    # No session block needed in modem.yaml.
    if transport == "hnap":
        return SessionDetail()

    # Stateless strategies typically don't need session config
    if auth_strategy == "none":
        # Still scan for unusual patterns (cookie set without login)
        session = _scan_session_artifacts(entries)
        if session.cookie_name:
            warnings.append(
                f"Cookie '{session.cookie_name}' detected on auth:none modem -- "
                "unusual but not invalid. Verify if session tracking is needed."
            )
        return session

    session = _scan_session_artifacts(entries)

    # Infer max_concurrent from session evidence
    _infer_max_concurrent(session, auth_strategy, warnings)

    return session


def _scan_session_artifacts(entries: list[dict[str, Any]]) -> SessionDetail:
    """Scan entries for session-related artifacts."""
    cookie_name = _detect_session_cookie(entries)
    headers = _detect_session_headers(entries)
    token_prefix = _detect_token_prefix(entries)

    return SessionDetail(
        cookie_name=cookie_name,
        headers=headers,
        token_prefix=token_prefix,
    )


def _detect_session_cookie(entries: list[dict[str, Any]]) -> str:
    """Find the session cookie name from Set-Cookie headers.

    Looks for cookies set after the first entry (post-login) that match
    known session cookie name patterns.
    """
    for entry in entries:
        resp = entry["response"]

        # Check structured cookies array
        for cookie in resp.get("cookies", []):
            cookie_name: str = cookie.get("name", "")
            if _is_session_cookie(cookie_name):
                return cookie_name

        # Check Set-Cookie headers
        for header in resp.get("headers", []):
            if header["name"].lower() == "set-cookie":
                name = _cookie_name_from_set_cookie(header["value"])
                if name and _is_session_cookie(name):
                    return name

    return ""


def _detect_session_headers(entries: list[dict[str, Any]]) -> dict[str, str]:
    """Detect session-wide headers from data page requests.

    Looks for headers like ``X-Requested-With: XMLHttpRequest`` that
    appear consistently on data page requests (non-static, non-login).
    """
    headers: dict[str, str] = {}

    # Scan non-static GET requests for common session headers
    data_requests = [
        entry
        for entry in entries
        if entry["request"].get("method") == "GET"
        and not is_static_resource(entry["request"].get("url", ""))
        and entry["response"].get("status") == 200
    ]

    if not data_requests:
        return headers

    # Check for X-Requested-With on data requests
    xhr_count = 0
    for entry in data_requests:
        req_hdrs = lower_headers(entry["request"])
        if "x-requested-with" in req_hdrs:
            xhr_count += 1

    # If most data requests have X-Requested-With, it's a session header
    if xhr_count > 0 and xhr_count >= len(data_requests) // 2:
        # Get the actual value from the first match
        for entry in data_requests:
            for h in entry["request"].get("headers", []):
                if h["name"].lower() == "x-requested-with":
                    headers[h["name"]] = h["value"]
                    break
            if headers:
                break

    return headers


def _detect_token_prefix(entries: list[dict[str, Any]]) -> str:
    """Detect URL token prefix on data page requests.

    For url_token auth, subsequent requests include a server-issued
    token in the query string with a consistent prefix (e.g., ``ct_``).
    """
    for entry in entries:
        req = entry["request"]
        url = req.get("url", "")
        if "?" not in url:
            continue
        query = url.split("?", 1)[1]
        # Look for short prefix followed by token-like value
        # Common patterns: ct_<timestamp>, token_<hash>
        for param in query.split("&"):
            if "=" in param:
                parts = param.split("=", 1)
                key_str: str = parts[0]
                val_str: str = parts[1]
                # Token prefixes are short identifiers
                if 2 <= len(key_str) <= 10 and len(val_str) >= 8:
                    # Check if this prefix appears on multiple data requests
                    count = _count_prefix_occurrences(entries, key_str)
                    if count >= 2:
                        return key_str + "_" if not key_str.endswith("_") else key_str

    return ""


def _count_prefix_occurrences(entries: list[dict[str, Any]], prefix: str) -> int:
    """Count how many data request URLs contain the given query parameter."""
    count = 0
    for entry in entries:
        url = entry["request"].get("url", "")
        if f"?{prefix}=" in url or f"&{prefix}=" in url:
            count += 1
    return count


def _is_session_cookie(name: str) -> bool:
    """Check if a cookie name matches known session cookie patterns."""
    lower = name.lower()
    return any(ind in lower for ind in _SESSION_COOKIE_INDICATORS)


def _cookie_name_from_set_cookie(header_value: str) -> str:
    """Extract cookie name from a Set-Cookie header value."""
    # Set-Cookie: name=value; path=/; ...
    if "=" in header_value:
        return header_value.split("=", 1)[0].strip()
    return ""


# Strategies that use credentials and could exhaust session slots.
_AUTHENTICATED_STRATEGIES: frozenset[str] = frozenset(
    {"form", "form_nonce", "form_pbkdf2", "form_sjcl", "url_token"},
)


def _infer_max_concurrent(
    session: SessionDetail,
    auth_strategy: str,
    warnings: list[str],
) -> None:
    """Infer max_concurrent from session evidence.

    IP-based sessions (form auth without cookies) typically allow only
    one concurrent session. Cookie-based sessions cannot be determined
    from HAR alone.
    """
    if auth_strategy not in _AUTHENTICATED_STRATEGIES:
        return

    if not session.cookie_name:
        # No session cookie + authenticated strategy = IP-based tracking.
        # These modems typically enforce a single-session limit.
        session.max_concurrent = 1
        session.max_concurrent_confidence = "medium"
        warnings.append(
            "No session cookie detected with authenticated strategy — "
            "likely IP-based session tracking with max_concurrent=1. "
            "Verify with contributor."
        )
    else:
        warnings.append(
            "max_concurrent cannot be determined from HAR for " "cookie-based sessions — verify with contributor."
        )
