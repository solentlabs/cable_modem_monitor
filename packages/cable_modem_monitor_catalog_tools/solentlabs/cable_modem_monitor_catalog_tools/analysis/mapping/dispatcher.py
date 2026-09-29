"""Phase 6 - Field mapping extraction for channel sections.

Dispatches to format-specific extraction handlers and delegates
field resolution, channel type detection, and filter detection
to specialized modules.

Per docs/ONBOARDING_SPEC.md Phase 6 and docs/FIELD_REGISTRY.md.
"""

from __future__ import annotations

from typing import Any

from ...validation.har_utils import WARNING_PREFIX
from ..ambiguity import Candidate
from ..format.table_analysis import is_data_row
from ..format.types import DetectedJsFunction, DetectedTable
from ..types import FleetPatterns
from .channel_detection import (
    detect_channel_type_fixed,
    detect_channel_type_json,
    detect_channel_type_table,
    detect_channel_type_transposed,
)
from .channel_keys import key_candidates, learned_field
from .field_resolution import (
    detect_field_type,
    match_header_to_field,
    match_json_key_to_field,
)
from .filter_detection import detect_filter_table
from .symbol_rate import symbol_rate_unit_and_scale
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
    fleet: FleetPatterns | None = None,
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
        return _extract_js_mappings(js_function, resource, direction, warnings, fleet=fleet)

    if fmt == "json" and json_data is not None:
        return _extract_json_mappings(json_data, resource, direction, warnings, fleet=fleet)

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
        scale = None
        if field_name == "symbol_rate":
            unit, scale = symbol_rate_unit_and_scale(sample_values, unit, warnings)

        mappings.append(
            FieldMapping(
                field=field_name,
                type=field_type,
                tier=tier,
                unit=unit,
                index=idx,
                scale=scale,
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

    # When channel_type is expressed as an indexed column with a
    # normalization map, the raw channel_type FieldMapping is redundant —
    # _transform_table will emit the enriched version via the channel_type
    # section.  Remove it here to avoid a duplicate column in parser.yaml.
    if channel_type and "index" in channel_type:
        mappings = [m for m in mappings if m.field != "channel_type"]

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
        # Transposed rows emit no unit, except symbol_rate, which needs one
        # to strip a ksym suffix before scaling to Sym/s.
        row_unit, scale = "", None
        if field_name == "symbol_rate":
            row_unit, scale = symbol_rate_unit_and_scale(sample_values, unit, warnings)

        mappings.append(
            FieldMapping(
                field=field_name,
                type=field_type,
                tier=tier,
                unit=row_unit,
                label=label.strip(),
                scale=scale,
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
    fleet: FleetPatterns | None = None,
) -> SectionDetail | None:
    """Extract offset -> field mappings from JS delimited data.

    When a fleet layout is available for this function name, uses the
    proven field layout from committed configs instead of value-based
    inference — this handles numeric fields (channel_id, power, snr,
    corrected, uncorrected) that heuristic inference misses.
    """
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

    # Fleet-based layout: use proven field offsets from committed configs
    if fleet and js_func.name in fleet.js_function_layouts:
        return _extract_js_mappings_from_fleet(
            js_func, resource, direction, fleet.js_function_layouts[js_func.name], record_count, warnings
        )

    # Inference-based layout (fallback)
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
    _resolve_js_symbol_rate(mappings, data_values, fields_per_record, warnings)

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


def _extract_js_mappings_from_fleet(
    js_func: DetectedJsFunction,
    resource: str,
    direction: str,
    layout: dict[str, Any],
    record_count: int,
    warnings: list[str],
) -> SectionDetail | None:
    """Build JS section from a fleet-proven function layout.

    Uses committed field definitions (offsets, types, units) instead of
    value inference.  Channel count comes from the actual HAR data.
    """
    field_defs = layout.get("fields", [])
    if not field_defs:
        return None

    mappings = [
        FieldMapping(
            field=f["field"],
            type=f.get("type", "string"),
            tier=1,
            unit=f.get("unit", ""),
            offset=f["offset"],
        )
        for f in field_defs
        if isinstance(f, dict) and "field" in f and "offset" in f
    ]
    if not mappings:
        return None

    # The fleet proves positions, not units: resolve symbol_rate from this capture.
    _resolve_js_symbol_rate(mappings, js_func.values[1:], layout.get("fields_per_channel", 0), warnings)

    ct_value = layout.get("channel_type", "")
    channel_type: dict[str, Any] = {"fixed": ct_value} if ct_value else (detect_channel_type_fixed(direction) or {})

    return SectionDetail(
        format="javascript",
        resource=resource,
        mappings=mappings,
        function_name=js_func.name,
        delimiter=js_func.delimiter or layout.get("delimiter", "|"),
        fields_per_record=layout.get("fields_per_channel", 0),
        channel_type=channel_type,
        channel_count=record_count,
    )


def _resolve_js_symbol_rate(
    mappings: list[FieldMapping],
    data_values: list[str],
    fields_per_record: int,
    warnings: list[str],
) -> None:
    """Set unit and scale on a JS symbol_rate mapping from every record's value."""
    for m in mappings:
        if m.field == "symbol_rate" and fields_per_record and m.offset is not None:
            samples = data_values[m.offset :: fields_per_record]
            m.unit, m.scale = symbol_rate_unit_and_scale(samples, m.unit, warnings)


# -----------------------------------------------------------------------
# JSON format
# -----------------------------------------------------------------------

# A list of objects is a channel array only when it carries one of these.
_MEASUREMENT_FIELDS = frozenset({"frequency", "power", "snr"})


def _extract_json_mappings(
    json_data: dict[str, Any],
    resource: str,
    direction: str,
    warnings: list[str],
    *,
    fleet: FleetPatterns | None = None,
) -> SectionDetail | None:
    """The first channel array of a JSON response, for callers that read one."""
    arrays = extract_json_arrays(json_data, resource, warnings, fleet=fleet)
    return arrays[0] if arrays else None


def extract_json_arrays(
    json_data: dict[str, Any],
    resource: str,
    warnings: list[str],
    *,
    fleet: FleetPatterns | None = None,
) -> list[SectionDetail]:
    """Every channel array in a JSON response, in document order; every other list is warned."""
    sections: list[SectionDetail] = []
    for array_path, items in _list_arrays(json_data):
        section = _json_array_section(array_path, items, resource, warnings, fleet)
        if section is None:
            # Named so a real channel array the rule missed shows at review.
            warnings.append(
                f"{WARNING_PREFIX} JSON array '{array_path}' on {resource} maps no channel "
                f"measurement key ({', '.join(sorted(_MEASUREMENT_FIELDS))}); skipped. "
                "Review it if it holds channels."
            )
            continue
        sections.append(section)
    return sections


def _json_array_section(
    array_path: str,
    channel_array: list[dict[str, Any]],
    resource: str,
    warnings: list[str],
    fleet: FleetPatterns | None,
) -> SectionDetail | None:
    """Map one array's keys; None unless one of them is a channel measurement."""
    # Use first item as sample
    sample = channel_array[0]

    mappings: list[FieldMapping] = []
    contested_keys: list[tuple[str, list[Candidate]]] = []
    for key, value in sample.items():
        field_name, tier = match_json_key_to_field(key)
        if not field_name:
            continue
        if tier == 3:
            # The registry left the key unmapped: one fleet meaning is learned;
            # several keep Tier 3 until the LLM resolves the key.
            learned = learned_field(key, fleet)
            if learned:
                field_name, tier = learned, 1
            elif candidates := key_candidates(key, channel_array, resource, fleet):
                contested_keys.append((key, candidates))

        field_type, unit = detect_field_type(field_name, [str(value)] if value is not None else [])
        # JSON keys emit no unit, except symbol_rate (see transposed).
        key_unit, scale = "", None
        if field_name == "symbol_rate":
            samples = [str(ch[key]) for ch in channel_array if isinstance(ch, dict) and ch.get(key) is not None]
            key_unit, scale = symbol_rate_unit_and_scale(samples, unit, warnings)
        mappings.append(
            FieldMapping(
                field=field_name,
                type=field_type,
                tier=tier,
                unit=key_unit,
                key=key,
                scale=scale,
            )
        )

    if not any(m.field in _MEASUREMENT_FIELDS for m in mappings):
        return None

    return SectionDetail(
        format="json",
        resource=resource,
        mappings=mappings,
        array_path=array_path,
        channel_type=detect_channel_type_json(channel_array),
        channel_count=len(channel_array),
        contested_keys=contested_keys,
    )


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _list_arrays(data: dict[str, Any], prefix: str = "") -> list[tuple[str, list[dict[str, Any]]]]:
    """Every non-empty list of objects under ``data``, by dot-notation path, in document order."""
    found: list[tuple[str, list[dict[str, Any]]]] = []
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, list) and value and isinstance(value[0], dict):
            found.append((path, value))
        elif isinstance(value, dict):
            found.extend(_list_arrays(value, path))
    return found


def _count_data_rows(table: DetectedTable) -> int:
    """Count data rows in a table (excluding empty/dash rows)."""
    return sum(1 for row in table.rows if is_data_row(row))


def _classify_counter_indices(
    field_counts: dict[str, int],
    row_counter_indices: dict[str, list[int]],
    mappings: list[FieldMapping],
) -> tuple[set[int], set[int]]:
    """Classify counter mapping positions into remove vs remap sets.

    For each duplicated field: if all copies are counters, keep only the
    highest-index one. Otherwise, remap channel_id counters to channel_number
    and drop counters for all other fields.
    """
    remove_indices: set[int] = set()
    # channel_id row counters become channel_number (display row position,
    # not DOCSIS ID) when a real non-sequential channel_id column exists.
    remap_to_channel_number: set[int] = set()
    for field_name, counter_idxs in row_counter_indices.items():
        total_for_field = field_counts[field_name]
        if len(counter_idxs) == total_for_field:
            # All are row counters — keep the one at the highest column index
            best = max(counter_idxs, key=lambda i: mappings[i].index or 0)
            remove_indices.update(i for i in counter_idxs if i != best)
        else:
            # Only some are row counters — remap channel_id row counters to
            # channel_number; remove row counters for all other fields.
            for i in counter_idxs:
                if field_name == "channel_id":
                    remap_to_channel_number.add(i)
                else:
                    remove_indices.add(i)
    return remove_indices, remap_to_channel_number


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

    # Identify row-counter mappings per duplicated field
    row_counter_indices: dict[str, list[int]] = {}
    for i, m in enumerate(mappings):
        if m.field in duplicated_fields and m.index is not None and _is_row_counter(m.index, data_rows, row_count):
            row_counter_indices.setdefault(m.field, []).append(i)

    remove_indices, remap_to_channel_number = _classify_counter_indices(field_counts, row_counter_indices, mappings)

    result = []
    for i, m in enumerate(mappings):
        if i in remove_indices:
            continue
        if i in remap_to_channel_number:
            m.field = "channel_number"
        result.append(m)
    return result


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
