"""Phase 2 - HTTP auth strategy detection.

Implements the HTTP branch of the ONBOARDING_SPEC Phase 2 decision tree.
Walks: none -> basic -> url_token -> form_pbkdf2 -> form_nonce -> form ->
hard stop.

Per docs/ONBOARDING_SPEC.md Phase 2 (HTTP transport).
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from typing import Any

from ...validation.har_utils import (
    HARD_STOP_PREFIX,
    has_content,
    has_set_cookie,
    lower_headers,
    parse_form_params,
    path_from_url,
)
from ..types import AuthDetail
from .patterns import (
    get_login_url_patterns,
    get_nonce_error_prefix,
    get_nonce_success_prefix,
    get_pbkdf2_salt_triggers,
)

# ---------------------------------------------------------------------------
# Auth patterns (loaded from auth_patterns.json)
# ---------------------------------------------------------------------------

_LOGIN_URL_PATTERNS: tuple[str, ...] = get_login_url_patterns()
_NONCE_SUCCESS_PREFIX: str = get_nonce_success_prefix()
_NONCE_ERROR_PREFIX: str = get_nonce_error_prefix()
_PBKDF2_SALT_TRIGGERS: tuple[str, ...] = get_pbkdf2_salt_triggers()

# Base64 pattern: login_<base64> or login%5f<base64> in URL
_URL_TOKEN_PATTERN = re.compile(r"login[_\-%]", re.IGNORECASE)
_BASE64_CHARS = re.compile(r"^[A-Za-z0-9+/=]{4,}$")


# ---------------------------------------------------------------------------
# HTTP auth decision tree
# ---------------------------------------------------------------------------


def detect_http_auth(
    entries: list[dict[str, Any]],
    warnings: list[str],
    hard_stops: list[str],
) -> AuthDetail:
    """Walk the HTTP auth decision tree.

    Order: none -> basic -> url_token -> form_pbkdf2 -> form_nonce ->
    form -> hard stop.

    Args:
        entries: HAR ``log.entries`` list.
        warnings: Mutable list to append warnings to.
        hard_stops: Mutable list to append hard stops to.

    Returns:
        AuthDetail with strategy, extracted fields, and confidence.
    """
    signals = _collect_http_signals(entries)

    # No auth signals at all -> none
    if not signals.has_any_auth_signal:
        return AuthDetail(strategy="none", confidence="high")

    # 401 + WWW-Authenticate: Digest -> HARD STOP (unsupported)
    if signals.digest_challenge:
        hard_stops.append(
            f"{HARD_STOP_PREFIX} WWW-Authenticate: Digest detected. "
            "Digest auth is not yet supported. "
            "See ONBOARDING_SPEC Phase 2 for supported auth strategies."
        )
        return AuthDetail(strategy="digest", confidence="high")

    # 401 + WWW-Authenticate: Basic -> basic
    if signals.basic_challenge:
        return _extract_basic(entries, signals)

    # URL token pattern -> url_token
    if signals.url_token_entry is not None:
        return _extract_url_token(entries, signals)

    # JSON POST with PBKDF2 salt flow -> form_pbkdf2
    if signals.pbkdf2_entries:
        return _extract_form_pbkdf2(signals)

    # Form POST to login endpoint
    if signals.form_post_entry is not None:
        # Check for nonce-style response
        if signals.form_nonce_entry is not None:
            return _extract_form_nonce(signals)
        # Standard form auth
        return _extract_form(entries, signals)

    # Auth signals detected but no strategy matched -> HARD STOP
    hard_stops.append(
        f"{HARD_STOP_PREFIX} Cannot determine auth mechanism. "
        f"Observed signals: {signals.describe()}. "
        "Manual review required - check HAR for login flow details."
    )
    return AuthDetail(strategy="unknown", confidence="low")


# ---------------------------------------------------------------------------
# HTTP signal collection
# ---------------------------------------------------------------------------


@dataclass
class _HttpAuthSignals:
    """Collected auth signals from HTTP HAR entries."""

    has_any_auth_signal: bool = False
    digest_challenge: bool = False
    basic_challenge: bool = False
    basic_challenge_cookie: bool = False
    url_token_entry: dict[str, Any] | None = None
    url_token_login_prefix: str = ""
    url_token_login_page: str = ""
    form_post_entry: dict[str, Any] | None = None
    form_nonce_entry: dict[str, Any] | None = None
    pbkdf2_entries: list[dict[str, Any]] = field(default_factory=list)
    has_401: bool = False
    has_302_after_post: bool = False
    has_authorization_header: bool = False
    has_set_cookie_after_login: bool = False

    def describe(self) -> str:
        """Describe what signals were found, for hard stop messages."""
        parts: list[str] = []
        if self.digest_challenge:
            parts.append("WWW-Authenticate: Digest")
        if self.has_401:
            parts.append("401 response")
        if self.has_authorization_header:
            parts.append("Authorization header")
        if self.form_post_entry is not None:
            url = self.form_post_entry["request"].get("url", "")
            parts.append(f"POST to {path_from_url(url)}")
        if self.has_set_cookie_after_login:
            parts.append("Set-Cookie after login")
        return ", ".join(parts) if parts else "ambiguous auth artifacts"


def _collect_http_signals(entries: list[dict[str, Any]]) -> _HttpAuthSignals:
    """Scan all entries and collect auth-related signals."""
    signals = _HttpAuthSignals()

    for entry in entries:
        _check_entry_auth_signals(entry, entries, signals)

    return signals


def _check_entry_auth_signals(
    entry: dict[str, Any],
    all_entries: list[dict[str, Any]],
    signals: _HttpAuthSignals,
) -> None:
    """Check a single HAR entry for auth-related signals."""
    req = entry["request"]
    resp = entry["response"]
    url = req.get("url", "")
    method = req.get("method", "")
    status = resp.get("status", 0)
    req_hdrs = lower_headers(req)
    resp_hdrs = lower_headers(resp)

    # Authorization header on any request
    if "authorization" in req_hdrs:
        signals.has_authorization_header = True
        signals.has_any_auth_signal = True

    # 401 + WWW-Authenticate
    if status == 401:
        signals.has_401 = True
        signals.has_any_auth_signal = True
        www_auth = resp_hdrs.get("www-authenticate", "")
        scheme = _parse_auth_scheme(www_auth)
        if scheme == "digest":
            signals.digest_challenge = True
        elif scheme == "basic":
            signals.basic_challenge = True
            signals.basic_challenge_cookie = _has_challenge_cookie_retry(all_entries, entry)

    # URL token pattern: login_<base64> in URL
    if _URL_TOKEN_PATTERN.search(url):
        token_match = _extract_url_token_parts(url)
        if token_match is not None:
            signals.url_token_entry = entry
            signals.url_token_login_prefix = token_match[0]
            signals.url_token_login_page = token_match[1]
            signals.has_any_auth_signal = True

    # POST requests
    if method == "POST":
        _check_post_signals(entry, req, resp, url, status, signals)

    # Set-Cookie on non-first entry after a login-like POST
    if has_set_cookie(resp) and signals.form_post_entry is not None:
        signals.has_set_cookie_after_login = True
        signals.has_any_auth_signal = True


def _check_post_signals(
    entry: dict[str, Any],
    req: dict[str, Any],
    resp: dict[str, Any],
    url: str,
    status: int,
    signals: _HttpAuthSignals,
) -> None:
    """Check POST request for auth signals (JSON/form)."""
    post_data = req.get("postData", {})
    mime = post_data.get("mimeType", "").lower()

    # JSON POST - check for PBKDF2 salt trigger
    if "json" in mime:
        text = post_data.get("text", "")
        is_salt = any(trigger in text.lower() for trigger in _PBKDF2_SALT_TRIGGERS)
        if is_salt or _is_login_url(url):
            signals.pbkdf2_entries.append(entry)
            signals.has_any_auth_signal = True

    # Form POST to login-like endpoint
    if ("form" in mime or "x-www-form-urlencoded" in mime) and _is_login_url(url):
        signals.form_post_entry = entry
        signals.has_any_auth_signal = True

        # Check response for nonce-style text prefixes
        resp_text = resp.get("content", {}).get("text", "")
        if resp_text and (
            resp_text.strip().startswith(_NONCE_SUCCESS_PREFIX) or resp_text.strip().startswith(_NONCE_ERROR_PREFIX)
        ):
            signals.form_nonce_entry = entry

        # 302 redirect after POST
        if status in (301, 302):
            signals.has_302_after_post = True


# ---------------------------------------------------------------------------
# Strategy extraction helpers
# ---------------------------------------------------------------------------


def _extract_basic(entries: list[dict[str, Any]], signals: _HttpAuthSignals) -> AuthDetail:
    """Extract basic auth fields."""
    return AuthDetail(
        strategy="basic",
        fields={"challenge_cookie": signals.basic_challenge_cookie},
        confidence="high",
    )


def _extract_url_token(entries: list[dict[str, Any]], signals: _HttpAuthSignals) -> AuthDetail:
    """Extract url_token auth fields."""
    entry = signals.url_token_entry
    assert entry is not None  # guaranteed by caller
    req = entry["request"]
    req_hdrs = lower_headers(req)
    resp = entry["response"]

    # Detect ajax_login from X-Requested-With header
    ajax_login = "x-requested-with" in req_hdrs

    # Detect success_indicator from response body
    success_indicator = ""
    resp_text = resp.get("content", {}).get("text", "")
    if resp_text and resp.get("status") == 200 and has_content(resp):
        # Success indicator is present if the response has data content
        # The LLM picks the actual indicator value during config generation
        pass

    return AuthDetail(
        strategy="url_token",
        fields={
            "login_page": signals.url_token_login_page,
            "login_prefix": signals.url_token_login_prefix,
            "ajax_login": ajax_login,
            "success_indicator": success_indicator,
        },
        confidence="high",
    )


def _extract_form_pbkdf2(signals: _HttpAuthSignals) -> AuthDetail:
    """Extract form_pbkdf2 auth fields from salt/challenge flow."""
    if not signals.pbkdf2_entries:
        return AuthDetail(strategy="form_pbkdf2", confidence="medium")

    # The first PBKDF2 entry is typically the salt request
    first_entry = signals.pbkdf2_entries[0]
    req = first_entry["request"]
    url = req.get("url", "")

    # Extract CSRF header if present
    csrf_header = ""
    req_hdrs_lower = lower_headers(req)
    for header_name in ("x-csrf-token", "csrf-token", "x-xsrf-token"):
        if header_name in req_hdrs_lower:
            csrf_header = header_name.upper().replace("-", "_")
            # Preserve original casing - check raw headers
            for h in req.get("headers", []):
                if h["name"].lower() == header_name:
                    csrf_header = h["name"]
                    break
            break

    # Detect CSRF init endpoint (request before the login POST)
    csrf_init_endpoint = ""

    fields: dict[str, Any] = {
        "login_endpoint": path_from_url(url),
        "csrf_header": csrf_header,
        "csrf_init_endpoint": csrf_init_endpoint,
    }

    # Try to extract PBKDF2 params from response JSON
    resp = first_entry["response"]
    resp_text = resp.get("content", {}).get("text", "")
    if resp_text:
        pbkdf2_params = _extract_pbkdf2_params_from_response(resp_text)
        fields.update(pbkdf2_params)

    return AuthDetail(
        strategy="form_pbkdf2",
        fields=fields,
        confidence="medium",
    )


def _extract_form_nonce(signals: _HttpAuthSignals) -> AuthDetail:
    """Extract form_nonce auth fields."""
    entry = signals.form_nonce_entry
    assert entry is not None  # guaranteed by caller
    req = entry["request"]
    url = req.get("url", "")
    post_data = req.get("postData", {})

    # Extract form params
    params = parse_form_params(post_data)

    # Identify nonce field (non-credential field in the POST)
    nonce_field = ""
    credential_format = ""
    for name in params:
        if name.lower() not in ("username", "password", "user", "pass"):
            nonce_field = name
            break

    # Detect success/error prefixes from response
    success_prefix = _NONCE_SUCCESS_PREFIX
    error_prefix = _NONCE_ERROR_PREFIX

    return AuthDetail(
        strategy="form_nonce",
        fields={
            "action": path_from_url(url),
            "nonce_field": nonce_field,
            "credential_format": credential_format,
            "success_prefix": success_prefix,
            "error_prefix": error_prefix,
        },
        confidence="high",
    )


def _extract_form(entries: list[dict[str, Any]], signals: _HttpAuthSignals) -> AuthDetail:
    """Extract standard form auth fields."""
    entry = signals.form_post_entry
    assert entry is not None  # guaranteed by caller
    req = entry["request"]
    resp = entry["response"]
    url = req.get("url", "")
    status = resp.get("status", 0)
    post_data = req.get("postData", {})

    # Parse form fields
    params = parse_form_params(post_data)
    username_field, password_field, hidden_fields = classify_form_fields(params)

    # Detect encoding: check if password value looks like base64
    encoding = detect_encoding(params, password_field)

    # Detect success indicator
    success: dict[str, str] = {}
    if status in (301, 302):
        # Redirect on success
        location = ""
        for h in resp.get("headers", []):
            if h["name"].lower() == "location":
                location = h["value"]
                break
        if location:
            success["redirect"] = path_from_url(location)

    return AuthDetail(
        strategy="form",
        fields={
            "action": path_from_url(url),
            "method": "POST",
            "username_field": username_field,
            "password_field": password_field,
            "encoding": encoding,
            "hidden_fields": hidden_fields,
            "success": success,
        },
        confidence="high",
    )


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _parse_auth_scheme(www_authenticate: str) -> str:
    """Extract the auth scheme token from a WWW-Authenticate header.

    Per RFC 7235, the scheme is the first whitespace-delimited token.
    Returns the lowercase scheme string, or empty string if absent.
    """
    token = www_authenticate.strip().split(None, 1)[0] if www_authenticate.strip() else ""
    return token.lower()


def _is_login_url(url: str) -> bool:
    """Check if a URL matches known login endpoint patterns."""
    lower = url.lower()
    return any(p in lower for p in _LOGIN_URL_PATTERNS)


def classify_form_fields(
    params: dict[str, str],
) -> tuple[str, str, dict[str, str]]:
    """Classify form fields into username, password, and hidden fields.

    Returns:
        Tuple of (username_field, password_field, hidden_fields).
    """
    username_field = ""
    password_field = ""
    hidden_fields: dict[str, str] = {}

    password_indicators = ("password", "pass", "pwd", "loginpassword")
    username_indicators = ("username", "user", "login", "loginusername")

    for name, value in params.items():
        lower_name = name.lower()
        # Check password first - "loginPassword" contains both "login"
        # (username indicator) and "password" (password indicator).
        # Password is more specific and should take priority.
        if any(ind in lower_name for ind in password_indicators):
            password_field = name
        elif any(ind in lower_name for ind in username_indicators):
            username_field = name
        else:
            hidden_fields[name] = value

    # Default field names if not identified
    if not username_field:
        username_field = "username"
    if not password_field:
        password_field = "password"

    return username_field, password_field, hidden_fields


def detect_encoding(params: dict[str, str], password_field: str) -> str:
    """Detect password encoding from form parameter values.

    If the password value looks like valid base64, returns ``base64``.
    Otherwise returns ``plain``.
    """
    pwd_value = params.get(password_field, "")
    if not pwd_value:
        return "plain"

    # Check if value looks like base64 (common in modem form auth)
    if _BASE64_CHARS.match(pwd_value) and len(pwd_value) >= 4:
        try:
            decoded = base64.b64decode(pwd_value, validate=True)
            # If it decodes to valid UTF-8 text, likely base64-encoded
            decoded.decode("utf-8")
            return "base64"
        except Exception:
            pass

    return "plain"


def _has_challenge_cookie_retry(entries: list[dict[str, Any]], challenge_entry: dict[str, Any]) -> bool:
    """Check if a 401 challenge is followed by a retry with Set-Cookie.

    Some modems (e.g., CM1200 HTTPS) return a challenge cookie on the
    initial 401 that must be included in the retry.
    """
    found_challenge = False
    for entry in entries:
        if entry is challenge_entry:
            found_challenge = True
            # Check if the 401 response sets a cookie
            if has_set_cookie(entry["response"]):
                continue
            return False
        if found_challenge:
            # Next request after challenge - check if it retries same URL
            challenge_url = challenge_entry["request"].get("url", "")
            retry_url = entry["request"].get("url", "")
            if path_from_url(challenge_url) == path_from_url(retry_url):
                return True
            break
    return False


def _extract_url_token_parts(url: str) -> tuple[str, str] | None:
    """Extract login prefix and page path from a URL token login URL.

    Returns:
        Tuple of (login_prefix, login_page) or None if not a token URL.
    """
    path = path_from_url(url)

    # Look for login_<token> pattern in query string
    full_lower = url.lower()
    for marker in ("login_", "login%5f"):
        idx = full_lower.find(marker)
        if idx < 0:
            continue
        # The prefix is everything up to and including the marker
        prefix = url[idx : idx + len(marker)]
        # Normalize: login%5f -> login_
        prefix = prefix.replace("%5f", "_").replace("%5F", "_")
        # The login page is the path without query string
        return prefix, path

    return None


def _extract_pbkdf2_params_from_response(resp_text: str) -> dict[str, Any]:
    """Try to extract PBKDF2 parameters from a JSON response body.

    Looks for salt, iterations, and key length fields in the response.
    Returns extracted params as a dict (may be partial or empty).
    """
    import json

    params: dict[str, Any] = {}
    try:
        data = json.loads(resp_text)
    except (json.JSONDecodeError, TypeError):
        return params

    if not isinstance(data, dict):
        return params

    # Common field names for PBKDF2 params
    for key, config_key in [
        ("iterations", "pbkdf2_iterations"),
        ("iter", "pbkdf2_iterations"),
        ("keyLength", "pbkdf2_key_length"),
        ("key_length", "pbkdf2_key_length"),
        ("salt", "salt_value"),
    ]:
        if key in data:
            params[config_key] = data[key]

    return params
