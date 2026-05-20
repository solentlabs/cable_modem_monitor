"""Catalog fixture integrity checks.

Validates that committed HAR fixtures contain the responses the runtime
auth manager needs — specifically, that form-auth modems with a
``login_page`` configured have a usable login page response in the fixture
so hidden-field discovery (CSRF tokens, etc.) works against the mock server
the same way it will against real hardware.
"""

from __future__ import annotations

from typing import Any


def check_login_page_in_har(
    entries: list[dict[str, Any]],
    login_page: str,
    action: str,
) -> str:
    """Verify the HAR fixture has a usable login page response.

    For ``form`` auth modems that set ``login_page``, the runtime auth
    manager GETs that page before POSTing credentials to discover hidden
    fields (e.g. CSRF tokens).  If the fixture is missing that response or
    the response has no body, hidden-field discovery silently returns empty
    and the POST goes out without the required fields — authentication fails
    on real hardware while tests pass against the mock server.

    Three failure modes are reported:
    - No GET entry for ``login_page`` in the fixture.
    - Entry present but response body is empty.
    - Entry present and non-empty but does not contain ``action`` — the page
      is not the login form (wrong path configured).

    Args:
        entries: HAR ``log.entries`` list from the test fixture.
        login_page: Path configured in ``auth.login_page`` (e.g. ``/GenieLogin.asp``).
        action: Login POST endpoint from ``auth.action`` (e.g. ``/goform/GenieLogin``).

    Returns:
        Non-empty issue string on failure, empty string if the check passes.
    """
    from urllib.parse import urlparse

    norm = login_page if login_page.startswith("/") else f"/{login_page}"

    for entry in entries:
        req = entry.get("request", {})
        if req.get("method", "") != "GET":
            continue
        path = urlparse(req.get("url", "")).path
        if path != norm:
            continue
        content = entry.get("response", {}).get("content", {})
        text: str = content.get("text", "")
        if not text:
            return (
                f"login_page '{login_page}' response body is empty in the HAR fixture — "
                "the fixture must include the actual login page HTML so hidden fields "
                "(e.g. CSRF tokens) can be discovered at runtime"
            )
        action_rel = action.lstrip("/")
        if action not in text and action_rel not in text:
            return (
                f"login_page '{login_page}' HTML does not reference form action '{action}' — "
                "this entry may not be the login form; check that login_page is correct"
            )
        return ""

    return (
        f"login_page '{login_page}' has no GET entry in the HAR fixture — "
        "add the login page response so the auth manager can discover hidden fields"
    )
