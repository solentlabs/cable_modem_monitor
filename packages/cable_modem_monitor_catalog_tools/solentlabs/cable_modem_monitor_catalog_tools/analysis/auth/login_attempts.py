"""Form login attempts: which one the server accepted, and what separates it from a rejected one.

A capture can hold several credential POSTs to the login endpoint: a typo,
a retry, or the capture guide's deliberate wrong password. The accepted
attempt is selected by its response, never by position: an attempt whose
answer is the login form again is a refusal and ranks below the rest.
When the accepted
response is not a redirect, the tokens it holds that a rejected response
lacks are offered as ``auth.success.indicator`` candidates.

Per docs/ONBOARDING_SPEC.md Phase 2 and § Ambiguities.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from ...validation.har_utils import WARNING_PREFIX, has_set_cookie, lower_headers, path_from_url
from ..ambiguity import Ambiguity, Candidate, Evidence
from ..login_form import has_password_input

_REDIRECTS = (301, 302)
# A quoted attribute (http-equiv="refresh") stays whole; anything else splits on
# whitespace and markup delimiters.
_TOKEN = re.compile(r'[\w-]+="[^"]*"|[^\s<>]+')
_MAX_CANDIDATES = 6
_CONTEXT_CHARS = 40
_REJECTED_SNIPPET_CHARS = 200


def attempt_rank(entry: dict[str, Any], entries: list[dict[str, Any]]) -> int:
    """-1 for a refusal, else 2 when the response redirects to another path, 1 when it sets a cookie, 0 otherwise."""
    if is_refusal(entry, entries):
        return -1
    resp = entry["response"]
    if resp.get("status") in _REDIRECTS:
        location = lower_headers(resp).get("location", "")
        if location and path_from_url(location) != path_from_url(entry["request"].get("url", "")):
            return 2
    return 1 if has_set_cookie(resp) else 0


def is_refusal(entry: dict[str, Any], entries: list[dict[str, Any]]) -> bool:
    """True when the attempt's answer is the login page again, wherever the attempt sits in the capture.

    Either its own body is that page (a 200 re-render) or the page its
    redirect lands on is. The page must hold a password input, Core's own
    login-page test (a tree parse misses firmware markup that closes the
    form early), and name the endpoint the attempt posted to: a home page
    with a change-password form is not the login page. A redirect whose
    target the capture never fetched says nothing, so the attempt is not
    called a refusal.
    """
    resp = entry["response"]
    request_url = entry["request"].get("url", "")
    login_path = path_from_url(request_url)
    if _is_login_page(_body(entry), login_path):
        return True
    location = lower_headers(resp).get("location", "")
    if resp.get("status") not in _REDIRECTS or not location:
        return False
    target = path_from_url(urljoin(request_url, location))
    position = next((i for i, e in enumerate(entries) if e is entry), len(entries))
    for later in entries[position + 1 :]:
        if later["request"].get("method") == "GET" and path_from_url(later["request"].get("url", "")) == target:
            return _is_login_page(_body(later), login_path)
    return False


def _is_login_page(text: str, login_path: str) -> bool:
    """A password input on a page that references the login endpoint."""
    return has_password_input(text) and login_path in text


def redirect_conflict_warning(
    accepted: dict[str, Any], attempts: list[dict[str, Any]], entries: list[dict[str, Any]]
) -> str | None:
    """A warning when attempts ranked with the accepted one redirect to different paths."""
    rank = attempt_rank(accepted, entries)
    if rank != 2:
        return None
    paths = sorted(
        {path_from_url(lower_headers(a["response"])["location"]) for a in attempts if attempt_rank(a, entries) == 2}
    )
    if len(paths) < 2:
        return None
    return (
        f"{WARNING_PREFIX} login attempts redirect to different paths ({', '.join(paths)}); "
        f"the latest was kept. Verify auth.success.redirect."
    )


def success_indicator_ambiguity(accepted: dict[str, Any], attempts: list[dict[str, Any]]) -> Ambiguity | None:
    """Candidates for ``auth.success.indicator``: tokens only the accepted response has, or None."""
    accepted_text = _body(accepted)
    if not accepted_text:
        return None
    rejected = [a for a in attempts if a is not accepted and _body(a) != accepted_text]
    if not rejected:
        return None
    rejected_texts = [_body(a) for a in rejected]
    tokens: list[str] = []
    for token in _TOKEN.findall(accepted_text):
        if len(token) < 3 or not re.search(r"\w", token) or token in tokens:
            continue
        if any(token in text for text in rejected_texts):
            continue
        tokens.append(token)
    if not tokens:
        return None

    source = path_from_url(accepted["request"].get("url", ""))
    rejected_start = " ".join(rejected_texts[-1].split())[:_REJECTED_SNIPPET_CHARS]
    candidates = [
        Candidate(
            value=token,
            evidence=[
                Evidence(source=source, snippet=_around(accepted_text, token)),
                Evidence(source=f"{source} (rejected attempt)", snippet=rejected_start),
            ],
        )
        for token in tokens[:_MAX_CANDIDATES]
    ]
    return Ambiguity(field="auth.success.indicator", blocking=False, candidates=candidates)


def _body(entry: dict[str, Any]) -> str:
    """The attempt's response body as captured, or empty."""
    return str((entry["response"].get("content") or {}).get("text") or "").strip()


def _around(text: str, token: str) -> str:
    """The token with a few characters of its surroundings, whitespace collapsed."""
    start = text.find(token)
    return " ".join(text[max(0, start - _CONTEXT_CHARS) : start + len(token) + _CONTEXT_CHARS].split())
