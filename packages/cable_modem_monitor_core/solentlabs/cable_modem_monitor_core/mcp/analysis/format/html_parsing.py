"""HTML content extraction for format detection.

Detects tables and label-value pairs from HTML page bodies.
Used by format.http during Phase 5 page analysis.
"""

from __future__ import annotations

import re

from .types import DetectedLabelPair, DetectedTable

# -----------------------------------------------------------------------
# Regex patterns for table extraction
# -----------------------------------------------------------------------

_TABLE_PATTERN = re.compile(r"<table[^>]*>(.*?)</table>", re.DOTALL | re.IGNORECASE)
_TABLE_ID_PATTERN = re.compile(r'id\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_TABLE_CLASS_PATTERN = re.compile(r'class\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_ROW_PATTERN = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_CELL_PATTERN = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
_TH_COLSPAN_PATTERN = re.compile(
    r'<th[^>]*colspan\s*=\s*["\']?\d+["\']?[^>]*>(.*?)</th>',
    re.DOTALL | re.IGNORECASE,
)

_TAG_STRIP = re.compile(r"<[^>]+>")

_HEADING_PATTERN = re.compile(
    r"<(?:h[1-6]|b|strong|td)[^>]*>([^<]+)</(?:h[1-6]|b|strong|td)>",
    re.IGNORECASE,
)

# -----------------------------------------------------------------------
# Regex patterns for label-value pair extraction
# -----------------------------------------------------------------------

_LABEL_VALUE_PATTERN = re.compile(
    r"<t[dh][^>]*>\s*([^<]+?)\s*:?\s*</t[dh]>\s*<t[dh][^>]*>\s*([^<]+?)\s*</t[dh]>",
    re.IGNORECASE,
)

_ID_VALUE_PATTERN = re.compile(
    r'<[^>]+id\s*=\s*["\']([^"\']+)["\'][^>]*>([^<]*)</[^>]+>',
    re.IGNORECASE,
)


# -----------------------------------------------------------------------
# HTML utility functions
# -----------------------------------------------------------------------


def _strip_tags(html: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    return _TAG_STRIP.sub("", html).strip()


def _extract_table_attr(tag_opening: str, pattern: re.Pattern[str]) -> str:
    """Extract an attribute value from a table opening tag."""
    match = pattern.search(tag_opening)
    return match.group(1) if match else ""


def _extract_title_row(table_content: str) -> str:
    """Extract title row text from th with colspan."""
    for th_match in _TH_COLSPAN_PATTERN.finditer(table_content):
        title_text = _strip_tags(th_match.group(1))
        if title_text:
            return title_text
    return ""


def _extract_preceding_text(body: str, start_pos: int) -> str:
    """Extract the last heading text before a table."""
    search_region = body[max(0, start_pos - 500) : start_pos]
    heading_matches = list(_HEADING_PATTERN.finditer(search_region))
    if heading_matches:
        return heading_matches[-1].group(1).strip()
    return ""


# -----------------------------------------------------------------------
# Table detection
# -----------------------------------------------------------------------


def detect_tables(body: str) -> list[DetectedTable]:
    """Detect HTML tables in a page body."""
    tables: list[DetectedTable] = []

    for idx, table_match in enumerate(_TABLE_PATTERN.finditer(body)):
        table_html = table_match.group(0)
        table_content = table_match.group(1)
        tag_opening = table_html.split(">", 1)[0]

        # Extract rows
        rows_raw = _ROW_PATTERN.findall(table_content)
        if not rows_raw:
            continue

        all_rows: list[list[str]] = []
        for row_html in rows_raw:
            cells = [_strip_tags(c) for c in _CELL_PATTERN.findall(row_html)]
            if cells:
                all_rows.append(cells)

        if not all_rows:
            continue

        tables.append(
            DetectedTable(
                table_id=_extract_table_attr(tag_opening, _TABLE_ID_PATTERN),
                css_class=_extract_table_attr(tag_opening, _TABLE_CLASS_PATTERN),
                headers=all_rows[0],
                rows=all_rows[1:] if len(all_rows) > 1 else [],
                preceding_text=_extract_preceding_text(body, table_match.start()),
                title_row_text=_extract_title_row(table_content),
                table_index=idx,
            )
        )

    return tables


# -----------------------------------------------------------------------
# Label-value pair detection
# -----------------------------------------------------------------------


def detect_label_pairs(body: str) -> list[DetectedLabelPair]:
    """Detect label-value pairs in HTML content."""
    pairs: list[DetectedLabelPair] = []
    seen_labels: set[str] = set()

    # Strategy 1: Table cells with label: value pattern
    for match in _LABEL_VALUE_PATTERN.finditer(body):
        label = match.group(1).strip().rstrip(":")
        value = match.group(2).strip()
        if label and value and label.lower() not in seen_labels:
            seen_labels.add(label.lower())
            pairs.append(
                DetectedLabelPair(
                    label=label,
                    value=value,
                    selector_type="label",
                    selector_value=label,
                    element_id="",
                )
            )

    # Strategy 2: Elements with id attributes containing values
    for match in _ID_VALUE_PATTERN.finditer(body):
        elem_id = match.group(1)
        value = match.group(2).strip()
        if value and elem_id.lower() not in seen_labels:
            seen_labels.add(elem_id.lower())
            pairs.append(
                DetectedLabelPair(
                    label=elem_id,
                    value=value,
                    selector_type="id",
                    selector_value=elem_id,
                    element_id=elem_id,
                )
            )

    return pairs
