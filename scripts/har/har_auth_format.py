#!/usr/bin/env python3
"""Render har_auth_extractor JSON as human-readable text or YAML.

Reads JSON produced by ``har_auth_extractor.py`` from stdin or a file argument
and renders it in a human-friendly format.

Usage:
    python scripts/har/har_auth_extractor.py file.har | python scripts/har/har_auth_format.py
    python scripts/har/har_auth_format.py --yaml < auth.json
    python scripts/har/har_auth_format.py -v auth.json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _text_auth_details(data: dict[str, Any]) -> list[str]:
    """Render optional auth-detail lines for text format."""
    lines: list[str] = []
    if data.get("login_url"):
        lines.append(f"Login URL: {data['login_url']}")
    if data.get("form_action"):
        lines.append(f"Form Action: {data.get('form_method', 'POST')} {data['form_action']}")
    if data.get("username_field"):
        lines.append(f"Username Field: {data['username_field']}")
    if data.get("password_field"):
        lines.append(f"Password Field: {data['password_field']}")
    if data.get("csrf_field"):
        lines.append(f"CSRF: {data['csrf_field']} (from {data.get('csrf_source', '?')})")
    if data.get("session_cookie"):
        lines.append(f"Session Cookie: {data['session_cookie']}")
    if data.get("credential_cookie"):
        lines.append(f"Credential Cookie: {data['credential_cookie']}")
    if data.get("url_token_prefix"):
        lines.append(f"URL Token: ?{data['url_token_prefix']}<base64>")
    if data.get("auth_header"):
        lines.append(f"Auth Header: {data['auth_header'][:50]}...")
    return lines


def _text_browser_cookies(data: dict[str, Any]) -> list[str]:
    """Render browser cookie snapshot section for text format."""
    browser = data.get("browser_cookies")
    if not browser:
        return []
    lines = ["", "Browser Cookies (snapshot after page load):"]
    for c in browser:
        flags = []
        if c.get("http_only"):
            flags.append("HttpOnly")
        if c.get("secure"):
            flags.append("Secure")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f"  {c['name']}{flag_str} — {c.get('domain', '?')}{c.get('path', '/')}")
    return lines


def _text_ghost_cookies(data: dict[str, Any]) -> list[str]:
    """Render ghost-cookie, browser-cookie, and probe sections for text format."""
    lines: list[str] = []
    ghosts = data.get("ghost_cookies") or []
    if ghosts:
        lines.extend(["", "Ghost Cookies (JS-set, never in Set-Cookie):"])
        for g in ghosts:
            lines.append(
                f"  {g['name']} [{g.get('category', '?')}]" f" — first seen entry[{g.get('first_seen_entry', '?')}]"
            )

    lines.extend(_text_browser_cookies(data))

    probe = data.get("probe")
    if probe:
        lines.extend(["", "Probe Data:"])
        if probe.get("auth_status_code") is not None:
            lines.append(f"  Auth status: {probe['auth_status_code']}")
        if probe.get("www_authenticate"):
            lines.append(f"  WWW-Authenticate: {probe['www_authenticate']}")
        if probe.get("auth_error"):
            lines.append(f"  Error: {probe['auth_error']}")
    return lines


def _text_verbose_sections(data: dict[str, Any]) -> list[str]:
    """Render verbose-only sections (form fields, page auth map)."""
    lines: list[str] = []
    form_fields = data.get("form_fields") or []
    if form_fields:
        lines.extend(["", "Form Fields:"])
        for f in form_fields:
            lines.append(f"  {f['name']} ({f.get('field_type', f.get('type', '?'))})")

    page_map = data.get("page_auth_map") or {}
    if page_map:
        lines.extend(["", "Page Auth Map:"])
        for path, summary in sorted(page_map.items()):
            status_str = ", ".join(str(s) for s in (summary.get("status_codes") or [])[:3])
            flags = []
            if summary.get("has_401"):
                flags.append("401")
            if summary.get("has_login_form"):
                flags.append("login-form")
            if summary.get("has_auth_header"):
                flags.append("auth-hdr")
            req_cookies = summary.get("request_cookies") or []
            if req_cookies:
                flags.append(f"cookies:{','.join(req_cookies[:3])}")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            lines.append(f"  {path} — {status_str}{flag_str}")
    return lines


def _text_diagnostics(data: dict[str, Any]) -> list[str]:
    """Render warnings, issues, and cross-validation sections."""
    lines: list[str] = []
    warnings = data.get("warnings") or []
    if warnings:
        lines.extend(["", "WARNINGS:"])
        for w in warnings:
            lines.append(f"  !! {w}")

    issues = data.get("issues") or []
    if issues:
        lines.extend(["", "Issues:"])
        for issue in issues:
            lines.append(f"  - {issue}")

    cv_issues = data.get("cross_validation_issues") or []
    if cv_issues:
        lines.extend(["", "Cross-Validation (modem.yaml):"])
        for cv in cv_issues:
            lines.append(f"  !! {cv}")
    return lines


def format_text(data: dict[str, Any], *, verbose: bool = False) -> str:
    """Render JSON data as human-readable text."""
    lines = [
        f"Modem: {data.get('modem_name') or 'Unknown'}",
        f"Protocol: {data.get('protocol', 'http')}",
        f"Interface: {data.get('interface_type', 'unknown')}",
        f"Auth Pattern: {data.get('auth_pattern', 'unknown')}",
        f"Confidence: {data.get('auth_confidence', 'low')}",
        f"Post-Auth Capture: {'yes' if data.get('is_post_auth') else 'no'}",
        "",
    ]
    lines.extend(_text_auth_details(data))
    lines.extend(_text_ghost_cookies(data))
    if verbose:
        lines.extend(_text_verbose_sections(data))
    lines.extend(_text_diagnostics(data))
    return "\n".join(lines)


def _yaml_list_section(comment: str, key: str, items: list[str]) -> list[str]:
    """Format a YAML list section with comment header."""
    if not items:
        return []
    lines = ["", comment, f"{key}:"]
    for item in items:
        lines.append(f"  - {item}")
    return lines


def _yaml_optional_sections(data: dict[str, Any]) -> list[str]:
    """Build optional YAML sections (CSRF, session, ghosts, form fields, etc.)."""
    lines: list[str] = []

    if data.get("csrf_field"):
        lines.extend(
            [
                "",
                "# CSRF handling",
                f"csrf_field: {data['csrf_field']}",
                f"csrf_source: {data.get('csrf_source') or 'null'}",
            ]
        )

    if data.get("session_cookie") or data.get("credential_cookie"):
        lines.extend(
            [
                "",
                "# Session management",
                f"session_cookie: {data.get('session_cookie') or 'null'}",
                f"credential_cookie: {data.get('credential_cookie') or 'null'}",
            ]
        )

    if data.get("url_token_prefix"):
        lines.extend(
            [
                "",
                "# URL token auth",
                f"url_token_prefix: {data['url_token_prefix']}",
                f"auth_header: {data.get('auth_header') or 'null'}",
            ]
        )

    ghosts = data.get("ghost_cookies") or []
    if ghosts:
        lines.extend(["", "# Ghost cookies (JS-set, never in Set-Cookie)", "ghost_cookies:"])
        for g in ghosts:
            lines.append(f"  - name: {g['name']}")
            lines.append(f"    category: {g.get('category', 'unknown')}")
            lines.append(f"    first_seen_entry: {g.get('first_seen_entry', '?')}")

    browser = data.get("browser_cookies")
    if browser:
        lines.extend(["", "# Browser cookies (snapshot after page load)", "browser_cookies:"])
        for c in browser:
            lines.append(f"  - name: {c['name']}")
            lines.append(f"    domain: {c.get('domain', '')}")
            lines.append(f"    path: {c.get('path', '/')}")
            if c.get("http_only"):
                lines.append("    http_only: true")
            if c.get("secure"):
                lines.append("    secure: true")

    lines.extend(_yaml_form_fields_and_diagnostics(data))
    return lines


def _yaml_form_fields_and_diagnostics(data: dict[str, Any]) -> list[str]:
    """Build YAML form-field, diagnostics, and probe sections."""
    lines: list[str] = []

    form_fields = data.get("form_fields") or []
    if form_fields:
        lines.extend(["", "# Form fields", "fields:"])
        for f in form_fields:
            lines.append(f"  - name: {f['name']}")
            lines.append(f"    type: {f.get('field_type', f.get('type', '?'))}")
            if f.get("value"):
                lines.append(f"    value: {f['value']}")

    lines.extend(_yaml_list_section("# Warnings", "warnings", data.get("warnings") or []))
    lines.extend(_yaml_list_section("# Issues", "issues", data.get("issues") or []))
    lines.extend(
        _yaml_list_section(
            "# Cross-validation (modem.yaml)",
            "cross_validation_issues",
            data.get("cross_validation_issues") or [],
        )
    )

    probe = data.get("probe")
    if probe:
        lines.extend(["", "# Probe data"])
        if probe.get("auth_status_code") is not None:
            lines.append(f"probe_auth_status: {probe['auth_status_code']}")
        if probe.get("www_authenticate"):
            lines.append(f"probe_www_authenticate: {probe['www_authenticate']}")
        if probe.get("auth_error"):
            lines.append(f"probe_error: {probe['auth_error']}")

    return lines


def format_yaml(data: dict[str, Any]) -> str:
    """Render JSON data as YAML-like output."""
    lines = [
        f"modem: {data.get('modem_name') or 'unknown'}",
        f"protocol: {data.get('protocol', 'http')}",
        f"interface_type: {data.get('interface_type', 'unknown')}",
        f"auth_pattern: {data.get('auth_pattern', 'unknown')}",
        f"auth_confidence: {data.get('auth_confidence', 'low')}",
        f"is_post_auth: {'true' if data.get('is_post_auth') else 'false'}",
        "",
        "# Login page",
        f"login_url: {data.get('login_url') or 'null'}",
        f"form_action: {data.get('form_action') or 'null'}",
        f"form_method: {data.get('form_method', 'POST')}",
        "",
        "# Credential fields",
        f"username_field: {data.get('username_field') or 'null'}",
        f"password_field: {data.get('password_field') or 'null'}",
    ]
    lines.extend(_yaml_optional_sections(data))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Render har_auth_extractor JSON as text or YAML",
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="JSON file (default: stdin)",
    )
    parser.add_argument("--yaml", action="store_true", help="Output as YAML")
    parser.add_argument("--verbose", "-v", action="store_true", help="Include page_auth_map detail")

    args = parser.parse_args()

    try:
        data = json.load(args.json_file)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if args.yaml:
        print(format_yaml(data))
    else:
        print(format_text(data, verbose=args.verbose))


if __name__ == "__main__":
    main()
