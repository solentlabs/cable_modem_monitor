"""Parser dict assembly — builds parser.yaml dict from analysis sections.

Transforms analysis channel sections (table, transposed, javascript,
hnap, json) into the parser.yaml dict format expected by Pydantic
validation and YAML serialization.

Per ONBOARDING_SPEC.md ``generate_config`` tool contract.
"""

from __future__ import annotations

from typing import Any

from .mappings import mapping_to_channel, mapping_to_column, mapping_to_json_channel, mapping_to_row
from .system_info import transform_system_info


def build_parser_dict(sections: dict[str, Any]) -> dict[str, Any] | None:
    """Transform analysis sections into parser.yaml dict."""
    result: dict[str, Any] = {}

    for section_name in ("downstream", "upstream"):
        section = sections.get(section_name)
        if section:
            transformed = _transform_channel_section(section)
            if transformed:
                result[section_name] = transformed

    system_info = sections.get("system_info")
    if system_info:
        result["system_info"] = transform_system_info(system_info)

    return result if result else None


def _transform_channel_section(section: dict[str, Any]) -> dict[str, Any] | None:
    """Transform a channel section from analysis format to parser.yaml format.

    Dispatches to format-specific transformers based on the ``format`` field.
    """
    fmt = section.get("format", "")

    if fmt == "table":
        return _transform_table(section)
    if fmt == "table_transposed":
        return _transform_transposed(section)
    if fmt == "javascript":
        return _transform_javascript(section)
    if fmt == "hnap":
        return _transform_hnap(section)
    if fmt == "json":
        return _transform_json(section)

    return None


def _transform_table(section: dict[str, Any]) -> dict[str, Any]:
    """Transform table format from analysis to parser.yaml structure."""
    columns = [mapping_to_column(m) for m in section.get("mappings", [])]

    ct = section.get("channel_type")
    if ct and "index" in ct:
        # Inline the channel_type mapping on the columns list
        columns.append(
            {
                "index": ct["index"],
                "field": "channel_type",
                "type": "string",
                "map": ct["map"],
            }
        )
        ct = None

    table_def: dict[str, Any] = {}
    if section.get("selector"):
        table_def["selector"] = section["selector"]
    if section.get("row_start"):
        table_def["row_start"] = section["row_start"]
    table_def["columns"] = columns
    if ct:
        table_def["channel_type"] = ct
    if section.get("filter"):
        table_def["filter"] = section["filter"]

    return {
        "format": "table",
        "resource": section.get("resource", ""),
        "tables": [table_def],
    }


def _transform_transposed(section: dict[str, Any]) -> dict[str, Any]:
    """Transform transposed table from analysis to parser.yaml structure."""
    rows = [mapping_to_row(m) for m in section.get("mappings", [])]

    result: dict[str, Any] = {
        "format": "table_transposed",
        "resource": section.get("resource", ""),
    }

    if section.get("selector"):
        result["selector"] = section["selector"]
    result["rows"] = rows
    if section.get("channel_type"):
        result["channel_type"] = section["channel_type"]

    return result


def _transform_javascript(section: dict[str, Any]) -> dict[str, Any]:
    """Transform JS format from analysis to parser.yaml structure."""
    fields = [mapping_to_channel(m) for m in section.get("mappings", [])]
    channel_type = section.get("channel_type", {})

    func_def: dict[str, Any] = {
        "name": section.get("function_name", ""),
        "channel_type": channel_type.get("fixed", "qam") if channel_type else "qam",
        "delimiter": section.get("delimiter", "|"),
        "fields_per_channel": section.get("fields_per_record", 0),
        "fields": fields,
    }
    if section.get("filter"):
        func_def["filter"] = section["filter"]

    return {
        "format": "javascript",
        "resource": section.get("resource", ""),
        "functions": [func_def],
    }


def _transform_hnap(section: dict[str, Any]) -> dict[str, Any]:
    """Transform HNAP format from analysis to parser.yaml structure."""
    fields = [mapping_to_channel(m) for m in section.get("mappings", [])]

    ct = section.get("channel_type")
    if ct and "index" in ct:
        # Inline the channel_type mapping on the fields list
        fields.append(
            {
                "index": ct["index"],
                "field": "channel_type",
                "type": "string",
                "map": ct["map"],
            }
        )
        ct = None

    result: dict[str, Any] = {
        "format": "hnap",
        "response_key": section.get("response_key", ""),
        "data_key": section.get("data_key", ""),
        "record_delimiter": section.get("record_delimiter", "|+|"),
        "field_delimiter": section.get("field_delimiter", "^"),
        "fields": fields,
    }
    if ct:
        result["channel_type"] = ct
    if section.get("filter"):
        result["filter"] = section["filter"]

    return result


def _transform_json(section: dict[str, Any]) -> dict[str, Any]:
    """Transform JSON format from analysis to parser.yaml structure."""
    fields = [mapping_to_json_channel(m) for m in section.get("mappings", [])]

    ct = section.get("channel_type")
    if ct and "key" in ct:
        # Inline the channel_type mapping on the fields list
        fields.append(
            {
                "key": ct["key"],
                "field": "channel_type",
                "type": "string",
                "map": ct["map"],
            }
        )
        ct = None  # Don't also set section-level

    result: dict[str, Any] = {
        "format": "json",
        "resource": section.get("resource", ""),
        "array_path": section.get("array_path", ""),
        "fields": fields,
    }
    if ct:
        result["channel_type"] = ct
    if section.get("filter"):
        result["filter"] = section["filter"]

    return result
