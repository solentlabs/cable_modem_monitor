"""Post-analysis JS endpoint discovery.

Scans all JavaScript content in the HAR — both standalone ``.js`` file
responses and inline ``<script>`` blocks in HTML pages — for server
endpoint references (AJAX calls, fetch targets).  Diffs these against
the captured request URLs and surfaces uncaptured endpoints as advisory
warnings.

**Why this exists:** Browser captures only record requests that fire
during the session.  Modem firmware JS may reference endpoints that
only fire under specific conditions (stale session state, keepalive
timers, conditional UI paths).  These endpoints can be critical to
the auth or session flow but invisible in the HAR.

See ONBOARDING_SPEC.md "Post-Analysis: JS Endpoint Discovery".
"""

from __future__ import annotations

import posixpath
import re
from typing import Any

from ..validation.har_utils import (
    WARNING_PREFIX,
    is_static_resource,
    path_from_url,
)

# -----------------------------------------------------------------------
# Comment stripping
# -----------------------------------------------------------------------

# Single-line // comments (but not :// in URLs)
_LINE_COMMENT = re.compile(r"(?<!:)//[^\n]*")

# Block /* ... */ comments
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)

# -----------------------------------------------------------------------
# AJAX/fetch endpoint extraction patterns
# -----------------------------------------------------------------------

# jQuery $.ajax / jQuery.ajax — scan ahead for url: "..." allowing
# nested braces (callbacks, config objects) between $.ajax({ and url:.
# Uses [\s\S] instead of [^}] so nested } doesn't terminate the match.
_JQUERY_AJAX = re.compile(
    r"""(?:\$|jQuery)\.ajax\s*\(\s*\{[\s\S]{0,500}?url\s*:\s*["']([^"']+)["']""",
)

# jQuery shorthand: $.post / $.get / $.getJSON / jQuery.post / etc.
_JQUERY_SHORTHAND = re.compile(
    r"""(?:\$|jQuery)\.(post|get|getJSON)\s*\(\s*["']([^"']+)["']""",
)

# Arris Touchstone firmware: createServerRecord("path", ...)
_CREATE_SERVER_RECORD = re.compile(
    r"""createServerRecord\s*\(\s*["']([^"']+)["']""",
)

# Fetch API: fetch("path", ...)
_FETCH_API = re.compile(
    r"""fetch\s*\(\s*["']([^"']+)["']""",
)

# XMLHttpRequest: .open("METHOD", "path")
_XHR_OPEN = re.compile(
    r"""\.open\s*\(\s*["'][A-Z]+["']\s*,\s*["']([^"']+)["']""",
)

_AJAX_PATTERNS: tuple[re.Pattern[str], ...] = (
    _JQUERY_AJAX,
    _JQUERY_SHORTHAND,
    _CREATE_SERVER_RECORD,
    _FETCH_API,
    _XHR_OPEN,
)

# Groups that contain the URL for each pattern (0-indexed capture group
# within the match).  Most patterns have the URL in group 1; jQuery
# shorthand has the method in group 1 and the URL in group 2.
_URL_GROUP: dict[re.Pattern[str], int] = {
    _JQUERY_SHORTHAND: 2,
}

# Inline <script> block extraction
_SCRIPT_BLOCK = re.compile(
    r"<script[^>]*>(.*?)</script>",
    re.DOTALL | re.IGNORECASE,
)


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------


def extract_endpoints_from_js(js_source: str) -> list[str]:
    """Extract server endpoint paths from a JavaScript source string.

    Scans for AJAX/fetch call patterns and returns the URL string
    literals found.  Variable references and static resources are
    filtered out.

    Args:
        js_source: JavaScript source code to scan.

    Returns:
        List of endpoint path strings (may contain relative paths
        like ``../../../php/foo.php``).  Deduplicated, order preserved.
    """
    # Strip comments to avoid matching patterns in commented-out code
    js_source = _strip_js_comments(js_source)

    seen: set[str] = set()
    result: list[str] = []

    for pattern in _AJAX_PATTERNS:
        group_idx = _URL_GROUP.get(pattern, 1)
        for match in pattern.finditer(js_source):
            url = match.group(group_idx)
            if url in seen:
                continue
            # Skip static resources — we only care about server endpoints
            if is_static_resource(url):
                continue
            # Skip bare directory prefixes from string concatenation
            # e.g. $.get("php/" + varName + "_data.php") matches "php/"
            if url.endswith("/"):
                continue
            seen.add(url)
            result.append(url)

    return result


def detect_uncaptured_endpoints(
    entries: list[dict[str, Any]],
    warnings: list[str],
) -> None:
    """Scan HAR JS content for server endpoints not captured as requests.

    Appends advisory warnings for each endpoint referenced in
    JavaScript but absent from the HAR request entries.

    Args:
        entries: HAR log entries.
        warnings: Mutable list to append warnings to.
    """
    captured = _collect_captured_paths(entries)
    uncaptured = _find_uncaptured(entries, captured)

    for endpoint in sorted(uncaptured):
        sources = sorted(uncaptured[endpoint])
        source_list = ", ".join(sources)
        warnings.append(
            f"{WARNING_PREFIX} JS references server endpoint not "
            f"captured in HAR: {endpoint} (referenced in {source_list})"
        )


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------


def _collect_captured_paths(entries: list[dict[str, Any]]) -> set[str]:
    """Build a set of all request paths from the HAR entries.

    Includes both the full normalized path and the bare filename
    to support matching against relative JS references.
    """
    captured: set[str] = set()
    for entry in entries:
        url = entry.get("request", {}).get("url", "")
        if url:
            path = path_from_url(url)
            captured.add(path)
            captured.add(path.rsplit("/", 1)[-1])
    return captured


def _find_uncaptured(
    entries: list[dict[str, Any]],
    captured: set[str],
) -> dict[str, set[str]]:
    """Scan entries for JS endpoint refs not in the captured set.

    Returns a dict mapping each uncaptured normalized endpoint path
    to the set of source labels that reference it.
    """
    uncaptured: dict[str, set[str]] = {}

    for entry in entries:
        for js_text, label in _extract_js_sources(entry):
            for ep in extract_endpoints_from_js(js_text):
                normalized = _normalize_path(ep)
                bare = normalized.rsplit("/", 1)[-1]
                if normalized not in captured and bare not in captured:
                    uncaptured.setdefault(normalized, set()).add(label)

    return uncaptured


def _extract_js_sources(
    entry: dict[str, Any],
) -> list[tuple[str, str]]:
    """Extract JS text and source labels from a single HAR entry.

    Returns (js_text, source_label) pairs from standalone ``.js``
    file responses and inline ``<script>`` blocks in HTML responses.
    """
    url = entry.get("request", {}).get("url", "")
    resp = entry.get("response", {})
    body = resp.get("content", {}).get("text", "")
    if not body:
        return []

    source_path = path_from_url(url) if url else "unknown"
    source_label = source_path.rsplit("/", 1)[-1]

    sources: list[tuple[str, str]] = []

    if _is_js_file(url):
        sources.append((body, source_label))

    content_type = resp.get("content", {}).get("mimeType", "")
    if "html" in content_type.lower():
        for block_match in _SCRIPT_BLOCK.finditer(body):
            block = block_match.group(1).strip()
            if block:
                page_label = f"inline JS in {source_label or '/'}"
                sources.append((block, page_label))

    return sources


def _strip_js_comments(source: str) -> str:
    """Remove JS comments to avoid matching patterns in dead code.

    Strips ``/* ... */`` block comments and ``// ...`` line comments.
    Preserves ``://`` in URLs (e.g., ``http://``).
    """
    source = _BLOCK_COMMENT.sub("", source)
    return _LINE_COMMENT.sub("", source)


def _is_js_file(url: str) -> bool:
    """Check if a URL points to a JavaScript file."""
    path = url.split("?", 1)[0].split("#", 1)[0]
    return path.lower().endswith(".js")


def _normalize_path(raw: str) -> str:
    """Normalize a JS endpoint path.

    Strips query strings and collapses ``../`` traversals.
    ``../../../php/foo.php`` becomes ``/php/foo.php``.
    """
    path = raw.split("?", 1)[0]
    # posixpath.normpath preserves leading ../ when no root anchor
    # exists — strip them so the result is an absolute server path.
    parts = posixpath.normpath(path).split("/")
    parts = [p for p in parts if p != ".."]
    path = "/".join(parts)
    if not path.startswith("/"):
        path = "/" + path
    return path
