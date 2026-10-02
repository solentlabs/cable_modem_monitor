"""Phase 4 - HTTP action detection.

Scans HAR entries for HTTP logout and restart endpoints using URL
pattern matching. Patterns are loaded from ``action_patterns.json``.

Per docs/ONBOARDING_SPEC.md Phase 4 (HTTP transport).
"""

from __future__ import annotations

import json
import re
from typing import Any

from ...validation.har_utils import WRITE_METHODS, is_static_resource, parse_form_params, path_from_url
from ..types import CoreGap
from .callsite import find_ajax_callsites
from .patterns import get_logout_patterns, get_restart_patterns
from .types import ActionDetail, ActionsDetail, sanitized_paths

# ---------------------------------------------------------------------------
# Endpoint patterns (loaded from action_patterns.json)
# ---------------------------------------------------------------------------

_LOGOUT_PATTERNS = get_logout_patterns()
_RESTART_PATTERNS = get_restart_patterns()


_ACTION_PARAM_INDICATORS = frozenset({"reboot", "restart", "reset", "logout", "logoff", "action", "security"})

# Matches quoted strings in HTML/JS source that could be URL paths.
# Intentionally broad — patterns filter for meaningful matches.
_SOURCE_CANDIDATE_PATTERN = re.compile(r'["\']([^\'"<>\s]{3,200})["\']')

# Attribute values may be quoted or bare (mb7621: action=/goform/MotoSecurity)
_FORM_ACTION_PATTERN = re.compile(
    r"<form[^>]*\saction=(?:[\"']([^\"']+)[\"']|([^\s>\"']+))[^>]*>",
    re.IGNORECASE,
)
_FORM_METHOD_PATTERN = re.compile(r"\smethod=(?:[\"']([A-Za-z]+)[\"']|([A-Za-z]+))", re.IGNORECASE)
_FORM_FIELD_NAME_PATTERN = re.compile(r"<(?:input|button)[^>]*\sname=[\"']([^\"']+)[\"']", re.IGNORECASE)


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
    cookie_names = _collect_set_cookie_names(entries)

    logout = _find_http_action(entries, _LOGOUT_PATTERNS, "logout", warnings)
    if logout is None:
        logout = _find_http_action_in_source(entries, _LOGOUT_PATTERNS, "logout", cookie_names, warnings)

    restart = _find_http_action(entries, _RESTART_PATTERNS, "restart", warnings)
    if restart is None:
        restart = _find_http_action_in_source(entries, _RESTART_PATTERNS, "restart", cookie_names, warnings)

    for action_name, action in (("logout", logout), ("restart", restart)):
        _report_unobserved_body(action_name, action, warnings)

    # Flag unmatched action-like POSTs as core gaps (only when both traffic
    # and source-scan came up empty — source_inferred counts as found)
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
    """Find an HTTP action matching any of the given URL patterns.

    A write (POST, PUT, PATCH) match outranks an earlier page GET:
    auto-action pages (a GET whose form JS fires the operative write)
    precede that write in traffic and match the same patterns, but the
    write is the action and the page is only its pre-fetch source
    (Netgear /Logout.htm -> /goform/logout).
    """
    first_match: tuple[int, dict[str, Any]] | None = None
    for idx, entry in enumerate(entries):
        req = entry["request"]
        path = path_from_url(req.get("url", ""))
        if not any(p.search(path) for p in patterns):
            continue
        if first_match is None:
            first_match = (idx, entry)
        if req.get("method", "").upper() in WRITE_METHODS:
            first_match = (idx, entry)
            break

    if first_match is None:
        return None

    idx, entry = first_match
    req = entry["request"]
    path = path_from_url(req.get("url", ""))
    params, json_body = _observed_body(req.get("postData", {}))
    body = ""
    body_evidence: dict[str, Any] = {}
    placeholders = sanitized_paths(json_body) if json_body is not None else []
    if json_body is not None and placeholders:
        # A placeholder is not the firmware's value; copying the body would
        # write a wrong one (an SJCL envelope's sanitized user, tg3442s)
        body, body_evidence = "encoded", {"keys": list(json_body), "sanitized": placeholders}
        warnings.append(
            f"{action_name} action {req.get('method', '')} {path}: the observed JSON body holds "
            f"sanitized or encoded values {placeholders} and was not copied to json_body. Check "
            f"Core's body_encoding: session and the page script for the plain body."
        )
        json_body = None
    detail = ActionDetail(
        type="http",
        method=req.get("method", ""),
        endpoint=path,
        params=params,
        json_body=json_body,
        body=body,
        body_evidence=body_evidence,
    )
    # A captured page whose form posts to this endpoint is the
    # pre-fetch source; deterministic, unlike the keyword
    # suggestion below, which stays warning-only
    form_page = _find_form_page_for_endpoint(entries, path)
    if form_page is not None:
        page_path, form_action = form_page
        detail.pre_fetch_url = page_path
        if "?" in form_action:
            detail.endpoint_pattern = path.rstrip("/").rsplit("/", 1)[-1]
    else:
        _suggest_pre_fetch_url(entries, idx, path, action_name, warnings)
    return detail


def _observed_body(post_data: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any] | None]:
    """(form params, JSON object body) of a captured request; at most one is non-empty."""
    text = post_data.get("text", "")
    # A JSON body is checked first: its values may hold "=", which the form
    # parser would split into bogus pairs
    if text.lstrip().startswith("{"):
        try:
            body = json.loads(text)
        except ValueError:
            body = None
        if isinstance(body, dict):
            return {}, body
    return parse_form_params(post_data), None


def _report_unobserved_body(action_name: str, action: ActionDetail | None, warnings: list[str]) -> None:
    """Mark and warn when a non-GET action came from page source with no body to copy."""
    # Bodies come from the capture only. Synthesizing one from page script
    # risks a wrong body, which is worse than none.
    if action is None or action.source != "source_inferred" or action.method.upper() == "GET" or action.params:
        return
    action.body = "unobserved"
    warnings.append(
        f"{action_name} action {action.method} {action.endpoint} (source_inferred): request body "
        f"unobserved. The capture holds no request to this endpoint, so neither params nor "
        f"json_body is generated. Capture the {action_name} to supply its body; never copy it "
        f"from page script."
    )


def _find_form_page_for_endpoint(
    entries: list[dict[str, Any]],
    endpoint: str,
) -> tuple[str, str] | None:
    """(page path, form action) for a captured page whose form posts to ``endpoint``."""
    for entry in entries:
        body = entry.get("response", {}).get("content", {}).get("text", "")
        if not body or "<form" not in body.lower():
            continue
        for match in _FORM_ACTION_PATTERN.finditer(body):
            raw = match.group(1) or match.group(2) or ""
            path = raw if raw.startswith("/") else f"/{raw}"
            if path.split("?", 1)[0] == endpoint:
                return path_from_url(entry["request"].get("url", "")), path
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


def _find_http_action_in_source(
    entries: list[dict[str, Any]],
    patterns: tuple[re.Pattern[str], ...],
    action_name: str,
    cookie_names: frozenset[str],
    warnings: list[str],
) -> ActionDetail | None:
    """Scan captured page source for action endpoint references.

    Used as a fallback when no matching request appears in HAR traffic.
    Pass 1 parses ``$.ajax({...})`` call sites (method + data params).
    Pass 2 reads ``<form action>`` URLs (method + Core pre-fetch shape
    for session-tokenized endpoints). Pass 3 falls back to bare quoted
    strings (endpoint only). Either way the result is source_inferred.
    """
    fallback_method = "GET" if action_name == "logout" else "POST"

    return (
        _find_action_in_ajax_callsites(entries, patterns, action_name, fallback_method, cookie_names, warnings)
        or _find_action_in_form_actions(entries, patterns, action_name, fallback_method, warnings)
        or _find_action_in_quoted_strings(entries, patterns, fallback_method)
    )


def _find_action_in_ajax_callsites(
    entries: list[dict[str, Any]],
    patterns: tuple[re.Pattern[str], ...],
    action_name: str,
    fallback_method: str,
    cookie_names: frozenset[str],
    warnings: list[str],
) -> ActionDetail | None:
    """Find an action endpoint at a ``$.ajax({...})`` call site."""
    for entry in entries:
        body = entry.get("response", {}).get("content", {}).get("text", "")
        if not body or "$.ajax" not in body:
            continue
        for site in find_ajax_callsites(body):
            path = site.url if site.url.startswith("/") else f"/{site.url}"
            if not any(p.search(path) for p in patterns):
                continue
            params = _resolve_callsite_params(site.params, site.unresolved, cookie_names, action_name, path, warnings)
            if site.data_identifier:
                warnings.append(
                    f"{action_name} action {path} (source_inferred): data payload is the "
                    f"JS identifier '{site.data_identifier}' — params could not be "
                    f"extracted from the call site."
                )
            return ActionDetail(
                type="http",
                # jQuery defaults a missing `type:` to GET, but every fleet action
                # call site declares it; absent type falls back to the action-name
                # prior rather than the jQuery default.
                method=site.method or fallback_method,
                endpoint=path,
                params=params,
                source="source_inferred",
            )
    return None


def _looks_like_endpoint(raw: str) -> bool:
    """Check if a quoted source string reads as a request path, not a label or asset."""
    # A bare word ("Reboot") is a UI label; ".." segments and static assets
    # are page furniture. Matching them fabricates endpoints the firmware
    # never exposes.
    if ".." in raw.split("/"):
        return False
    if is_static_resource(raw):
        return False
    last_segment = raw.rstrip("/").rsplit("/", 1)[-1].split("?", 1)[0]
    return "/" in raw or "." in last_segment


def _find_action_in_quoted_strings(
    entries: list[dict[str, Any]],
    patterns: tuple[re.Pattern[str], ...],
    fallback_method: str,
) -> ActionDetail | None:
    """Find an action endpoint as a bare quoted string (endpoint only)."""
    for entry in entries:
        body = entry.get("response", {}).get("content", {}).get("text", "")
        if not body:
            continue
        for match in _SOURCE_CANDIDATE_PATTERN.finditer(body):
            raw = match.group(1)
            if not _looks_like_endpoint(raw):
                continue
            path = raw if raw.startswith("/") else f"/{raw}"
            if any(p.search(path) for p in patterns):
                return ActionDetail(
                    type="http",
                    method=fallback_method,
                    endpoint=path,
                    source="source_inferred",
                )
    return None


def _find_action_in_form_actions(
    entries: list[dict[str, Any]],
    patterns: tuple[re.Pattern[str], ...],
    action_name: str,
    fallback_method: str,
    warnings: list[str],
) -> ActionDetail | None:
    """Find an action endpoint in a captured page's ``<form action>``.

    A query string on the form action is a per-session dynamic token
    (Netgear ``?id=``), so the config gets the Core pre-fetch shape:
    bare endpoint as fallback, endpoint_pattern keyword, pre_fetch_url
    pointing at the page that embeds the live URL. Form input values
    are rewritten by page JS before submit, so params are never
    extracted — the warning names the fields for the manual step.
    """
    for entry in entries:
        body = entry.get("response", {}).get("content", {}).get("text", "")
        if not body or "<form" not in body.lower():
            continue
        for match in _FORM_ACTION_PATTERN.finditer(body):
            raw = match.group(1) or match.group(2) or ""
            path = raw if raw.startswith("/") else f"/{raw}"
            if not any(p.search(path) for p in patterns):
                continue
            bare = path.split("?", 1)[0]
            method_match = _FORM_METHOD_PATTERN.search(match.group(0))
            field_names = _form_field_names(body, match.end())
            if field_names:
                warnings.append(
                    f"{action_name} action {bare} (source_inferred): form fields "
                    f"{field_names} not extracted — input values are set by page "
                    f"script at submit time; resolve required params manually "
                    f"from the page source."
                )
            dynamic = "?" in path
            return ActionDetail(
                type="http",
                method=(method_match.group(1) or method_match.group(2)).upper() if method_match else fallback_method,
                endpoint=bare,
                source="source_inferred",
                pre_fetch_url=path_from_url(entry["request"].get("url", "")) if dynamic else "",
                endpoint_pattern=bare.rstrip("/").rsplit("/", 1)[-1] if dynamic else "",
            )
    return None


def _form_field_names(body: str, form_tag_end: int) -> list[str]:
    """Named input/button fields between a form's open tag and ``</form>``."""
    close = body.find("</form>", form_tag_end)
    innards = body[form_tag_end : close if close >= 0 else len(body)]
    return sorted(set(_FORM_FIELD_NAME_PATTERN.findall(innards)))


def _resolve_callsite_params(
    literals: dict[str, str],
    unresolved: dict[str, str],
    cookie_names: frozenset[str],
    action_name: str,
    path: str,
    warnings: list[str],
) -> dict[str, str]:
    """Resolve call-site data params to config values.

    A param whose name matches a Set-Cookie name observed in the HAR
    resolves to a ``{cookie:name}`` directive (double-submit CSRF shape)
    — this wins even over a literal value, which would be the captured
    session's token, not a reusable one. Remaining literals are emitted
    verbatim; computed expressions are dropped with a warning.
    """
    params: dict[str, str] = {}
    for name, value in literals.items():
        params[name] = f"{{cookie:{name}}}" if name in cookie_names else value
    for name, expression in unresolved.items():
        if name in cookie_names:
            params[name] = f"{{cookie:{name}}}"
        else:
            warnings.append(
                f"{action_name} action {path} (source_inferred): param '{name}' is "
                f"computed in page script ({expression!r}) — resolve its value "
                f"manually from the page source."
            )
    return params


def _collect_set_cookie_names(entries: list[dict[str, Any]]) -> frozenset[str]:
    """Cookie names the modem issues via Set-Cookie response headers."""
    names: set[str] = set()
    for entry in entries:
        for header in entry.get("response", {}).get("headers", []):
            value = header.get("value", "")
            if header.get("name", "").lower() == "set-cookie" and "=" in value:
                names.add(value.split("=", 1)[0].strip())
    return frozenset(names)


def _unmatched_category(
    indicators: list[str],
    found_logout: ActionDetail | None,
    found_restart: ActionDetail | None,
) -> str | None:
    """Classify action-like param indicators as an unmatched logout or restart, or None."""
    # Classify as logout-like or restart-like
    logout_indicators = {"logout", "logoff"}
    restart_indicators = {"reboot", "restart", "reset", "action", "security"}

    if not found_logout and logout_indicators & set(indicators):
        return "unmatched_logout"
    if not found_restart and restart_indicators & set(indicators):
        return "unmatched_restart"
    return None


def _detect_unmatched_actions(
    entries: list[dict[str, Any]],
    found_logout: ActionDetail | None,
    found_restart: ActionDetail | None,
    core_gaps: list[CoreGap],
) -> None:
    """Flag write requests with action-like params as core gaps.

    Scans entries for POST, PUT and PATCH requests whose param names (or JSON body keys) contain
    action indicators but whose URLs didn't match the pattern lists.
    """
    matched_endpoints = set()
    if found_logout:
        matched_endpoints.add(found_logout.endpoint)
    if found_restart:
        matched_endpoints.add(found_restart.endpoint)

    # A page that repeats a write (a logout clicked twice) is one gap citing every entry.
    seen: dict[tuple[str, str, str], CoreGap] = {}
    for index, entry in enumerate(entries):
        req = entry["request"]
        method = req.get("method", "").upper()
        if method not in WRITE_METHODS:
            continue
        path = path_from_url(req.get("url", ""))
        if path in matched_endpoints:
            continue

        params, json_body = _observed_body(req.get("postData", {}))
        # A JSON body's top-level keys play the role of form param names
        names = list(json_body) if json_body else list(params)
        if not names:
            continue

        indicators = [ind for ind in _ACTION_PARAM_INDICATORS if any(ind in name.lower() for name in names)]
        category = _unmatched_category(indicators, found_logout, found_restart)
        if category is None:
            continue

        key = (category, method, path)
        if key in seen:
            seen[key].evidence["entries"].append(index)
            continue
        seen[key] = CoreGap(
            phase="actions",
            category=category,
            summary=f"{method} to {path} has action-like params but URL not in patterns",
            evidence={
                "endpoint": path,
                "method": method,
                **({"json_body": json_body} if json_body else {"params": params}),
                "indicators": indicators,
                "entries": [index],
            },
        )
        core_gaps.append(seen[key])
