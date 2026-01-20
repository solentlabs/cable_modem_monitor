#!/usr/bin/env python3
"""Extract authentication patterns from HAR files.

Analyzes HTTP Archive (HAR) files to identify:
- Login form pages and field names
- Authentication POST requests
- Cookie/session management
- CSRF token patterns
- Redirect flows

Usage:
    python scripts/har_auth_extractor.py path/to/file.har
    python scripts/har_auth_extractor.py path/to/file.har --yaml
    python scripts/har_auth_extractor.py path/to/file.har --verbose
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from dataclasses import dataclass, field
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
class AuthFlow:
    """Extracted authentication flow from HAR."""

    modem_name: str | None = None
    auth_pattern: str = "unknown"

    # Login page info
    login_url: str | None = None
    login_method: str = "GET"
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

    # URL token (SB8200 pattern)
    url_token_prefix: str | None = None
    auth_header: str | None = None

    # Success indicators
    success_indicator: str | None = None
    success_status: int | None = None
    redirect_url: str | None = None

    # Raw entries for debugging
    login_entry_index: int | None = None
    auth_entry_index: int | None = None

    # Issues found
    issues: list[str] = field(default_factory=list)


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


def track_cookies(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Track cookie flow across all entries."""
    cookie_timeline: list[dict[str, Any]] = []
    known_cookies: set[str] = set()

    for i, entry in enumerate(entries):
        # Check response Set-Cookie headers
        for header in entry.get("response", {}).get("headers", []):
            if header["name"].lower() == "set-cookie":
                cookie_str = header["value"]
                cookie_name = cookie_str.split("=")[0].strip()
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
    if flow.session_header and "hnap" in (flow.session_header or "").lower():
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


def analyze_har(har: dict[str, Any]) -> AuthFlow:  # noqa: C901
    """Analyze HAR file and extract authentication flow."""
    flow = AuthFlow()
    entries = har.get("log", {}).get("entries", [])

    if not entries:
        flow.issues.append("No entries found in HAR")
        return flow

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

    return flow


def format_yaml(flow: AuthFlow) -> str:
    """Format auth flow as YAML."""
    lines = [
        f"modem: {flow.modem_name or 'unknown'}",
        f"auth_pattern: {flow.auth_pattern}",
        "",
        "# Login page",
        f"login_url: {flow.login_url or 'null'}",
        f"form_action: {flow.form_action or 'null'}",
        f"form_method: {flow.form_method}",
        "",
        "# Credential fields",
        f"username_field: {flow.username_field or 'null'}",
        f"password_field: {flow.password_field or 'null'}",
    ]

    if flow.csrf_field:
        lines.extend(
            [
                "",
                "# CSRF handling",
                f"csrf_field: {flow.csrf_field}",
                f"csrf_source: {flow.csrf_source}",
            ]
        )

    if flow.session_cookie or flow.credential_cookie:
        lines.extend(
            [
                "",
                "# Session management",
                f"session_cookie: {flow.session_cookie or 'null'}",
                f"credential_cookie: {flow.credential_cookie or 'null'}",
            ]
        )

    if flow.url_token_prefix:
        lines.extend(
            [
                "",
                "# URL token auth",
                f"url_token_prefix: {flow.url_token_prefix}",
                f"auth_header: {flow.auth_header or 'null'}",
            ]
        )

    if flow.form_fields:
        lines.extend(
            [
                "",
                "# Form fields",
                "fields:",
            ]
        )
        for f in flow.form_fields:
            lines.append(f"  - name: {f.name}")
            lines.append(f"    type: {f.field_type}")
            if f.value:
                lines.append(f"    value: {f.value}")

    if flow.issues:
        lines.extend(
            [
                "",
                "# Issues",
                "issues:",
            ]
        )
        for issue in flow.issues:
            lines.append(f"  - {issue}")

    return "\n".join(lines)


def format_text(flow: AuthFlow, verbose: bool = False) -> str:  # noqa: C901
    """Format auth flow as human-readable text."""
    lines = [
        f"Modem: {flow.modem_name or 'Unknown'}",
        f"Auth Pattern: {flow.auth_pattern}",
        "",
    ]

    if flow.login_url:
        lines.append(f"Login URL: {flow.login_url}")
    if flow.form_action:
        lines.append(f"Form Action: {flow.form_method} {flow.form_action}")
    if flow.username_field:
        lines.append(f"Username Field: {flow.username_field}")
    if flow.password_field:
        lines.append(f"Password Field: {flow.password_field}")
    if flow.csrf_field:
        lines.append(f"CSRF: {flow.csrf_field} (from {flow.csrf_source})")
    if flow.session_cookie:
        lines.append(f"Session Cookie: {flow.session_cookie}")
    if flow.credential_cookie:
        lines.append(f"Credential Cookie: {flow.credential_cookie}")
    if flow.url_token_prefix:
        lines.append(f"URL Token: ?{flow.url_token_prefix}<base64>")
    if flow.auth_header:
        lines.append(f"Auth Header: {flow.auth_header[:50]}...")

    if verbose and flow.form_fields:
        lines.extend(["", "Form Fields:"])
        for f in flow.form_fields:
            lines.append(f"  {f.name} ({f.field_type})")

    if flow.issues:
        lines.extend(["", "Issues:"])
        for issue in flow.issues:
            lines.append(f"  - {issue}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Extract authentication patterns from HAR files")
    parser.add_argument("har_file", type=Path, help="Path to HAR file")
    parser.add_argument("--yaml", action="store_true", help="Output as YAML")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

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

    if args.yaml:
        print(format_yaml(flow))
    else:
        print(format_text(flow, verbose=args.verbose))


if __name__ == "__main__":
    main()
