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
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

import yaml

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


def get_password_field_indicators() -> tuple[str, ...]:
    """Return password field-name indicators (case-insensitive substrings)."""
    data = _load_patterns()
    return tuple(data["password_field_indicators"])


# The fleet an analysis runs with, when it was scanned: the intake score
# excludes the modem under test, so its own password_field teaches nothing.
_SCOPED_PASSWORD_NAMES: ContextVar[frozenset[str] | None] = ContextVar("scoped_password_names", default=None)


@contextmanager
def fleet_password_names(names: frozenset[str] | None) -> Iterator[None]:
    """Use a scanned fleet's password_field names in place of the whole catalog's."""
    token = _SCOPED_PASSWORD_NAMES.set(names)
    try:
        yield
    finally:
        _SCOPED_PASSWORD_NAMES.reset(token)


def collect_password_field_names(catalog_root: Path, exclude: Path | None = None) -> frozenset[str]:
    """Collect declared password_field names from committed modem*.yaml configs outside ``exclude``."""
    names: set[str] = set()
    for modem_yaml_path in sorted(catalog_root.rglob("modem*.yaml")):
        if exclude is not None and modem_yaml_path.is_relative_to(exclude):
            continue
        try:
            config: Any = yaml.safe_load(modem_yaml_path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError):
            continue
        if not isinstance(config, dict):
            continue
        auth = config.get("auth", {})
        if not isinstance(auth, dict):
            continue
        declared = auth.get("password_field")
        fields = declared if isinstance(declared, list) else [declared]
        names.update(f.lower() for f in fields if isinstance(f, str) and f)
    return frozenset(names)


@functools.lru_cache(maxsize=1)
def _fleet_password_field_names(catalog_root: Path) -> frozenset[str]:
    """The whole catalog's password_field names, read once."""
    return collect_password_field_names(catalog_root)


def get_fleet_password_field_names() -> frozenset[str]:
    """Return exact password field names declared by committed catalog modems."""
    # Attribute read at call time so tests can monkeypatch CATALOG_PATH.
    from solentlabs import cable_modem_monitor_catalog as catalog_pkg

    return _fleet_password_field_names(catalog_pkg.CATALOG_PATH)


def _active_password_names() -> frozenset[str]:
    """The scoped fleet's names inside ``fleet_password_names``, else the whole catalog's."""
    scoped = _SCOPED_PASSWORD_NAMES.get()
    return scoped if scoped is not None else get_fleet_password_field_names()


def is_password_field_name(name: str) -> bool:
    """Check if a form field name reads as a password field."""
    # Substrings generalize to unseen firmware; catalog names match exactly,
    # so committing a modem extends detection without a pattern edit.
    lower = name.lower()
    if any(ind in lower for ind in get_password_field_indicators()):
        return True
    return lower in _active_password_names()


# Checked after is_password_field_name: "loginPassword" matches both.
_USERNAME_FIELD_INDICATORS = ("username", "user", "login")


def is_username_field_name(name: str) -> bool:
    """Check if a field name reads as a username field."""
    lower = name.lower()
    return any(ind in lower for ind in _USERNAME_FIELD_INDICATORS)


def has_credential_fields(post_data: dict[str, Any]) -> bool:
    """Check if form POST data carries a password-shaped field name."""
    # Names, not values; HAR sanitizers redact values.
    params = post_data.get("params", [])
    if params:
        return any(is_password_field_name(p.get("name", "")) for p in params)
    text = post_data.get("text", "").lower()
    if not text:
        return False
    if any(ind in text for ind in get_password_field_indicators()):
        return True
    # "name=" keeps exact names from matching as substrings of other tokens.
    return any(f"{name}=" in text for name in _active_password_names())


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


def get_hnap_hmac_scripts() -> dict[str, str]:
    """Return HNAP hmac script file names mapped to the algorithm each one implements."""
    data = _load_patterns()
    return dict(data["hnap_hmac_scripts"])


def get_json_sjcl_script_constants() -> dict[str, str]:
    """Return json_sjcl config fields mapped to the JS constant that declares each."""
    data = _load_patterns()
    return dict(data["json_sjcl_script_constants"])


def get_json_sjcl_encrypt_calls() -> tuple[str, ...]:
    """Return the JS functions whose fourth argument is the json_sjcl aad."""
    data = _load_patterns()
    return tuple(data["json_sjcl_encrypt_calls"])


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
