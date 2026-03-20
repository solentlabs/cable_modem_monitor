"""HTML content extraction for format detection.

Detects tables and label-value pairs from HTML page bodies.
Used by format.http during Phase 5 page analysis.

Table detection uses BeautifulSoup for reliable nested HTML parsing.
Cells that contain nested ``<table>`` elements are treated as layout
wrappers, not data cells — consistent with the parser-side table
selector in ``parsers.table_selector``.

Label-value pair detection uses regex (no nesting issues).
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from .types import DetectedLabelPair, DetectedTable

# -----------------------------------------------------------------------
# Regex patterns (label-value pairs and preceding text)
# -----------------------------------------------------------------------

_TAG_STRIP = re.compile(r"<[^>]+>")

_LABEL_VALUE_PATTERN = re.compile(
    r"<t[dh][^>]*>\s*([^<]+?)\s*:?\s*</t[dh]>\s*<t[dh][^>]*>\s*([^<]+?)\s*</t[dh]>",
    re.IGNORECASE,
)

_ID_VALUE_PATTERN = re.compile(
    r'<[^>]+id\s*=\s*["\']([^"\']+)["\'][^>]*>([^<]*)</[^>]+>',
    re.IGNORECASE,
)


# -----------------------------------------------------------------------
# Table detection (BeautifulSoup)
# -----------------------------------------------------------------------


def _get_direct_rows(table: Tag) -> list[Tag]:
    """Get direct child ``<tr>`` elements, including those in ``<tbody>``.

    Only returns rows that are direct children of the table or its
    ``<thead>``/``<tbody>``/``<tfoot>`` sections — not rows from
    nested tables.
    """
    rows: list[Tag] = []
    for child in table.children:
        if isinstance(child, Tag):
            if child.name == "tr":
                rows.append(child)
            elif child.name in ("thead", "tbody", "tfoot"):
                rows.extend(r for r in child.children if isinstance(r, Tag) and r.name == "tr")
    return rows


def _is_data_table(table: Tag) -> bool:
    """Check if a table element is a data table, not a layout wrapper.

    A data table must have:
    1. At least 2 direct rows — title/decoration tables typically have
       a single row. Channel data tables always have a header row plus
       one or more data rows.
    2. No direct cells containing nested tables — if any of the table's
       own cells are wrappers, the table is a layout container, not a
       data table.

    Consistent with ``parsers.table_selector`` wrapper-cell filtering.
    """
    direct_rows = _get_direct_rows(table)

    if len(direct_rows) < 2:
        return False

    # If any direct cell contains a nested table, this is a layout wrapper
    for row in direct_rows:
        for cell in row.find_all(["td", "th"], recursive=False):
            if cell.find("table") is not None:
                return False

    return True


def _extract_rows(table: Tag) -> list[list[str]]:
    """Extract text content from direct table rows.

    Only processes direct child rows (not rows from nested tables)
    and leaf cells (cells without nested tables).
    Returns a list of rows, each row a list of cell text strings.
    """
    all_rows: list[list[str]] = []

    for row in _get_direct_rows(table):
        cells = row.find_all(["td", "th"], recursive=False)
        if not cells:
            continue

        leaf_texts: list[str] = []
        for cell in cells:
            leaf_texts.append(cell.get_text(strip=True))

        if any(t for t in leaf_texts):
            all_rows.append(leaf_texts)

    return all_rows


def _extract_table_id(table: Tag) -> str:
    """Extract the id attribute from a table element."""
    table_id = table.get("id", "")
    return str(table_id) if table_id else ""


def _extract_css_class(table: Tag) -> str:
    """Extract the class attribute from a table element."""
    classes = table.get("class")
    if isinstance(classes, list):
        return " ".join(str(c) for c in classes)
    return str(classes) if classes else ""


def _extract_title_row(table: Tag) -> str:
    """Extract title row text from th with colspan."""
    for th in table.find_all("th"):
        colspan = th.get("colspan")
        if colspan:
            text = str(th.get_text(strip=True))
            if text:
                return text
    return ""


def _extract_preceding_text(table: Tag) -> str:
    """Extract the nearest heading or title text before a table.

    Walks outward through the DOM to find title text associated with
    the table. Handles multiple patterns:

    1. Direct previous sibling heading/bold (``<h2>Title</h2><table>``)
    2. Title inside a sibling element (Netgear: ``<b>Title</b>`` in
       adjacent ``<tr>``)
    3. Title in a sibling row of a wrapper table (Motorola: title table
       and data table are both inside an outer wrapper ``<table>``)

    Walks up through ``<td>`` → ``<tr>`` → parent containers to find
    the title, checking siblings at each level.
    """
    # Walk up the DOM — at each level, check previous siblings
    current: Tag | None = table
    for _ in range(6):  # max depth to prevent runaway
        if current is None:
            break

        # Check previous siblings at this level
        text = _search_previous_siblings(current)
        if text:
            return text

        # Move up one level
        current = current.parent if isinstance(current.parent, Tag) else None

    return ""


def _search_previous_siblings(element: Tag) -> str:
    """Search previous siblings of an element for title text."""
    for sibling in element.previous_siblings:
        if not isinstance(sibling, Tag):
            continue

        # Direct heading or bold text
        text = _find_heading_text(sibling)
        if text:
            return text

        # Check inside the sibling (e.g., a title table or wrapper row)
        for child in sibling.descendants:
            if isinstance(child, Tag):
                text = _find_heading_text(child)
                if text:
                    return text

    return ""


def _find_heading_text(element: Tag) -> str:
    """Extract heading text from an element if it looks like a title."""
    tag = element.name
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "b", "strong"):
        text = str(element.get_text(strip=True))
        if text and len(text) < 100:
            return text

    # Title-class td elements (e.g., moto-param-title)
    if tag == "td":
        raw_class = element.get("class")
        css_class = " ".join(str(c) for c in raw_class) if isinstance(raw_class, list) else str(raw_class or "")
        if "title" in css_class.lower():
            text = str(element.get_text(strip=True))
            if text and len(text) < 100:
                return text

    return ""


def detect_tables(body: str) -> list[DetectedTable]:
    """Detect HTML tables in a page body.

    Uses BeautifulSoup for reliable nested HTML parsing. Layout
    and wrapper tables (cells containing nested tables) are filtered
    out — only data tables with leaf cells are returned.

    Consistent with the parser-side table selector in
    ``parsers.table_selector`` which applies the same wrapper-cell
    filtering.
    """
    soup = BeautifulSoup(body, "html.parser")
    tables: list[DetectedTable] = []

    for idx, table_el in enumerate(soup.find_all("table")):
        if not isinstance(table_el, Tag):
            continue

        if not _is_data_table(table_el):
            continue

        all_rows = _extract_rows(table_el)
        if not all_rows:
            continue

        tables.append(
            DetectedTable(
                table_id=_extract_table_id(table_el),
                css_class=_extract_css_class(table_el),
                headers=all_rows[0],
                rows=all_rows[1:] if len(all_rows) > 1 else [],
                preceding_text=_extract_preceding_text(table_el),
                title_row_text=_extract_title_row(table_el),
                table_index=idx,
            )
        )

    return tables


# -----------------------------------------------------------------------
# Label-value pair detection (regex — no nesting issues)
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
