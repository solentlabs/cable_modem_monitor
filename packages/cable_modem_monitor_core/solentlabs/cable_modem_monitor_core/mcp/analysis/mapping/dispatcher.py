"""Phase 6 - Field mapping extraction for channel sections.

Dispatches to format-specific extraction handlers and delegates
field resolution, channel type detection, and filter detection
to specialized modules.

Per docs/ONBOARDING_SPEC.md Phase 6 and docs/FIELD_REGISTRY.md.
"""

from __future__ import annotations

from typing import Any

from ..format.table_analysis import is_data_row
from ..format.types import DetectedJsFunction, DetectedTable
from .channel_detection import (
    detect_channel_type_fixed,
    detect_channel_type_json,
    detect_channel_type_table,
    detect_channel_type_transposed,
)
from .field_resolution import (
    detect_field_type,
    match_header_to_field,
    match_json_key_to_field,
)
from .filter_detection import detect_filter_table
from .types import FieldMapping, SectionDetail

# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------


def extract_section_mappings(
    fmt: str,
    resource: str = "",
    direction: str = "",
    table: DetectedTable | None = None,
    js_function: DetectedJsFunction | None = None,
    json_data: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> SectionDetail | None:
    """Extract field mappings for a channel section.

    Dispatches to format-specific extraction based on ``fmt``.
    Returns None if no recognizable fields are found.
    """
    if warnings is None:
        warnings = []

    if fmt == "table" and table is not None:
        return _extract_table_mappings(table, resource, direction, warnings)

    if fmt == "table_transposed" and table is not None:
        return _extract_transposed_mappings(table, resource, direction, warnings)

    if fmt == "javascript" and js_function is not None:
        return _extract_js_mappings(js_function, resource, direction, warnings)

    if fmt == "json" and json_data is not None:
        return _extract_json_mappings(json_data, resource, direction, warnings)

    return None


# -----------------------------------------------------------------------
# Table format (standard)
# -----------------------------------------------------------------------


def _extract_table_mappings(
    table: DetectedTable,
    resource: str,
    direction: str,
    warnings: list[str],
) -> SectionDetail | None:
    """Extract column index -> field mappings from a standard table."""
    mappings: list[FieldMapping] = []

    for idx, header in enumerate(table.headers):
        field_name, tier, header_unit = match_header_to_field(header)
        if not field_name:
            continue

        # Detect type and unit from data values; header unit takes priority
        sample_values = [row[idx] for row in table.rows if idx < len(row)]
        field_type, unit = detect_field_type(field_name, sample_values, header_unit)

        mappings.append(
            FieldMapping(
                field=field_name,
                type=field_type,
                tier=tier,
                unit=unit,
                index=idx,
            )
        )

    if not mappings:
        return None

    # Remove row counter columns (sequential 1..N matching row count)
    mappings = _remove_row_counters(mappings, table)

    # Detect channel type and filter
    channel_type = detect_channel_type_table(table, mappings, direction)
    row_filter = detect_filter_table(table, mappings)
    channel_count = _count_data_rows(table)

    return SectionDetail(
        format="table",
        resource=resource,
        mappings=mappings,
        channel_type=channel_type,
        filter=row_filter,
        channel_count=channel_count,
    )


# -----------------------------------------------------------------------
# Table transposed format
# -----------------------------------------------------------------------


def _extract_transposed_mappings(
    table: DetectedTable,
    resource: str,
    direction: str,
    warnings: list[str],
) -> SectionDetail | None:
    """Extract row label -> field mappings from a transposed table."""
    mappings: list[FieldMapping] = []

    for row in table.rows:
        if not row:
            continue

        label = row[0]
        field_name, tier, header_unit = match_header_to_field(label)
        if not field_name:
            continue

        # Sample values from the data columns
        sample_values = row[1:] if len(row) > 1 else []
        field_type, unit = detect_field_type(field_name, sample_values, header_unit)

        mappings.append(
            FieldMapping(
                field=field_name,
                type=field_type,
                tier=tier,
                label=label.strip(),
            )
        )

    if not mappings:
        return None

    # Channel count from number of data columns
    channel_count = 0
    for row in table.rows:
        if len(row) > 1:
            channel_count = max(channel_count, len(row) - 1)
            break

    channel_type = detect_channel_type_transposed(table, mappings, direction)

    return SectionDetail(
        format="table_transposed",
        resource=resource,
        mappings=mappings,
        channel_type=channel_type,
        channel_count=channel_count,
    )


# -----------------------------------------------------------------------
# JavaScript format
# -----------------------------------------------------------------------


def _extract_js_mappings(
    js_func: DetectedJsFunction,
    resource: str,
    direction: str,
    warnings: list[str],
) -> SectionDetail | None:
    """Extract offset -> field mappings from JS delimited data."""
    values = js_func.values
    if not values:
        return None

    # First value is typically the channel count
    try:
        record_count = int(values[0])
    except (ValueError, IndexError):
        record_count = 0

    if record_count <= 0:
        return None

    # Calculate fields per record
    data_values = values[1:]
    if not data_values:
        return None

    fields_per_record = len(data_values) // record_count if record_count else 0
    if fields_per_record <= 0:
        return None

    # Extract first record as sample
    first_record = data_values[:fields_per_record]

    # Map offsets to fields by examining sample values
    mappings: list[FieldMapping] = []
    for offset, value in enumerate(first_record):
        field_name, tier = _infer_field_from_value(value, offset, direction)
        if not field_name:
            continue

        field_type, unit = detect_field_type(field_name, [value])
        mappings.append(
            FieldMapping(
                field=field_name,
                type=field_type,
                tier=tier,
                unit=unit,
                offset=offset,
            )
        )

    if not mappings:
        return None

    channel_type = detect_channel_type_fixed(direction)

    return SectionDetail(
        format="javascript",
        resource=resource,
        mappings=mappings,
        function_name=js_func.name,
        delimiter=js_func.delimiter,
        fields_per_record=fields_per_record,
        channel_type=channel_type,
        channel_count=record_count,
    )


# -----------------------------------------------------------------------
# JSON format
# -----------------------------------------------------------------------


def _extract_json_mappings(
    json_data: dict[str, Any],
    resource: str,
    direction: str,
    warnings: list[str],
) -> SectionDetail | None:
    """Extract JSON key -> field mappings from a JSON response."""
    # Find the channel array
    array_path, channel_array = _find_channel_array(json_data)
    if not channel_array:
        return None

    # Use first item as sample
    sample = channel_array[0]
    if not isinstance(sample, dict):
        return None

    mappings: list[FieldMapping] = []
    for key, value in sample.items():
        field_name, tier = match_json_key_to_field(key)
        if not field_name:
            continue

        field_type, unit = detect_field_type(field_name, [str(value)] if value is not None else [])
        mappings.append(
            FieldMapping(
                field=field_name,
                type=field_type,
                tier=tier,
                key=key,
            )
        )

    if not mappings:
        return None

    channel_type = detect_channel_type_json(channel_array)

    return SectionDetail(
        format="json",
        resource=resource,
        mappings=mappings,
        array_path=array_path,
        channel_type=channel_type,
        channel_count=len(channel_array),
    )


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _find_channel_array(data: dict[str, Any], prefix: str = "") -> tuple[str, list[dict[str, Any]]]:
    """Find a channel array in JSON data using dot-notation path.

    Walks the JSON structure looking for a list of dicts.
    Returns (dot_path, array) or ("", []).
    """
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return path, value
        if isinstance(value, dict):
            result = _find_channel_array(value, path)
            if result[1]:
                return result
    return "", []


def _count_data_rows(table: DetectedTable) -> int:
    """Count data rows in a table (excluding empty/dash rows)."""
    return sum(1 for row in table.rows if is_data_row(row))


def _remove_row_counters(
    mappings: list[FieldMapping],
    table: DetectedTable,
) -> list[FieldMapping]:
    """Remove row counter columns from mappings.

    A row counter column has values that are sequential integers
    1, 2, 3, ..., N matching the data row count. Only removed when
    another column maps to the same field name (otherwise it may be
    the real data).

    Evidence: across the modem landscape, real DOCSIS channel IDs are
    never perfectly sequential from 1. Row counters always are.
    """
    # Find fields that appear more than once
    field_counts: dict[str, int] = {}
    for m in mappings:
        field_counts[m.field] = field_counts.get(m.field, 0) + 1

    duplicated_fields = {f for f, count in field_counts.items() if count > 1}
    if not duplicated_fields:
        return mappings

    # Count data rows
    data_rows = [row for row in table.rows if is_data_row(row)]
    row_count = len(data_rows)
    if row_count == 0:
        return mappings

    # Check each mapping in a duplicated field for row-counter pattern
    keep: list[FieldMapping] = []
    for m in mappings:
        if m.field in duplicated_fields and m.index is not None and _is_row_counter(m.index, data_rows, row_count):
            continue
        keep.append(m)

    return keep


def _is_row_counter(
    col_index: int,
    data_rows: list[list[str]],
    row_count: int,
) -> bool:
    """Check if a column contains sequential 1..N values.

    Allows trailing non-integer rows (e.g., "Total" summary rows).
    Returns True when all integer-parseable values form a perfect
    1..K sequence and K covers most of the data rows.
    """
    sequential_count = 0
    for row_num, row in enumerate(data_rows, start=1):
        if col_index >= len(row):
            return False
        value = row[col_index].strip()
        try:
            if int(value) != row_num:
                return False
            sequential_count = row_num
        except ValueError:
            # Non-integer value — allow only after sequential portion
            # (summary rows like "Total" at the bottom)
            break

    # Must have at least 2 sequential rows covering most of the data
    return sequential_count >= 2 and sequential_count >= row_count - 1


def _infer_field_from_value(value: str, offset: int, direction: str) -> tuple[str, int]:
    """Infer field name from a JS value at a given offset.

    This is a heuristic for JS-embedded data where there are no headers.
    Returns (field_name, tier) or ("", 0).
    """
    stripped = value.strip()
    if not stripped:
        return "", 0

    # Lock status values
    if stripped.lower() in ("locked", "not locked", "unlocked"):
        return "lock_status", 1

    # Modulation values
    if stripped.upper().startswith("QAM") or stripped.upper().startswith("OFDM"):
        return "modulation", 1

    # Channel type values
    if stripped.lower() in ("sc-qam", "ofdm", "atdma", "ofdma"):
        return "channel_type", 1

    # Numeric: try to distinguish frequency vs power vs channel_id
    try:
        num = float(stripped.split()[0])
        if num > 1_000_000:
            return "frequency", 1
        if 0 < num < 200 and abs(num) == int(abs(num)):
            # Small integer could be channel_id
            return "", 0
        return "", 0
    except ValueError:
        pass

    return "", 0
