"""Shared utilities for HAR entry inspection.

Generic HAR reading utilities — no domain-specific knowledge about
modem auth patterns or login endpoints. Domain-specific constants
live in the modules that use them (auth_flow.py, protocol_signals.py).
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Issue prefixes — structured markers for validation results
# ---------------------------------------------------------------------------

HARD_STOP_PREFIX = "HARD STOP:"
WARNING_PREFIX = "WARNING:"

# ---------------------------------------------------------------------------
# Static resource extensions — excluded from data page detection
# ---------------------------------------------------------------------------

STATIC_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".css",
        ".js",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".svg",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
    }
)


# ---------------------------------------------------------------------------
# HAR entry inspection functions
# ---------------------------------------------------------------------------


def lower_headers(req_or_resp: dict[str, Any]) -> dict[str, str]:
    """Build lowercase header name -> value dict from a request or response."""
    return {h["name"].lower(): h["value"] for h in req_or_resp.get("headers", [])}


def is_hnap_request(url: str, req_headers: dict[str, str]) -> bool:
    """Check if a request has HNAP protocol markers."""
    return "/HNAP1/" in url or "hnap_auth" in req_headers or "soapaction" in req_headers


def has_set_cookie(resp: dict[str, Any]) -> bool:
    """Check if a response sets a cookie (via cookies array or Set-Cookie header)."""
    if resp.get("cookies"):
        return True
    return any(h["name"].lower() == "set-cookie" for h in resp.get("headers", []))


def has_content(response: dict[str, Any]) -> bool:
    """Check if a response has non-trivial content."""
    content = response.get("content", {})
    size = content.get("size", 0)
    text = content.get("text", "")
    return size > 0 or bool(text)


def is_static_resource(url: str) -> bool:
    """Check if a URL is a static resource (CSS, JS, image, font)."""
    path = url.split("?", maxsplit=1)[0].split("#", maxsplit=1)[0]
    return any(path.lower().endswith(ext) for ext in STATIC_EXTENSIONS)
