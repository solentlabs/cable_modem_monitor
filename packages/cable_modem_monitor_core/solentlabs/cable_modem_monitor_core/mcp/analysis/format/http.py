"""Phase 5 - HTTP format detection.

Identifies data pages in the HAR and classifies their format:
table, table_transposed, javascript, json, or html_fields.

Per docs/ONBOARDING_SPEC.md Phase 5 (HTTP transport).
"""

from __future__ import annotations

import json as json_mod
import re
from typing import Any

from ...validation.har_utils import (
    has_content,
    is_static_resource,
    lower_headers,
    path_from_url,
)
from .html_parsing import detect_label_pairs, detect_tables
from .table_analysis import is_channel_table, is_transposed
from .types import (
    DetectedJsFunction,
    PageAnalysis,
)

# -----------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------

_DATA_CONTENT_TYPES: frozenset[str] = frozenset({"text/html", "application/json", "application/xml", "text/xml"})

# JS function name pattern for channel data (Init*TagValue)
_JS_FUNCTION_PATTERN = re.compile(
    r"function\s+(Init\w*TagValue)\s*\([^)]*\)\s*\{(.*?)\n\s*\}",
    re.DOTALL,
)

# JS tagValueList assignment pattern
_JS_TAG_VALUE_PATTERN = re.compile(
    r"(?:var\s+)?tagValueList\s*=\s*['\"]([^'\"]+)['\"]",
)

# Common JS delimiters
_JS_DELIMITERS: tuple[str, ...] = ("|", ",", ";", "^")


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------


def identify_data_pages(
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter HAR entries to data pages.

    Returns entries with: status 200, non-static, has content,
    and data-bearing Content-Type.
    """
    result: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for entry in entries:
        resp = entry.get("response", {})
        req = entry.get("request", {})
        url = req.get("url", "")
        status = resp.get("status", 0)

        if status != 200:
            continue
        if is_static_resource(url):
            continue
        if not has_content(resp):
            continue

        content_type = _extract_content_type(resp)
        if not any(ct in content_type for ct in _DATA_CONTENT_TYPES):
            continue

        # Deduplicate by path
        path = path_from_url(url)
        if path in seen_paths:
            continue
        seen_paths.add(path)

        result.append(entry)

    return result


def analyze_page(entry: dict[str, Any]) -> PageAnalysis:
    """Analyze a single data page entry for extractable content.

    Returns a PageAnalysis with all detected content types:
    tables, JS functions, label-value pairs, and/or JSON data.
    A page can contribute to multiple sections.
    """
    req = entry.get("request", {})
    resp = entry.get("response", {})
    url = req.get("url", "")
    resource = path_from_url(url)
    content_type = _extract_content_type(resp)
    body = resp.get("content", {}).get("text", "")

    page = PageAnalysis(resource=resource, content_type=content_type)

    if "application/json" in content_type:
        page.json_data = _parse_json_body(body)
    elif "text/html" in content_type:
        page.tables = detect_tables(body)
        page.js_functions = _detect_js_functions(body)
        page.label_pairs = detect_label_pairs(body)

    return page


def classify_page_format(page: PageAnalysis) -> str:
    """Classify the primary data format of a page.

    Returns one of: json, javascript, table, table_transposed,
    html_fields, or unknown.
    """
    if page.json_data is not None:
        return "json"

    if page.js_functions:
        return "javascript"

    if page.tables:
        # Check if any table has channel data
        for table in page.tables:
            if is_channel_table(table):
                if is_transposed(table):
                    return "table_transposed"
                return "table"

    if page.label_pairs:
        return "html_fields"

    return "unknown"


# -----------------------------------------------------------------------
# JavaScript data detection
# -----------------------------------------------------------------------


def _detect_js_functions(body: str) -> list[DetectedJsFunction]:
    """Detect JS functions with delimited data strings."""
    functions: list[DetectedJsFunction] = []

    for match in _JS_FUNCTION_PATTERN.finditer(body):
        name = match.group(1)
        func_body = match.group(2)

        # Look for tagValueList assignment
        tag_match = _JS_TAG_VALUE_PATTERN.search(func_body)
        if not tag_match:
            continue

        raw_value = tag_match.group(1)

        # Detect delimiter
        delimiter = _detect_delimiter(raw_value)
        if not delimiter:
            continue

        values = raw_value.split(delimiter)
        if len(values) < 3:
            continue

        functions.append(
            DetectedJsFunction(
                name=name,
                body=func_body,
                delimiter=delimiter,
                values=values,
            )
        )

    return functions


def _detect_delimiter(raw_value: str) -> str:
    """Detect the delimiter character in a delimited string."""
    for d in _JS_DELIMITERS:
        if d in raw_value:
            parts = raw_value.split(d)
            if len(parts) >= 3:
                return d
    return ""


# -----------------------------------------------------------------------
# JSON body parsing
# -----------------------------------------------------------------------


def _parse_json_body(body: str) -> dict[str, Any] | None:
    """Parse a JSON response body, returning None on failure."""
    if not body:
        return None
    try:
        data = json_mod.loads(body)
        if isinstance(data, dict):
            return data
        return None
    except (json_mod.JSONDecodeError, TypeError):
        return None


# -----------------------------------------------------------------------
# Content type extraction
# -----------------------------------------------------------------------


def _extract_content_type(resp: dict[str, Any]) -> str:
    """Extract Content-Type from response, lowercase."""
    resp_hdrs = lower_headers(resp)
    ct = resp_hdrs.get("content-type", "")
    # Also check content object
    if not ct:
        ct = resp.get("content", {}).get("mimeType", "")
    return ct.lower().split(";")[0].strip()
