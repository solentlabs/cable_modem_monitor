"""Shared loader diagnostics — format request shape for failure logs.

When a loader raises or warns on an HTTP error, the failure message
should include enough request detail that a contributor's first log
paste shows what we sent — not just the status code. Without this, the
"modem rejected our request" loop costs N round-trips to discover the
header / query-param mismatch (see #86 retro for the concrete cost).

Auth strategies decide which header names to scrub from these logs
(see ``BaseAuthManager.headers``); from this module's point
of view a header is just a name + value, and the redaction list is
opaque input. This keeps token-knowledge in the auth layer instead of
encoding a central allowlist that drifts as new strategies arrive.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

import requests


def describe_request(
    req: requests.PreparedRequest | None,
    *,
    headers: frozenset[str],
    mask_query: bool = False,
) -> str:
    """Format a one-line summary of an outgoing request for failure logs.

    Includes method + full URL (query string preserved — needed to
    debug cache-buster / token query params) and headers actually
    sent. For each header whose lowercase name appears in
    ``headers``, the value is replaced with ``<set, len=N>``;
    the name itself is shown verbatim. ``mask_query`` is the caller's
    declaration that the URL query carries a session token; the whole
    query is then replaced the same way.
    """
    if req is None:
        return "(no PreparedRequest available)"
    url = req.url or ""
    if mask_query:
        # The caller knows it put a secret in the query; masking all of it
        # needs no guess about where the token sits, so it cannot fail open.
        parts = urlsplit(url)
        if parts.query:
            url = urlunsplit(parts._replace(query=f"<set, len={len(parts.query)}>"))
    safe_headers: list[str] = []
    for name, value in req.headers.items():
        if name.lower() in headers:
            safe_headers.append(f"{name}=<set, len={len(value)}>")
        else:
            safe_headers.append(f"{name}={value}")
    return f"{req.method} {url} [{', '.join(safe_headers)}]"
