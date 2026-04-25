"""Post-analysis -- request requirements detection.

Scans data-fetch entries for query parameters that appear on every
request, indicating a session-level requirement the modem firmware
imposes on all AJAX calls.

**Detection rule:** A query parameter present on every data-fetch
entry that carries a query string is a session requirement.
Entries with no query string (navigation pages, initial page
loads) are excluded from the count — they have no information
about session-level parameters.  Parameters appearing on fewer
entries are endpoint-specific and ignored.

**Known filter:** jQuery's ``cache: false`` adds ``_=<timestamp>``
to every AJAX request.  The bare ``_`` key is always excluded.

See ONBOARDING_SPEC.md "Post-Analysis: Request Requirements".
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

from ..analysis.format.http import identify_data_pages
from ..analysis.session import SessionDetail

# jQuery's ``cache: false`` adds ``_=<timestamp>`` to every AJAX
# request.  This is not a session requirement -- filter by name.
_JQUERY_CACHE_BUSTER: frozenset[str] = frozenset({"_"})


def detect_request_requirements(
    entries: list[dict[str, Any]],
    transport: str,
    session_result: SessionDetail,
    warnings: list[str],
) -> None:
    """Detect session-level query parameters on data-fetch entries.

    Mutates *session_result* and *warnings* in place.

    Args:
        entries: HAR ``log.entries`` list.
        transport: Detected transport (``http`` or ``hnap``).
        session_result: Phase 3 session result to augment.
        warnings: Mutable list to append warnings to.
    """
    if transport == "hnap":
        return

    data_pages = identify_data_pages(entries)
    if len(data_pages) < 2:
        return

    query_params = _detect_session_query_params(data_pages, session_result.token_prefix)
    if query_params:
        session_result.query_params = query_params
        param_list = ", ".join(f"{k}={v!r}" for k, v in query_params.items())
        warnings.append(
            f"Detected session-level query parameters on all data-fetch "
            f"requests: {param_list} — verify these are required by the "
            f"firmware (candidate for session.query_params in modem.yaml)."
        )


def _detect_session_query_params(
    data_pages: list[dict[str, Any]],
    token_prefix: str,
) -> dict[str, str]:
    """Find query params present on every data-fetch entry with a query string.

    Entries with no query string (navigation pages, initial page loads)
    are excluded from the count — they carry no information about
    session-level parameters.

    Auth-managed token params (matching ``token_prefix`` from Phase 3)
    are excluded — those belong on the auth strategy, not session.

    Returns a dict mapping param name to the first observed value.
    """
    # param_name -> list of values (one per entry that has the param)
    param_occurrences: dict[str, list[str]] = {}
    entries_with_qs = 0

    for entry in data_pages:
        url = entry["request"].get("url", "")
        params = _extract_query_params(url)
        if not params:
            continue
        entries_with_qs += 1
        for name, value in params.items():
            param_occurrences.setdefault(name, []).append(value)

    if entries_with_qs < 2:
        return {}

    result: dict[str, str] = {}
    for name, values in param_occurrences.items():
        if len(values) != entries_with_qs:
            continue
        if _is_known_cache_buster(name):
            continue
        if token_prefix and name.startswith(token_prefix):
            continue
        result[name] = values[0]

    return result


def _extract_query_params(url: str) -> dict[str, str]:
    """Extract query parameters from a URL as a flat dict.

    When a key appears multiple times, the first value wins.
    """
    parsed = urlparse(url)
    if not parsed.query:
        return {}
    qs = parse_qs(parsed.query, keep_blank_values=True)
    return {k: v[0] for k, v in qs.items()}


def _is_known_cache_buster(param_name: str) -> bool:
    """Check if a query parameter is a known non-session cache-buster."""
    return param_name in _JQUERY_CACHE_BUSTER
