"""Load auth detection patterns from JSON.

Single source of truth for login URL patterns, nonce prefixes,
PBKDF2 triggers, and SJCL indicators. Shared by
``mcp.analysis.auth.http`` (Phase 2) and
``mcp.validation.auth_flow`` (HAR validation gate).

Follows the same data-driven pattern as ``mapping.registry_loader``
for field definitions.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

_PATTERNS_PATH = Path(__file__).parent / "auth_patterns.json"


@functools.lru_cache(maxsize=1)
def _load_patterns() -> dict[str, Any]:
    """Load and cache the auth patterns JSON."""
    data: dict[str, Any] = json.loads(_PATTERNS_PATH.read_text(encoding="utf-8"))
    return data


def get_login_url_patterns() -> tuple[str, ...]:
    """Return login URL substring patterns (all lowercase)."""
    data = _load_patterns()
    return tuple(data["login_url_patterns"])


def get_nonce_success_prefix() -> str:
    """Return the success prefix for form_nonce response detection."""
    data = _load_patterns()
    return str(data["nonce_prefixes"]["success"])


def get_nonce_error_prefix() -> str:
    """Return the error prefix for form_nonce response detection."""
    data = _load_patterns()
    return str(data["nonce_prefixes"]["error"])


def get_pbkdf2_salt_triggers() -> tuple[str, ...]:
    """Return PBKDF2 salt trigger patterns for POST body detection."""
    data = _load_patterns()
    return tuple(data["pbkdf2_salt_triggers"])


def get_sjcl_page_variables() -> tuple[str, ...]:
    """Return JS variable names that indicate SJCL AES-CCM auth.

    These appear in the login page HTML as ``var myIv = '...'`` etc.
    """
    data = _load_patterns()
    return tuple(data["sjcl_page_variables"])


def get_sjcl_post_fields() -> tuple[str, ...]:
    """Return POST body field names that indicate SJCL encrypted payload."""
    data = _load_patterns()
    return tuple(data["sjcl_post_fields"])


def get_session_cookie_indicators() -> frozenset[str]:
    """Return session cookie name indicators (case-insensitive substrings).

    Cookie names containing any of these substrings suggest an active
    session. Used by Phase 2 (auth flow validation) and Phase 3
    (session detection).
    """
    data = _load_patterns()
    return frozenset(data["session_cookie_indicators"])
