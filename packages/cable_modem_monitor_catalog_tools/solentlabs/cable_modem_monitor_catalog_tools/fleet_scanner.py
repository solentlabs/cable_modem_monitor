"""Fleet scanner — builds FleetPatterns from the modem catalog.

Reads all ``parser.yaml`` files in the catalog and extracts proven
patterns: selector→direction mappings, system_info label/ID/JSON-key
mappings, delimiters, channel type values, and aggregate patterns.

The result is a ``FleetPatterns`` instance that Core's analyzer uses
to augment its baseline detection.

Usage::

    from cable_modem_monitor_catalog import CATALOG_PATH
    from cable_modem_monitor_catalog_tools.fleet_scanner import scan_fleet

    fleet = scan_fleet(CATALOG_PATH)
    result = analyze_har(har_path, fleet=fleet)
"""

from __future__ import annotations

from pathlib import Path

import yaml
from solentlabs.cable_modem_monitor_catalog_tools.analysis.types import FleetPatterns


def scan_fleet(catalog_path: Path) -> FleetPatterns:
    """Scan all parser.yaml files and build fleet patterns.

    Args:
        catalog_path: Root of the modem catalog directory
            (``modems/{manufacturer}/{model}/``).

    Returns:
        ``FleetPatterns`` populated from the fleet's proven configs.
    """
    selector_directions: dict[str, str] = {}
    system_info_labels: dict[str, tuple[str, int]] = {}
    system_info_ids: dict[str, tuple[str, int]] = {}
    system_info_json_keys: dict[str, tuple[str, int]] = {}
    delimiters: set[str] = set()
    channel_type_values: set[str] = set()
    aggregate_fields: list[tuple[str, str]] = []
    seen_aggregates: set[tuple[str, str]] = set()

    for parser_path in sorted(catalog_path.rglob("parser.yaml")):
        try:
            data = yaml.safe_load(parser_path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError):
            continue

        if not isinstance(data, dict):
            continue

        _extract_selectors(data, selector_directions)
        _extract_system_info_labels(data, system_info_labels)
        _extract_system_info_ids(data, system_info_ids)
        _extract_system_info_json_keys(data, system_info_json_keys)
        _extract_delimiters(data, delimiters)
        _extract_channel_type_values(data, channel_type_values)
        _extract_aggregates(data, aggregate_fields, seen_aggregates)

    return FleetPatterns(
        selector_directions=selector_directions,
        system_info_labels=system_info_labels,
        system_info_ids=system_info_ids,
        system_info_json_keys=system_info_json_keys,
        delimiters=delimiters,
        channel_type_values=channel_type_values,
        aggregate_fields=aggregate_fields,
    )


# -----------------------------------------------------------------------
# Selector → direction
# -----------------------------------------------------------------------


def _extract_selectors(
    data: dict[str, object],
    result: dict[str, str],
) -> None:
    """Extract selector.match → direction mappings from parser.yaml."""
    for direction in ("downstream", "upstream"):
        section = data.get(direction)
        if not isinstance(section, dict):
            continue

        _add_selector(section.get("selector"), direction, result)

        tables = section.get("tables")
        if isinstance(tables, list):
            for table in tables:
                if isinstance(table, dict):
                    _add_selector(table.get("selector"), direction, result)


def _add_selector(
    selector: object,
    direction: str,
    result: dict[str, str],
) -> None:
    """Add a single selector match to the result map."""
    if not isinstance(selector, dict):
        return
    match = selector.get("match")
    if isinstance(match, str) and match.strip():
        result[match.strip().lower()] = direction


# -----------------------------------------------------------------------
# System info: labels, IDs, JSON keys
# -----------------------------------------------------------------------


def _extract_system_info_labels(
    data: dict[str, object],
    result: dict[str, tuple[str, int]],
) -> None:
    """Extract label → (field, tier) from system_info ``label`` fields."""
    for field_def in _iter_system_info_fields(data):
        label = field_def.get("label")
        field_name = field_def.get("field")
        if isinstance(label, str) and isinstance(field_name, str) and label.strip() and field_name.strip():
            normalized = label.strip().lower()
            if normalized not in result:
                result[normalized] = (field_name.strip(), 1)


def _extract_system_info_ids(
    data: dict[str, object],
    result: dict[str, tuple[str, int]],
) -> None:
    """Extract element ID → (field, tier) from system_info ``id`` fields."""
    for field_def in _iter_system_info_fields(data):
        css_id = field_def.get("id")
        field_name = field_def.get("field")
        if isinstance(css_id, str) and isinstance(field_name, str) and css_id.strip() and field_name.strip():
            normalized = css_id.strip().lower()
            if normalized not in result:
                result[normalized] = (field_name.strip(), 1)


def _extract_system_info_json_keys(
    data: dict[str, object],
    result: dict[str, tuple[str, int]],
) -> None:
    """Extract JSON key → (field, tier) from system_info ``key`` fields."""
    for field_def in _iter_system_info_fields(data):
        key = field_def.get("key")
        field_name = field_def.get("field")
        if isinstance(key, str) and isinstance(field_name, str) and key.strip() and field_name.strip():
            normalized = key.strip().lower()
            if normalized not in result:
                result[normalized] = (field_name.strip(), 1)


def _iter_system_info_fields(
    data: dict[str, object],
) -> list[dict[str, object]]:
    """Iterate over all field dicts in system_info sources."""
    system_info = data.get("system_info")
    if not isinstance(system_info, dict):
        return []

    sources = system_info.get("sources")
    if not isinstance(sources, list):
        return []

    fields: list[dict[str, object]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_fields = source.get("fields")
        if not isinstance(source_fields, list):
            continue
        for field_def in source_fields:
            if isinstance(field_def, dict):
                fields.append(field_def)
    return fields


# -----------------------------------------------------------------------
# Delimiters
# -----------------------------------------------------------------------


def _extract_delimiters(
    data: dict[str, object],
    result: set[str],
) -> None:
    """Extract record delimiters from HNAP and JavaScript configs."""
    for direction in ("downstream", "upstream"):
        section = data.get(direction)
        if not isinstance(section, dict):
            continue

        # Section-level delimiter (HNAP/JS)
        _add_delimiter(section.get("delimiter"), result)

        # Per-function delimiters (JS)
        functions = section.get("functions")
        if isinstance(functions, list):
            for func in functions:
                if isinstance(func, dict):
                    _add_delimiter(func.get("delimiter"), result)


def _add_delimiter(value: object, result: set[str]) -> None:
    """Add a non-empty string delimiter to the result set."""
    if isinstance(value, str) and value.strip():
        result.add(value.strip())


# -----------------------------------------------------------------------
# Channel type values
# -----------------------------------------------------------------------


def _extract_channel_type_values(
    data: dict[str, object],
    result: set[str],
) -> None:
    """Extract channel type map keys from downstream/upstream sections."""
    for direction in ("downstream", "upstream"):
        section = data.get(direction)
        if not isinstance(section, dict):
            continue

        # Section-level channel_type.map
        _add_channel_type_map(section.get("channel_type"), result)

        # Per-table channel_type.map
        tables = section.get("tables")
        if isinstance(tables, list):
            for table in tables:
                if isinstance(table, dict):
                    _add_channel_type_map(table.get("channel_type"), result)


def _add_channel_type_map(ct: object, result: set[str]) -> None:
    """Add channel type map keys to the result set."""
    if not isinstance(ct, dict):
        return
    ct_map = ct.get("map")
    if isinstance(ct_map, dict):
        for key in ct_map:
            if isinstance(key, str) and key.strip():
                result.add(key.strip())


# -----------------------------------------------------------------------
# Aggregates
# -----------------------------------------------------------------------


def _extract_aggregates(
    data: dict[str, object],
    result: list[tuple[str, str]],
    seen: set[tuple[str, str]],
) -> None:
    """Extract (source_field, aggregate_name) pairs from aggregate sections."""
    aggregate = data.get("aggregate")
    if not isinstance(aggregate, dict):
        return

    for agg_name, agg_def in aggregate.items():
        if not isinstance(agg_def, dict):
            continue
        source_field = agg_def.get("sum")
        if isinstance(source_field, str) and source_field.strip():
            pair = (source_field.strip(), agg_name.strip())
            if pair not in seen:
                seen.add(pair)
                result.append(pair)
