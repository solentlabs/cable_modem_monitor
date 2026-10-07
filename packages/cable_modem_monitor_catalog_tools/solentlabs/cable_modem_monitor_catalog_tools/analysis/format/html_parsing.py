"""HTML content extraction for format detection.

Detects tables and label-value pairs from HTML page bodies.
Used by format.http during Phase 5 page analysis.

Table detection uses BeautifulSoup for reliable nested HTML parsing.
Cells that contain nested ``<table>`` elements are treated as layout
wrappers, not data cells — consistent with the parser-side table
selector in ``parsers.table_selector``.

Table-row label pairs are kept only when Core's label lookup reads the
same value; id and inline "Label: Value<BR>" pairs use regex.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag
from solentlabs.cable_modem_monitor_core.loaders.html_normalize import normalize_html
from solentlabs.cable_modem_monitor_core.parsers import extract_by_label

from .types import DetectedLabelPair, DetectedTable

# -----------------------------------------------------------------------
# Regex patterns (label-value pairs and preceding text)
# -----------------------------------------------------------------------

# Some modem firmware emits malformed table HTML where column header
# <td> cells appear *after* the title row's </tr> close tag, without a
# wrapping <tr>.  html.parser silently drops these orphaned cells and
# treats the first real data row as the header row, producing field
# names like "locked", "qam256", "237000000_hz".  The pattern is:
#
#   <tr><th colspan=N>Title</th></tr>
#         <td><strong>Header1</strong></td>   ← no enclosing <tr>
#         <td><strong>Header2</strong></td>
#      </tr>                                  ← rogue </tr>
#   <tr>...</tr>                              ← first data row
#
# Fix: insert the missing <tr> before orphaned <td> cells so html.parser
# receives valid HTML.  The pattern only fires when <td> appears
# immediately after </tr> (never valid in well-formed HTML), so it
# cannot silently corrupt correct tables.  The inserted row is marked:
# Core's parser does no such repair and drops the orphaned cells, so it
# is not a row row_start may count.
_ORPHANED_TD_RE = re.compile(
    r"(</tr>)((?:\s*<td\b[^>]*>.*?</td>)+\s*)(</tr>)",
    re.DOTALL | re.IGNORECASE,
)

# Some modem firmware emits malformed transposed-table HTML where each
# row's label <th> is closed with </td> instead of </th>:
#
#   <th class="row-label">Channel ID</td>
#   <td>17</td><td>1</td>...
#
# html.parser (via BS4) nests the following <td> elements inside the
# unclosed <th>, so recursive=False on the row returns 1 cell with all
# values concatenated in its text. Fix: replace </td> with </th> when it
# appears as the only closing tag inside a <th> that has no nested tags.
# The pattern only fires on <th>text</td> (never valid HTML), so it
# cannot silently corrupt well-formed tables.
_REPAIRED_ROW_ATTR = "data-cmm-repaired"

_UNCLOSED_TH_RE = re.compile(
    r"(<th\b[^>]*>)([^<]*)(</td>)",
    re.IGNORECASE,
)

# Inline "Label: Value<BR>" pattern — some modems embed system info
# as BR-delimited text inside a single <TD> cell (e.g., SB6141 cmHelpData.htm).
_BR_LABEL_VALUE_PATTERN = re.compile(
    r"([A-Z][A-Za-z ]+?)\s*:\s*([^\n<]+?)\s*<[Bb][Rr]\s*/?>",
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
                rows.extend(_flatten_row(child))
            elif child.name in ("thead", "tbody", "tfoot"):
                for r in child.children:
                    if isinstance(r, Tag) and r.name == "tr":
                        rows.extend(_flatten_row(r))
    return rows


def _flatten_row(row: Tag) -> list[Tag]:
    """Return the row plus any rows html.parser nested directly inside it."""
    # Firmware that omits </tr> leaves each data row unclosed, and html.parser
    # nests the next <tr> inside it. A <tr> directly inside a <tr> is never
    # valid HTML, so this only unwinds that chain; rows of a table nested in
    # a cell sit under <td>, not <tr>, and stay excluded.
    rows = [row]
    for child in row.children:
        if isinstance(child, Tag) and child.name == "tr":
            rows.extend(_flatten_row(child))
    return rows


def _is_data_table(table: Tag) -> bool:
    """Check if a table element is a data table, not a layout wrapper.

    A data table must have:
    1. At least 2 direct rows — title/decoration tables typically have
       a single row. Channel data tables always have a header row plus
       one or more data rows.
    2. Not primarily a layout wrapper — if many cells contain nested
       tables, the table is a layout container. A single cosmetic
       nested table (e.g., an explanatory note inside a Power Level
       cell) does not disqualify the table.

    Consistent with ``parsers.table_selector`` wrapper-cell filtering.
    """
    direct_rows = _get_direct_rows(table)

    if len(direct_rows) < 2:
        return False

    # Count cells with nested tables vs total cells.  A layout wrapper
    # has most cells containing sub-tables.  A data table may have one
    # cosmetic nested table (e.g., explanatory text in a <small> helper).
    total_cells = 0
    nested_cells = 0
    for row in direct_rows:
        for cell in row.find_all(["td", "th"], recursive=False):
            total_cells += 1
            if cell.find("table") is not None:
                nested_cells += 1

    if total_cells == 0:
        return False

    # Reject if more than 25% of cells contain nested tables
    return not (nested_cells > 0 and nested_cells / total_cells > 0.25)


def _own_text(cell: Tag) -> str:
    """The cell's text without any table nested in it (ONBOARDING_SPEC § Table cell text)."""
    if cell.find("table") is None:
        return str(cell.get_text(strip=True))
    return "".join(str(s) for s in cell.find_all(string=True, recursive=False)).strip()


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
        for position, cell in enumerate(cells):
            # The label cell alone drops nested help text; values are read as Core reads them.
            text = _own_text(cell) if position == 0 else cell.get_text(strip=True)
            if not text:
                # Fallback: i18n attributes contain semantic header labels
                # when the visible text is injected by JavaScript at runtime.
                i18n_key = cell.get("data-i18n", "")
                if i18n_key:
                    text = str(i18n_key)
            leaf_texts.append(text)

        if any(t for t in leaf_texts):
            all_rows.append(leaf_texts)

    return all_rows


def _repaired_label_rows(table: Tag, headers: list[str]) -> int:
    """1 when the label row is one the analyzer repaired in; repairs among data rows never shift row_start."""
    for row in table.find_all("tr", attrs={_REPAIRED_ROW_ATTR: True}):
        if [cell.get_text(strip=True) for cell in row.find_all(["td", "th"], recursive=False)] == headers:
            return 1
    return 0


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
    """Extract title row text from th with colspan.

    Falls back to ``data-i18n`` attribute when visible text is empty
    (common on i18n pages where JavaScript injects labels at runtime).
    """
    for th in table.find_all("th"):
        colspan = th.get("colspan")
        if colspan:
            text = str(th.get_text(strip=True))
            if not text:
                i18n_key = th.get("data-i18n", "")
                if i18n_key:
                    text = str(i18n_key)
            if text:
                return text
    return ""


def _extract_preceding_text(table: Tag) -> str:
    """Extract the nearest heading or title text before a table.

    Walks outward through the DOM to find title text associated with
    the table. Handles multiple patterns:

    1. Direct previous sibling heading/bold (``<h2>Title</h2><table>``)
    2. Title inside a sibling element (``<b>Title</b>`` in adjacent
       ``<tr>``)
    3. Title in a sibling row of a wrapper table (title table and data
       table are both inside an outer wrapper ``<table>``)

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


def _extract_i18n_header_map(table: Tag) -> dict[str, str]:
    """Map data-i18n keys to tag names for header cells with empty text.

    Returns a dict of ``{i18n_key: tag_name}`` for every cell in the
    first direct row whose visible text is empty but whose
    ``data-i18n`` attribute supplies a semantic label.  Used by
    ``detect_table_selector`` to generate a CSS attribute selector
    instead of a ``header_text`` match that would never find the
    table at runtime (because the actual text is injected by
    JavaScript and is absent in the HAR capture).
    """
    i18n_map: dict[str, str] = {}
    direct_rows = _get_direct_rows(table)
    if not direct_rows:
        return i18n_map
    first_row = direct_rows[0]
    for cell in first_row.find_all(["td", "th"], recursive=False):
        if not isinstance(cell, Tag):
            continue
        text = cell.get_text(strip=True)
        if not text:
            i18n_key = cell.get("data-i18n", "")
            if i18n_key:
                i18n_map[str(i18n_key)] = str(cell.name)
    return i18n_map


def detect_tables(body: str) -> list[DetectedTable]:
    """Detect HTML tables in a page body.

    Uses BeautifulSoup for reliable nested HTML parsing. Layout
    and wrapper tables (cells containing nested tables) are filtered
    out — only data tables with leaf cells are returned.

    Consistent with the parser-side table selector in
    ``parsers.table_selector`` which applies the same wrapper-cell
    filtering.
    """
    body = _ORPHANED_TD_RE.sub(rf"\1<tr {_REPAIRED_ROW_ATTR}>\2\3", body)
    body = _UNCLOSED_TH_RE.sub(r"\1\2</th>", body)
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

        title_row_text = _extract_title_row(table_el)

        # When a th-colspan title row is the first extracted row,
        # skip it — the real column headers are in the next row.
        headers = all_rows[0]
        data_rows = all_rows[1:] if len(all_rows) > 1 else []
        if title_row_text and len(all_rows) > 1 and len(all_rows[0]) == 1 and all_rows[0][0] == title_row_text:
            headers = all_rows[1]
            data_rows = all_rows[2:] if len(all_rows) > 2 else []

        tables.append(
            DetectedTable(
                table_id=_extract_table_id(table_el),
                css_class=_extract_css_class(table_el),
                headers=headers,
                rows=data_rows,
                preceding_text=_extract_preceding_text(table_el),
                title_row_text=title_row_text,
                table_index=idx,
                repaired_rows=_repaired_label_rows(table_el, headers),
                i18n_header_map=_extract_i18n_header_map(table_el),
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

    # Strategy 1: table rows, first cell the label, second the value
    for label, value in _confirmed_row_pairs(body):
        if label.lower() not in seen_labels:
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

    # Strategy 3: Inline "Label: Value<BR>" inside a single cell
    for match in _BR_LABEL_VALUE_PATTERN.finditer(body):
        label = match.group(1).strip()
        value = match.group(2).strip()
        if label and value and label.lower() not in seen_labels:
            seen_labels.add(label.lower())
            pairs.append(
                DetectedLabelPair(
                    label=label,
                    value=value,
                    selector_type="css_pattern",
                    selector_value=label,
                    element_id="",
                )
            )

    return pairs


# Mirrors Core's private _BLOCK_LEVEL_TAGS in parsers.formats.html_fields:
# a cell holding one of these is a layout wrapper, not a label or value.
_BLOCK_LEVEL_TAGS = ["table", "div", "section", "article", "ul", "ol", "dl"]


def _confirmed_row_pairs(body: str) -> list[tuple[str, str]]:
    """Return (label, value) from table rows that Core's label lookup reads back."""
    # Same parse as Core's loader, so the confirmation sees the runtime DOM.
    soup = BeautifulSoup(normalize_html(body), "html.parser")
    pairs: list[tuple[str, str]] = []
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 2 or cells[0].find(_BLOCK_LEVEL_TAGS) or cells[1].find(_BLOCK_LEVEL_TAGS):
            continue
        label = cells[0].get_text().strip().rstrip(":").strip()
        value = cells[1].get_text().strip()
        if not label or not value:
            continue
        # Core matches labels by substring, so a row whose label also sits
        # inside an earlier cell (channel tables of numbers) reads that
        # cell's neighbour instead; such a row is not a label pair.
        core_value = extract_by_label(soup, label)
        if core_value is not None and core_value.strip() == value:
            pairs.append((label, value))
    return pairs
