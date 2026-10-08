"""Post-analysis hard stops that guard Core's login-page detection.

Core decides that a fetched page is a login page by one signal: a
``type="password"`` substring (``loaders/http.py::_is_login_page``). Two
captures defeat it, and each is a hard stop that needs human review:

1. The login page auth analysis identified carries no password input
   (a script renders it), so an expired session goes unrecognized.
2. A data page the config will fetch carries a password input, so every
   poll reads as an expired session and the auth circuit breaker opens.

Scope mirrors runtime: HTTP transport, a strategy that holds a session,
and HTML responses. The data pages are the sections' ``resource`` values,
the same fetch list ``parser.yaml`` carries, not every page in the HAR:
the login page and the post-login redirect target are not fetched.

See RESOURCE_LOADING_SPEC.md § MCP onboarding validation.
"""

from __future__ import annotations

from typing import Any

from solentlabs.cable_modem_monitor_core.models.modem_config.auth import get_auth_strategy_rows

from ..validation.har_utils import (
    HARD_STOP_PREFIX,
    content_type_of,
    decode_body,
    path_from_url,
)
from .auth.types import AuthDetail
from .format.http import identify_data_pages
from .unread_resources import collect_resources, normalize_endpoint


def has_password_input(text: str) -> bool:
    """Match Core's login-page test, so intake and runtime agree."""
    lower = text.lower()
    return 'type="password"' in lower or "type='password'" in lower


def detect_login_page_hard_stops(
    entries: list[dict[str, Any]],
    sections: dict[str, Any] | None,
    auth: AuthDetail,
    transport: str,
) -> list[str]:
    """Return the login-page hard stops for a capture, empty when out of scope."""
    if not _detection_applies(auth.strategy, transport):
        return []

    data_paths = list(dict.fromkeys(normalize_endpoint(resource) for resource in collect_resources(sections)))

    issues: list[str] = []
    login_page = auth.fields.get("login_page")
    if isinstance(login_page, str) and login_page:
        login_path = normalize_endpoint(login_page)
        # url_token names the status page as login_page; a page the config reads
        # as data is not a login page, and the data-page check covers it.
        if login_path not in data_paths:
            issues.extend(_login_page_without_password(entries, login_path))

    for path in data_paths:
        issues.extend(_data_page_with_password(entries, path))
    return issues


def _detection_applies(strategy: str, transport: str) -> bool:
    """Whether Core's runtime login-page detection runs for this strategy."""
    if transport != "http":
        return False
    row = next((r for r in get_auth_strategy_rows() if r.strategy == strategy), None)
    return row is not None and not row.stateless and row.transport == "http"


def _html_pages(entries: list[dict[str, Any]], path: str) -> list[tuple[int, str]]:
    """Index and body of each 200 HTML response captured for ``path``."""
    pages: list[tuple[int, str]] = []
    for index, entry in enumerate(entries):
        response = entry.get("response", {})
        if response.get("status") != 200:
            continue
        if path_from_url(entry.get("request", {}).get("url", "")) != path:
            continue
        if "html" not in content_type_of(response):
            continue
        pages.append((index, decode_body(response)))
    return pages


def _login_page_without_password(entries: list[dict[str, Any]], path: str) -> list[str]:
    """Flag 1: the login page is captured and none of its responses has a password input."""
    pages = _html_pages(entries, path)
    if not pages or any(has_password_input(body) for _, body in pages):
        return []
    index, body = pages[-1]
    return [
        f"{HARD_STOP_PREFIX} Login page {path} (entry [{index}], {len(body)} bytes) has no "
        '<input type="password">, and Core recognizes a login page by that input alone, so an '
        "expired session on this modem would go unnoticed. Either the capture holds the page "
        "before its script ran (recapture after the page finishes loading), or the input is "
        "rendered by script and Core needs another login-page signal."
    ]


def _data_page_with_password(entries: list[dict[str, Any]], path: str) -> list[str]:
    """Flag 2: the response analysis reads for a fetched data page contains a password input."""
    # identify_data_pages picks one response per path, the one Phase 5 parses. A modem
    # answers an unauthenticated visit with its login page at the same URL, and that
    # pre-login response is not what the parser reads.
    for entry in identify_data_pages(entries):
        if path_from_url(entry.get("request", {}).get("url", "")) != path:
            continue
        response = entry.get("response", {})
        body = decode_body(response)
        if "html" in content_type_of(response) and has_password_input(body):
            index = next(i for i, candidate in enumerate(entries) if candidate is entry)
            return [
                f"{HARD_STOP_PREFIX} Data page {path} (entry [{index}]) contains a password field, "
                "so Core would read it as a login page on every poll, open the auth circuit "
                "breaker and prompt for credentials that are not wrong. Confirm the page is a "
                "data page; if it is, Core needs a way to exempt it from login-page detection."
            ]
    return []
