"""Mapping conversion — analysis FieldMapping to parser config format.

Converts analysis-layer field mappings (index-based, key-based) into
the format expected by parser.yaml config models (ColumnMapping,
RowMapping, ChannelMapping, JsonChannelMapping).

Used by parser.py and system_info.py during config generation.
"""

from __future__ import annotations

from typing import Any

_TYPE_ALIASES: dict[str, str] = {
    "int": "integer",
    "str": "string",
    "bool": "boolean",
}


def normalize_type(field_type: str) -> str:
    """Normalize Python type names to parser config type names."""
    return _TYPE_ALIASES.get(field_type, field_type)


def mapping_to_column(mapping: dict[str, Any]) -> dict[str, Any]:
    """Convert analysis FieldMapping to table ColumnMapping dict."""
    result: dict[str, Any] = {
        "index": mapping.get("index", 0),
        "field": mapping["field"],
        "type": normalize_type(mapping["type"]),
    }
    if mapping.get("unit"):
        result["unit"] = mapping["unit"]
    if mapping.get("map"):
        result["map"] = mapping["map"]
    return result


def mapping_to_row(mapping: dict[str, Any]) -> dict[str, Any]:
    """Convert analysis FieldMapping to transposed RowMapping dict."""
    result: dict[str, Any] = {
        "label": mapping.get("label", ""),
        "field": mapping["field"],
        "type": normalize_type(mapping["type"]),
    }
    if mapping.get("unit"):
        result["unit"] = mapping["unit"]
    if mapping.get("map"):
        result["map"] = mapping["map"]
    return result


def mapping_to_channel(mapping: dict[str, Any]) -> dict[str, Any]:
    """Convert analysis FieldMapping to HNAP/JS ChannelMapping dict."""
    result: dict[str, Any] = {"field": mapping["field"], "type": normalize_type(mapping["type"])}
    if mapping.get("offset") is not None:
        result["offset"] = mapping["offset"]
    elif mapping.get("index") is not None:
        result["index"] = mapping["index"]
    if mapping.get("unit"):
        result["unit"] = mapping["unit"]
    if mapping.get("map"):
        result["map"] = mapping["map"]
    return result


def mapping_to_json_channel(mapping: dict[str, Any]) -> dict[str, Any]:
    """Convert analysis FieldMapping to JSON JsonChannelMapping dict."""
    result: dict[str, Any] = {
        "key": mapping.get("key", ""),
        "field": mapping["field"],
        "type": normalize_type(mapping["type"]),
    }
    if mapping.get("unit"):
        result["unit"] = mapping["unit"]
    if mapping.get("map"):
        result["map"] = mapping["map"]
    return result
