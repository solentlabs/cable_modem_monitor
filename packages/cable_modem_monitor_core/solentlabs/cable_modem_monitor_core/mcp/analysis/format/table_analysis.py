"""Table analysis for format classification and section assembly.

Direction detection, selector detection, row start detection, and
table orientation (standard vs transposed). Used by format.http
for format classification and by the format dispatcher for section
assembly.

Per docs/ONBOARDING_SPEC.md Phase 5.
"""

from __future__ import annotations

from ..mapping.registry_loader import get_channel_field_labels
from .types import DetectedTable

# -----------------------------------------------------------------------
# Channel field labels (derived from field_registry.json)
# -----------------------------------------------------------------------

CHANNEL_FIELD_LABELS: tuple[str, ...] = get_channel_field_labels()


# -----------------------------------------------------------------------
# Table classification
# -----------------------------------------------------------------------


def is_channel_table(table: DetectedTable) -> bool:
    """Check if a table contains channel data based on headers/labels."""
    for header in table.headers:
        if header.lower().strip() in CHANNEL_FIELD_LABELS:
            return True

    # For transposed: check first column of data rows
    return any(row and row[0].lower().strip() in CHANNEL_FIELD_LABELS for row in table.rows)


def is_transposed(table: DetectedTable) -> bool:
    """Determine if a table is transposed (rows=metrics, cols=channels).

    If the first column of data rows contains
    known field labels, it is transposed.
    """
    label_count = 0
    for row in table.rows:
        if row and row[0].lower().strip() in CHANNEL_FIELD_LABELS:
            label_count += 1

    # If most data rows have field labels in the first column, transposed
    return bool(table.rows and label_count >= len(table.rows) * 0.5)


# -----------------------------------------------------------------------
# Table direction detection
# -----------------------------------------------------------------------


def detect_table_direction(table: DetectedTable) -> str:
    """Detect whether a table is downstream or upstream.

    Three-strategy cascade:
    1. Title row (th colspan) containing keyword
    2. Preceding heading/text containing keyword
    3. First cell in first row containing keyword

    Returns "downstream", "upstream", or "unknown".
    """
    # Strategy 1: title row
    if table.title_row_text:
        direction = _keyword_match(table.title_row_text)
        if direction:
            return direction

    # Strategy 2: preceding heading
    if table.preceding_text:
        direction = _keyword_match(table.preceding_text)
        if direction:
            return direction

    # Secondary: table id attribute
    if table.table_id:
        direction = _keyword_match_id(table.table_id)
        if direction:
            return direction

    # Strategy 3: first cell of first row
    if table.headers:
        direction = _keyword_match(table.headers[0])
        if direction:
            return direction

    return "unknown"


def _keyword_match(text: str) -> str:
    """Match downstream/upstream keywords in text."""
    lower = text.lower()
    if "downstream" in lower:
        return "downstream"
    if "upstream" in lower:
        return "upstream"
    return ""


def _keyword_match_id(table_id: str) -> str:
    """Match downstream/upstream from table id attributes."""
    lower = table_id.lower()
    if lower.startswith("ds") or "downstream" in lower:
        return "downstream"
    if lower.startswith("us") or "upstream" in lower:
        return "upstream"
    return ""


# -----------------------------------------------------------------------
# Table selector detection
# -----------------------------------------------------------------------


def detect_table_selector(
    table: DetectedTable,
    all_tables: list[DetectedTable] | None = None,
) -> dict[str, str]:
    """Choose the best selector for a table.

    Priority: id > title_row_text > unique_column_header >
    preceding_text > css > nth.

    When ``all_tables`` is provided, a unique column header is one
    that appears in this table but not in any other table on the page.
    Headers from the field registry are preferred as discriminators.
    """
    if table.table_id:
        return {"type": "id", "match": table.table_id}

    if table.title_row_text:
        return {"type": "header_text", "match": table.title_row_text}

    # Unique column header (requires knowing sibling tables)
    if all_tables is not None:
        unique = _find_unique_column_header(table, all_tables)
        if unique:
            return {"type": "header_text", "match": unique}

    if table.preceding_text:
        return {"type": "header_text", "match": table.preceding_text}

    if table.css_class:
        return {"type": "css", "match": f"table.{table.css_class.split()[0]}"}

    return {"type": "nth", "match": str(table.table_index)}


def _find_unique_column_header(
    table: DetectedTable,
    all_tables: list[DetectedTable],
) -> str:
    """Find a column header unique to this table among all page tables.

    Prefers headers that are known channel field labels (from the
    registry) over arbitrary text. Returns empty string if no unique
    header is found.
    """
    my_headers = {h.strip() for h in table.headers if h.strip()}
    if not my_headers:
        return ""

    # Collect headers from all other tables
    other_headers: set[str] = set()
    for other in all_tables:
        if other is table:
            continue
        other_headers.update(h.strip() for h in other.headers if h.strip())

    unique = my_headers - other_headers
    if not unique:
        return ""

    # Prefer known field labels as discriminators, sorted for determinism
    for header in sorted(unique):
        if header.lower() in CHANNEL_FIELD_LABELS:
            return header

    # Fall back to first unique header (deterministic via sort)
    return sorted(unique)[0]


# -----------------------------------------------------------------------
# Row start detection
# -----------------------------------------------------------------------


def detect_row_start(table: DetectedTable) -> int:
    """Detect where data rows begin.

    Returns the row index (0-based from full table including headers)
    where actual data starts. The header row counts as row 0.
    """
    # Row 0 is the header row itself. Data rows start at index 1+
    # but some tables have a title row first, then headers.
    # We count from the start of all_rows (headers + data).

    # Check if the header row is actually a title row (single cell)
    skip = 1  # At least skip the header row

    if table.title_row_text:
        # Title row + header row = skip 2
        skip = 2

    # Check for additional non-data rows at the top of data_rows
    for row in table.rows:
        if is_data_row(row):
            break
        skip += 1

    return skip


def is_data_row(row: list[str]) -> bool:
    """Check if a row contains actual data (not headers/empty/dashes)."""
    if not row:
        return False

    # All empty
    if all(not cell.strip() for cell in row):
        return False

    # All dashes
    if all(cell.strip() in ("-", "--", "---", "N/A", "n/a") for cell in row):
        return False

    # At least one cell with a numeric-looking value
    for cell in row:
        stripped = cell.strip()
        if not stripped:
            continue
        # Try to parse as number (with possible unit suffix)
        num_part = stripped.split()[0] if " " in stripped else stripped
        try:
            float(num_part)
            return True
        except ValueError:
            continue

    # Non-empty non-numeric row — could still be data (string values)
    # If the first cell matches a field label, it is a header/label row
    return row[0].lower().strip() not in CHANNEL_FIELD_LABELS
