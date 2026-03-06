#!/usr/bin/env python3
"""Extract authentication patterns from HAR files.

Analyzes HTTP Archive (HAR) files to identify:
- Protocol (http/https) and interface type (hnap/rest/html)
- Login form pages and field names
- Authentication POST requests
- Cookie/session management (server-set, ghost/JS-set, headers)
- CSRF token patterns

Output is JSON only (via ``dataclasses.asdict``).  For human-readable text or
YAML rendering, pipe into ``har_auth_format.py``.

Usage:
    python scripts/har/har_auth_extractor.py path/to/file.har
    python scripts/har/har_auth_extractor.py path/to/file.har --modem-yaml path/to/modem.yaml
    python scripts/har/har_auth_extractor.py path/to/file.har | python scripts/har/har_auth_format.py
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass
class FormField:
    """Discovered form field."""

    name: str
    field_type: str  # text, password, hidden, submit
    value: str | None = None


@dataclass
class ProbeReport:
    """Parsed _probes from har-capture v0.4.1+."""

    auth_status_code: int | None = None
    www_authenticate: str | None = None
    auth_set_cookies: list[str] = field(default_factory=list)
    auth_error: str | None = None
    icmp_reachable: bool | None = None
    headers: dict[str, str] = field(default_factory=dict)
    body_preview: str = ""


@dataclass
class BrowserCookie:
    """Cookie from browser snapshot (har-capture v0.4.2+)."""

    name: str
    domain: str = ""
    path: str = "/"
    http_only: bool = False
    secure: bool = False
    same_site: str = ""


@dataclass
class GhostCookie:
    """Cookie in requests that was never Set-Cookie'd by server."""

    name: str
    first_seen_entry: int
    first_seen_url: str
    category: str  # "session", "csrf", "preference", "artifact"


@dataclass
class SessionSummary:
    """How the modem maintains authenticated sessions."""

    mechanism: str = "unknown"  # cookie, header, url_token, stateless, unknown
    cookies: list[str] = field(default_factory=list)  # Server-set session cookies
    js_cookies: list[str] = field(default_factory=list)  # Ghost cookies (JS-set)
    headers: list[str] = field(default_factory=list)  # Session headers (e.g. HNAP_AUTH)
    csrf: str | None = None  # CSRF field name if detected
    csrf_source: str | None = None  # cookie, hidden_field, header


@dataclass
class PageAuthSummary:
    """Per-URL auth evidence from browser entries."""

    path: str
    status_codes: list[int] = field(default_factory=list)
    has_401: bool = False
    www_authenticate: str | None = None
    request_cookies: list[str] = field(default_factory=list)
    response_set_cookies: list[str] = field(default_factory=list)
    has_login_form: bool = False
    has_auth_header: bool = False
    response_content_type: str | None = None


@dataclass
class AuthFlow:
    """Extracted authentication flow from HAR."""

    modem_name: str | None = None
    auth_pattern: str = "unknown"
    protocol: str = "http"  # http or https
    interface_type: str = "unknown"  # hnap, rest, html, unknown

    # Login page info
    login_url: str | None = None
    form_action: str | None = None
    form_method: str = "POST"
    form_fields: list[FormField] = field(default_factory=list)

    # Credential fields (detected or inferred)
    username_field: str | None = None
    password_field: str | None = None

    # CSRF handling
    csrf_field: str | None = None
    csrf_source: str | None = None  # cookie, hidden_field, header

    # Session management
    session_cookie: str | None = None
    session_header: str | None = None
    credential_cookie: str | None = None
    session: SessionSummary = field(default_factory=SessionSummary)

    # URL token (SB8200 pattern)
    url_token_prefix: str | None = None
    auth_header: str | None = None

    # Raw entries for debugging
    login_entry_index: int | None = None
    auth_entry_index: int | None = None

    # Issues found
    issues: list[str] = field(default_factory=list)

    # Enhanced analysis (v2)
    warnings: list[str] = field(default_factory=list)
    ghost_cookies: list[GhostCookie] = field(default_factory=list)
    browser_cookies: list[BrowserCookie] | None = None
    probe: ProbeReport | None = None
    is_post_auth: bool = False
    auth_confidence: str = "low"
    page_auth_map: dict[str, PageAuthSummary] = field(default_factory=dict)
    modem_yaml_auth: str | None = None
    cross_validation_issues: list[str] = field(default_factory=list)


def load_har(path: Path) -> dict[str, Any]:
    """Load HAR file (supports .har and .har.gz)."""
    result: dict[str, Any]
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            result = json.load(f)
    else:
        with open(path, encoding="utf-8") as f:
            result = json.load(f)
    return result


def extract_forms_from_html(html: str) -> list[dict[str, Any]]:
    """Extract form information from HTML content."""
    forms = []

    # Simple regex-based form extraction (avoids BeautifulSoup dependency)
    form_pattern = re.compile(r"<form[^>]*>(.*?)</form>", re.IGNORECASE | re.DOTALL)
    action_pattern = re.compile(r'action=["\']([^"\']*)["\']', re.IGNORECASE)
    method_pattern = re.compile(r'method=["\']([^"\']*)["\']', re.IGNORECASE)
    input_pattern = re.compile(r'<input[^>]*name=["\']([^"\']*)["\'][^>]*>', re.IGNORECASE)
    type_pattern = re.compile(r'type=["\']([^"\']*)["\']', re.IGNORECASE)
    value_pattern = re.compile(r'value=["\']([^"\']*)["\']', re.IGNORECASE)

    for form_match in form_pattern.finditer(html):
        form_html = form_match.group(0)
        form_content = form_match.group(1)

        form_info: dict[str, Any] = {
            "action": None,
            "method": "GET",
            "fields": [],
        }

        # Extract action
        action_match = action_pattern.search(form_html)
        if action_match:
            form_info["action"] = action_match.group(1)

        # Extract method
        method_match = method_pattern.search(form_html)
        if method_match:
            form_info["method"] = method_match.group(1).upper()

        # Extract input fields
        for input_match in input_pattern.finditer(form_content):
            input_html = input_match.group(0)
            field_name = input_match.group(1)

            field_type = "text"
            type_match = type_pattern.search(input_html)
            if type_match:
                field_type = type_match.group(1).lower()

            field_value = None
            value_match = value_pattern.search(input_html)
            if value_match:
                field_value = value_match.group(1)

            form_info["fields"].append(FormField(name=field_name, field_type=field_type, value=field_value))

        forms.append(form_info)

    return forms


def detect_login_page(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Check if entry is a login page."""
    response = entry.get("response", {})
    content = response.get("content", {})
    html = content.get("text", "")

    if not html:
        return None

    # Look for password field
    if 'type="password"' not in html.lower() and "type='password'" not in html.lower():
        return None

    forms = extract_forms_from_html(html)
    for form in forms:
        password_fields = [f for f in form["fields"] if f.field_type == "password"]
        if password_fields:
            return {
                "url": entry["request"]["url"],
                "form": form,
                "entry_index": None,  # Set by caller
            }

    return None


def detect_auth_post(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Check if entry is an authentication POST request."""
    request = entry.get("request", {})
    if request.get("method") != "POST":
        return None

    post_data = request.get("postData", {})
    text = post_data.get("text", "")
    params = post_data.get("params", [])

    # Check for credential-like parameters
    credential_hints = ["password", "pwd", "pass", "login", "user", "credential"]
    has_credentials = False

    for param in params:
        param_name = param.get("name", "").lower()
        if any(hint in param_name for hint in credential_hints):
            has_credentials = True
            break

    if not has_credentials and text:
        text_lower = text.lower()
        has_credentials = any(hint in text_lower for hint in credential_hints)

    if has_credentials:
        return {
            "url": request["url"],
            "method": "POST",
            "params": params,
            "text": text,
            "entry_index": None,
        }

    return None


def detect_url_token_auth(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Check for URL-based token authentication (SB8200 pattern)."""
    request = entry.get("request", {})
    url = request.get("url", "")

    # Look for patterns like ?login_<base64> or ?ct_<token>
    # Prefer login_ as it's the actual auth, ct_ is CSRF for subsequent requests
    patterns = [
        (r"\?login_([A-Za-z0-9+/=]+)", "login_"),  # Primary auth pattern
        (r"\?ct_([A-Za-z0-9+/=]+)", "ct_"),  # CSRF token pattern
    ]

    for pattern, prefix in patterns:
        match = re.search(pattern, url)
        if match:
            # Check for Authorization header
            auth_header = None
            for header in request.get("headers", []):
                if header["name"].lower() == "authorization":
                    auth_header = header["value"]
                    break

            return {
                "url": url,
                "prefix": prefix,
                "token": match.group(1),
                "auth_header": auth_header,
                "entry_index": None,
            }

    return None


def detect_basic_auth(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Check for HTTP Basic Authentication."""
    request = entry.get("request", {})
    response = entry.get("response", {})

    # Check for 401 response with WWW-Authenticate: Basic
    if response.get("status") == 401:
        for header in response.get("headers", []):
            if header["name"].lower() == "www-authenticate" and "basic" in header["value"].lower():
                return {
                    "url": request["url"],
                    "type": "basic",
                    "realm": header["value"],
                    "entry_index": None,
                }

    # Check for Authorization: Basic header
    for header in request.get("headers", []):
        if header["name"].lower() == "authorization" and header["value"].lower().startswith("basic "):
            return {
                "url": request["url"],
                "type": "basic",
                "header": header["value"],
                "entry_index": None,
            }

    return None


def detect_hnap_auth(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Check for HNAP/SOAP authentication."""
    request = entry.get("request", {})

    # Check for HNAP indicators
    url = request.get("url", "")
    if "/HNAP1" not in url:
        return None

    # Look for SOAP action header
    soap_action = None
    hnap_auth = None
    for header in request.get("headers", []):
        name_lower = header["name"].lower()
        if name_lower == "soapaction":
            soap_action = header["value"]
        elif name_lower == "hnap_auth":
            hnap_auth = header["value"]

    # Check for Login action
    if soap_action and ("Login" in soap_action or "GetMultipleHNAPs" in soap_action):
        return {
            "url": url,
            "type": "hnap",
            "soap_action": soap_action,
            "hnap_auth": hnap_auth,
            "entry_index": None,
        }

    return None


def _is_malformed_set_cookie(value: str) -> bool:
    """Filter 'Secure; HttpOnly' artifacts with no name=value pair.

    Some modems (S33 family) send ``Set-Cookie: Secure; HttpOnly`` on every
    response — a firmware bug.  A valid Set-Cookie must have ``name=value``
    before the first semicolon.
    """
    first_part = value.split(";", maxsplit=1)[0].strip()
    return "=" not in first_part


# Ghost cookie classification — names that indicate auth-critical cookies
SESSION_COOKIE_NAMES = {"uid", "PrivateKey", "SID", "credential", "sysauth", "sessionToken"}
CSRF_COOKIE_NAMES = {"XSRF_TOKEN", "csrfp_token", "x-csrf-token"}
ARTIFACT_NAMES = {"Secure"}

# Login-related URL path fragments (case-insensitive comparison)
_LOGIN_PATH_FRAGMENTS = {"login", "auth", "session", "signin", "credential"}


def track_cookies(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Track cookie flow across all entries."""
    cookie_timeline: list[dict[str, Any]] = []
    known_cookies: set[str] = set()

    for i, entry in enumerate(entries):
        # Check response Set-Cookie headers
        for header in entry.get("response", {}).get("headers", []):
            if header["name"].lower() == "set-cookie":
                cookie_str = header["value"]
                if _is_malformed_set_cookie(cookie_str):
                    continue
                cookie_name = cookie_str.split("=", maxsplit=1)[0].strip()
                if cookie_name not in known_cookies:
                    known_cookies.add(cookie_name)
                    cookie_timeline.append(
                        {
                            "index": i,
                            "cookie": cookie_name,
                            "action": "set",
                            "url": entry["request"]["url"],
                        }
                    )

        # Check request cookies
        for cookie in entry.get("request", {}).get("cookies", []):
            cookie_name = cookie.get("name", "")
            if cookie_name and cookie_name not in known_cookies:
                known_cookies.add(cookie_name)
                cookie_timeline.append(
                    {
                        "index": i,
                        "cookie": cookie_name,
                        "action": "appeared",  # Not set by server, maybe JS
                        "url": entry["request"]["url"],
                    }
                )

    return {
        "timeline": cookie_timeline,
        "all_cookies": list(known_cookies),
    }


def extract_probes(har: dict[str, Any]) -> ProbeReport | None:
    """Read ``har["log"]["_probes"]`` from har-capture v0.4.1+.

    Returns *None* when the section is absent (all pre-v0.4.0 captures).
    """
    probes = har.get("log", {}).get("_probes")
    if not probes:
        return None

    auth_probe = probes.get("auth_challenge", {})
    icmp_probe = probes.get("icmp", {})

    report = ProbeReport()
    if "status_code" in auth_probe:
        report.auth_status_code = auth_probe["status_code"]
    if "www_authenticate" in auth_probe:
        report.www_authenticate = auth_probe["www_authenticate"]
    if "set_cookie" in auth_probe:
        report.auth_set_cookies = auth_probe["set_cookie"]
    if "error" in auth_probe:
        report.auth_error = auth_probe["error"]
    if "headers" in auth_probe:
        report.headers = auth_probe["headers"]
    if "body_preview" in auth_probe:
        report.body_preview = auth_probe["body_preview"]
    if "reachable" in icmp_probe:
        report.icmp_reachable = icmp_probe["reachable"]

    return report


def extract_browser_cookies(har: dict[str, Any]) -> list[BrowserCookie] | None:
    """Read browser cookies from log._har_capture.browser_cookies.

    Returns None when the section is absent (pre-v0.4.2 captures).
    """
    har_capture = har.get("log", {}).get("_har_capture", {})
    raw = har_capture.get("browser_cookies")
    if raw is None:
        return None
    return [
        BrowserCookie(
            name=c.get("name", ""),
            domain=c.get("domain", ""),
            path=c.get("path", "/"),
            http_only=c.get("httpOnly", False),
            secure=c.get("secure", False),
            same_site=c.get("sameSite", ""),
        )
        for c in raw
        if c.get("name")
    ]


def _classify_cookie_name(name: str) -> str:
    """Classify a ghost cookie by name."""
    if name in ARTIFACT_NAMES:
        return "artifact"
    # CSRF is more specific than session — check first
    if name in CSRF_COOKIE_NAMES:
        return "csrf"
    if name in SESSION_COOKIE_NAMES:
        return "session"
    return "preference"


def detect_ghost_cookies(
    cookie_info: dict[str, Any],
    browser_cookies: list[BrowserCookie] | None = None,
) -> list[GhostCookie]:
    """Find cookies that appeared in requests but were never Set-Cookie'd.

    Filters ``track_cookies()`` output for ``action == "appeared"`` events,
    classifies each as session / csrf / preference / artifact.

    When *browser_cookies* is provided (har-capture v0.4.2+), cookies from the
    browser snapshot that are neither server-set nor already found in request
    traffic are added as additional ghosts with ``first_seen_entry=-1``.
    """
    server_set = {e["cookie"] for e in cookie_info["timeline"] if e["action"] == "set"}
    ghosts: list[GhostCookie] = []
    seen_names: set[str] = set()

    # Source 1: appeared in requests without Set-Cookie (existing logic)
    for event in cookie_info["timeline"]:
        if event["action"] != "appeared":
            continue
        name = event["cookie"]
        seen_names.add(name)
        ghosts.append(
            GhostCookie(
                name=name,
                first_seen_entry=event["index"],
                first_seen_url=event["url"],
                category=_classify_cookie_name(name),
            )
        )

    # Source 2: browser cookies not server-set and not already found
    if browser_cookies:
        for bc in browser_cookies:
            if bc.name not in server_set and bc.name not in seen_names:
                seen_names.add(bc.name)
                ghosts.append(
                    GhostCookie(
                        name=bc.name,
                        first_seen_entry=-1,
                        first_seen_url="",
                        category=_classify_cookie_name(bc.name),
                    )
                )

    return ghosts


def _update_page_summary_response(summary: PageAuthSummary, response: dict[str, Any]) -> None:
    """Update summary with response-side evidence."""
    status = response.get("status", 0)
    if status:
        summary.status_codes.append(status)
    if status == 401:
        summary.has_401 = True

    for header in response.get("headers", []):
        name_lower = header["name"].lower()
        if name_lower == "www-authenticate":
            summary.www_authenticate = header["value"]
            summary.has_401 = True
        if name_lower == "set-cookie" and not _is_malformed_set_cookie(header["value"]):
            cookie_name = header["value"].split("=", maxsplit=1)[0].strip()
            if cookie_name not in summary.response_set_cookies:
                summary.response_set_cookies.append(cookie_name)

    content = response.get("content", {})
    mime = content.get("mimeType", "")
    if mime:
        summary.response_content_type = mime.split(";")[0].strip()

    html = content.get("text", "")
    if html and ('type="password"' in html.lower() or "type='password'" in html.lower()):
        summary.has_login_form = True


def _update_page_summary(summary: PageAuthSummary, entry: dict[str, Any]) -> None:
    """Update a PageAuthSummary with evidence from a single HAR entry."""
    request = entry.get("request", {})
    _update_page_summary_response(summary, entry.get("response", {}))

    for cookie in request.get("cookies", []):
        cname = cookie.get("name", "")
        if cname and cname not in summary.request_cookies:
            summary.request_cookies.append(cname)

    for header in request.get("headers", []):
        if header["name"].lower() == "authorization":
            summary.has_auth_header = True


def build_page_auth_map(entries: list[dict[str, Any]]) -> dict[str, PageAuthSummary]:
    """Build per-path auth evidence from all entries."""
    page_map: dict[str, PageAuthSummary] = {}

    for entry in entries:
        url = entry.get("request", {}).get("url", "")
        path = urlparse(url).path or "/"

        if path not in page_map:
            page_map[path] = PageAuthSummary(path=path)
        _update_page_summary(page_map[path], entry)

    return page_map


def detect_post_auth_capture(
    entries: list[dict[str, Any]],
    ghosts: list[GhostCookie],
    page_map: dict[str, PageAuthSummary],
) -> tuple[bool, list[str]]:
    """Detect whether the HAR was captured after the browser was already logged in.

    Returns ``(is_post_auth, warnings)``.

    Signals (all must be true):
      1. Auth-related ghost cookies present (session or csrf category)
      2. No login form anywhere in HAR
      3. No login POST (POST to a login/auth/session URL)

    Definitive signal (any → post-auth even without 1-3):
      - Logout POST visible but no login POST
    """
    warnings: list[str] = []

    session_ghosts = [g for g in ghosts if g.category == "session"]
    has_login_form = any(s.has_login_form for s in page_map.values())

    # Find login and logout POSTs
    has_login_post = False
    has_logout_post = False
    for entry in entries:
        request = entry.get("request", {})
        if request.get("method") != "POST":
            continue
        url_path = urlparse(request.get("url", "")).path.lower()
        if any(frag in url_path for frag in _LOGIN_PATH_FRAGMENTS):
            has_login_post = True
        if "logout" in url_path:
            has_logout_post = True

    # Definitive: logout visible but no login
    if has_logout_post and not has_login_post and not has_login_form:
        warnings.append("Logout POST visible but no login flow — capture started " "with an authenticated session")
        return True, warnings

    # Primary signal combination
    if session_ghosts and not has_login_form and not has_login_post:
        ghost_names = ", ".join(g.name for g in session_ghosts)
        warnings.append(
            f"JS-set session cookie(s) ({ghost_names}) with no login flow "
            f"visible — auth mechanism unclear from this capture"
        )
        return True, warnings

    return False, warnings


def _is_clean_no_auth(flow: AuthFlow, entries: list[dict[str, Any]]) -> bool:
    """All 200s, no cookies, no forms, no auth headers, no ghosts."""
    has_any_cookies = any(entry.get("request", {}).get("cookies") for entry in entries)
    has_any_form = any(s.has_login_form for s in flow.page_auth_map.values())
    has_any_auth_header = any(s.has_auth_header for s in flow.page_auth_map.values())
    all_success = all(200 <= entry.get("response", {}).get("status", 0) < 400 for entry in entries)
    return (
        all_success
        and not has_any_cookies
        and not has_any_form
        and not has_any_auth_header
        and not any(g.category == "session" for g in flow.ghost_cookies)
    )


def _probe_confidence(probe: ProbeReport | None) -> str | None:
    """Return confidence from probe data, or None if inconclusive."""
    if not probe:
        return None
    if probe.www_authenticate:
        return "high"
    if probe.auth_status_code and probe.auth_status_code < 400:
        return "medium"
    return None


def assess_auth_confidence(
    flow: AuthFlow,
    entries: list[dict[str, Any]],
    probe: ProbeReport | None,
) -> str:
    """Categorical confidence based on evidence quality.

    Returns one of: "high", "medium", "low", "insufficient_evidence".
    """
    if flow.is_post_auth:
        return "insufficient_evidence"

    probe_result = _probe_confidence(probe)
    if probe_result:
        return probe_result

    # Known pattern with visible auth flow
    high_patterns = {
        "hnap_session": flow.auth_entry_index is not None,
        "form_plain": flow.login_url and flow.auth_entry_index is not None,
        "url_token_session": flow.url_token_prefix is not None,
    }
    if high_patterns.get(flow.auth_pattern, False):
        return "high"

    if _is_clean_no_auth(flow, entries):
        return "high"

    if flow.auth_pattern != "unknown":
        return "medium"

    return "low"


def cross_validate_modem_yaml(flow: AuthFlow, yaml_path: Path) -> tuple[str, list[str]]:
    """Compare HAR evidence against modem.yaml auth config.

    Returns ``(yaml_auth_type, issues)`` — the declared auth type and a list
    of inconsistency descriptions.  Caller assigns both to the flow.
    """
    import yaml  # conditional import

    issues: list[str] = []
    with open(yaml_path) as f:
        modem_cfg = yaml.safe_load(f)

    auth_cfg = modem_cfg.get("auth", {})
    auth_types = auth_cfg.get("types", {})

    yaml_auth: str = next(iter(auth_types), "none") if auth_types else "none"

    # modem.yaml says "none" but HAR has auth-related ghost cookies
    auth_ghosts = [g for g in flow.ghost_cookies if g.category in ("session", "csrf")]
    if yaml_auth == "none" and auth_ghosts:
        ghost_names = ", ".join(g.name for g in auth_ghosts)
        issues.append(f'modem.yaml declares auth "none" but HAR has JS-set session ' f"cookie(s): {ghost_names}")

    # modem.yaml says "basic" but HAR has no Authorization/WWW-Authenticate
    if yaml_auth == "basic":
        has_www_auth = any(s.www_authenticate for s in flow.page_auth_map.values())
        has_auth_hdr = any(s.has_auth_header for s in flow.page_auth_map.values())
        if not has_www_auth and not has_auth_hdr:
            issues.append(
                'modem.yaml declares "basic" auth but HAR has no ' "Authorization or WWW-Authenticate headers"
            )

    # Session config contradicts auth type
    session_cfg = auth_cfg.get("session", {})
    if yaml_auth == "basic" and session_cfg.get("cookies"):
        issues.append('modem.yaml declares "basic" auth but has session cookies — ' "HTTP Basic is stateless")

    if yaml_auth == "none" and session_cfg.get("cookies"):
        issues.append("modem.yaml declares no auth but has session cookie config — " "contradictory")

    return yaml_auth, issues


def flow_to_json(flow: AuthFlow) -> str:
    """Serialize AuthFlow to JSON via ``dataclasses.asdict``."""
    return json.dumps(asdict(flow), indent=2)


def detect_csrf(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Detect CSRF token patterns."""
    for i, entry in enumerate(entries):
        request = entry.get("request", {})
        post_data = request.get("postData", {})
        params = post_data.get("params", [])

        for param in params:
            param_name = param.get("name", "").lower()
            if "csrf" in param_name or "token" in param_name:
                return {
                    "field": param.get("name"),
                    "source": "form_field",
                    "entry_index": i,
                    "url": request["url"],
                }

        # Check headers
        for header in request.get("headers", []):
            header_name = header["name"].lower()
            if "csrf" in header_name or "x-token" in header_name:
                return {
                    "field": header["name"],
                    "source": "header",
                    "entry_index": i,
                    "url": request["url"],
                }

    return None


def infer_modem_name(entries: list[dict[str, Any]]) -> str | None:
    """Try to infer modem name from HAR content."""
    # Common patterns in page titles or content
    model_patterns = [
        r"(SB\d{4})",  # ARRIS SB series
        r"(S33)",  # ARRIS S33
        r"(MB\d{4})",  # Motorola MB series
        r"(CM\d{4})",  # Various CM series
        r"(C\d{4})",  # Netgear C series
        r"(TC\d{4})",  # Technicolor
        r"(G54)",  # ARRIS G54
        r"(XB\d)",  # Technicolor XB series
        r"(CGA\d+)",  # Technicolor CGA
        r"(SuperHub)",  # Virgin SuperHub
    ]

    for entry in entries:
        content = entry.get("response", {}).get("content", {})
        html = content.get("text", "")
        if not html:
            continue

        for pattern in model_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1).upper()

    return None


def classify_auth_pattern(flow: AuthFlow) -> str:
    """Classify the authentication pattern."""
    # URL token takes highest priority (specific pattern)
    if flow.url_token_prefix:
        return "url_token_session"
    # HNAP detected via SOAP actions
    if flow.session_header and "hnap" in flow.session_header.lower():
        return "hnap_session"
    # Credential + CSRF is a specific pattern
    if flow.csrf_field and flow.credential_cookie:
        return "credential_csrf"
    # Form auth with password field
    if flow.password_field:
        # Check for base64 encoding hints
        return "form_plain"  # May be form_base64, needs validation
    # Basic auth if we have session cookie but no form
    if flow.session_cookie and not flow.password_field and not flow.form_action:
        return "basic_http"

    return "unknown"


def _detect_interface_type(flow: AuthFlow) -> str:
    """Classify interface type from existing evidence on the flow.

    Priority: hnap > rest > html.  Uses content types already captured in
    ``page_auth_map`` and the auth pattern.
    """
    if flow.auth_pattern == "hnap_session" or flow.session_header == "HNAP_AUTH":
        return "hnap"

    # Count data-bearing content types across pages
    json_xml = 0
    html = 0
    for summary in flow.page_auth_map.values():
        ct = summary.response_content_type or ""
        if ct in ("application/json", "text/xml", "application/xml"):
            json_xml += 1
        elif ct == "text/html":
            html += 1

    if json_xml > html:
        return "rest"
    if html > 0:
        return "html"
    return "unknown"


def _build_session_summary(flow: AuthFlow) -> SessionSummary:
    """Consolidate scattered session fields into a structured summary."""
    cookies = [flow.session_cookie] if flow.session_cookie else []
    if flow.credential_cookie and flow.credential_cookie not in cookies:
        cookies.append(flow.credential_cookie)

    js_cookies = [g.name for g in flow.ghost_cookies if g.category in ("session", "csrf")]
    headers = [flow.session_header] if flow.session_header else []

    # Determine mechanism
    if flow.url_token_prefix:
        mechanism = "url_token"
    elif headers:
        mechanism = "header"
    elif cookies or js_cookies:
        mechanism = "cookie"
    elif not cookies and not js_cookies and not headers and flow.auth_pattern in ("unknown", "none"):
        # Clean no-auth or truly unknown
        mechanism = "stateless" if flow.auth_confidence == "high" else "unknown"
    else:
        mechanism = "unknown"

    return SessionSummary(
        mechanism=mechanism,
        cookies=cookies,
        js_cookies=js_cookies,
        headers=headers,
        csrf=flow.csrf_field,
        csrf_source=flow.csrf_source,
    )


def analyze_har(har: dict[str, Any]) -> AuthFlow:  # noqa: C901
    """Analyze HAR file and extract authentication flow."""
    flow = AuthFlow()
    entries = har.get("log", {}).get("entries", [])

    if not entries:
        flow.issues.append("No entries found in HAR")
        return flow

    # Protocol from first entry URL
    first_url = entries[0].get("request", {}).get("url", "")
    flow.protocol = urlparse(first_url).scheme or "http"

    # Try to identify modem
    flow.modem_name = infer_modem_name(entries)

    # Track cookies
    cookie_info = track_cookies(entries)

    # Look for session cookies
    session_cookie_hints = ["session", "credential", "sid", "uid", "auth"]
    for cookie in cookie_info["all_cookies"]:
        cookie_lower = cookie.lower()
        if any(hint in cookie_lower for hint in session_cookie_hints):
            if "credential" in cookie_lower:
                flow.credential_cookie = cookie
            else:
                flow.session_cookie = cookie

    # Detect CSRF
    csrf_info = detect_csrf(entries)
    if csrf_info:
        flow.csrf_field = csrf_info["field"]
        flow.csrf_source = csrf_info["source"]

    # Scan entries for auth patterns
    for i, entry in enumerate(entries):
        # Check for login page
        login_info = detect_login_page(entry)
        if login_info:
            flow.login_url = login_info["url"]
            flow.login_entry_index = i
            form = login_info["form"]
            flow.form_action = form["action"]
            flow.form_method = form["method"]
            flow.form_fields = form["fields"]

            # Find username/password fields
            for f in form["fields"]:
                if f.field_type == "password":
                    flow.password_field = f.name
                elif f.field_type in ("text", "email"):
                    name_lower = f.name.lower()
                    if any(h in name_lower for h in ["user", "login", "name", "email"]):
                        flow.username_field = f.name

        # Check for auth POST
        auth_post = detect_auth_post(entry)
        if auth_post:
            flow.auth_entry_index = i
            if not flow.form_action:
                flow.form_action = urlparse(auth_post["url"]).path

        # Check for URL token auth
        # Prefer login_ over ct_ (login_ is auth, ct_ is CSRF)
        url_token = detect_url_token_auth(entry)
        # Only overwrite if we don't have login_ already or this is login_
        if url_token and (not flow.url_token_prefix or url_token["prefix"] == "login_"):
            flow.url_token_prefix = url_token["prefix"]
            flow.auth_header = url_token["auth_header"]
            flow.auth_entry_index = i

        # Check for Basic auth
        basic_auth = detect_basic_auth(entry)
        if basic_auth:
            flow.auth_pattern = "basic_http"
            flow.auth_entry_index = i

        # Check for HNAP
        hnap_auth = detect_hnap_auth(entry)
        if hnap_auth:
            flow.auth_pattern = "hnap_session"
            flow.session_header = "HNAP_AUTH"
            flow.auth_entry_index = i

    # Classify pattern if not already set
    if flow.auth_pattern == "unknown":
        flow.auth_pattern = classify_auth_pattern(flow)

    # Add issues for missing info
    if not flow.login_url and flow.auth_pattern not in ("basic_http", "url_token_session", "hnap_session"):
        flow.issues.append("No login page detected")
    if not flow.password_field and flow.auth_pattern in ("form_plain", "form_base64", "credential_csrf"):
        flow.issues.append("No password field detected")
    if flow.credential_cookie and not flow.csrf_field:
        # Check if this might be credential_csrf without visible CSRF
        flow.issues.append("Credential cookie found but no CSRF - may need JS analysis")

    # Enhanced analysis (v2)
    flow.probe = extract_probes(har)
    if flow.probe and flow.probe.auth_error:
        flow.warnings.append(f"Pre-capture probe failed: {flow.probe.auth_error}")
    browser_cookies = extract_browser_cookies(har)
    flow.browser_cookies = browser_cookies
    flow.ghost_cookies = detect_ghost_cookies(cookie_info, browser_cookies)
    flow.page_auth_map = build_page_auth_map(entries)
    flow.is_post_auth, post_auth_warnings = detect_post_auth_capture(entries, flow.ghost_cookies, flow.page_auth_map)
    flow.warnings.extend(post_auth_warnings)

    # Classify genuinely public pages (no auth needed)
    if flow.auth_pattern == "unknown" and not flow.is_post_auth and _is_clean_no_auth(flow, entries):
        flow.auth_pattern = "none"

    flow.auth_confidence = assess_auth_confidence(flow, entries, flow.probe)

    # Interface type from page content types
    flow.interface_type = _detect_interface_type(flow)

    # Session summary — consolidate scattered fields
    flow.session = _build_session_summary(flow)

    return flow


def main():
    parser = argparse.ArgumentParser(description="Extract authentication patterns from HAR files")
    parser.add_argument("har_file", type=Path, help="Path to HAR file")
    parser.add_argument("--modem-yaml", type=Path, metavar="PATH", help="Cross-validate against modem.yaml")

    args = parser.parse_args()

    if not args.har_file.exists():
        print(f"Error: File not found: {args.har_file}", file=sys.stderr)
        sys.exit(1)

    try:
        har = load_har(args.har_file)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in HAR file: {e}", file=sys.stderr)
        sys.exit(1)

    flow = analyze_har(har)

    if args.modem_yaml:
        if not args.modem_yaml.exists():
            print(f"Error: modem.yaml not found: {args.modem_yaml}", file=sys.stderr)
            sys.exit(1)
        flow.modem_yaml_auth, flow.cross_validation_issues = cross_validate_modem_yaml(flow, args.modem_yaml)

    print(flow_to_json(flow))


if __name__ == "__main__":
    main()
