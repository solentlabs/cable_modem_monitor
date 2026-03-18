"""Phase 6 result types for field mapping and system info.

Dataclasses for section configuration, field mappings, and
system_info detection output. Used by the mapping dispatcher,
system_info, and the format dispatcher.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldMapping:
    """A single field mapping from source position to canonical name.

    The locator key varies by format: ``index`` (table column),
    ``offset`` (javascript/hnap), ``key`` (json), ``label``
    (table_transposed row label).
    """

    field: str
    type: str
    tier: int = 3
    unit: str = ""
    index: int | None = None
    offset: int | None = None
    key: str = ""
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the sections output format."""
        result: dict[str, Any] = {"field": self.field, "type": self.type}
        if self.unit:
            result["unit"] = self.unit
        if self.index is not None:
            result["index"] = self.index
        if self.offset is not None:
            result["offset"] = self.offset
        if self.key:
            result["key"] = self.key
        if self.label:
            result["label"] = self.label
        return result


def find_mapping(mappings: list[FieldMapping], field_name: str) -> FieldMapping | None:
    """Find a mapping by canonical field name."""
    for m in mappings:
        if m.field == field_name:
            return m
    return None


@dataclass
class SectionDetail:
    """Detected configuration for a single data section (DS/US).

    Format-agnostic ``mappings`` output.
    ``generate_config`` transforms this into parser.yaml.
    """

    format: str
    resource: str
    mappings: list[FieldMapping]
    selector: dict[str, str] = field(default_factory=dict)
    row_start: int = 0
    channel_type: dict[str, Any] | None = None
    filter: dict[str, Any] | None = None
    channel_count: int = 0
    function_name: str = ""
    delimiter: str = ""
    fields_per_record: int = 0
    array_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the sections output format."""
        result: dict[str, Any] = {
            "format": self.format,
            "resource": self.resource,
            "mappings": [m.to_dict() for m in self.mappings],
        }
        if self.selector:
            result["selector"] = self.selector
        if self.row_start:
            result["row_start"] = self.row_start
        if self.channel_type is not None:
            result["channel_type"] = self.channel_type
        if self.filter is not None:
            result["filter"] = self.filter
        if self.channel_count:
            result["channel_count"] = self.channel_count
        if self.function_name:
            result["function_name"] = self.function_name
        if self.delimiter:
            result["delimiter"] = self.delimiter
        if self.fields_per_record:
            result["fields_per_record"] = self.fields_per_record
        if self.array_path:
            result["array_path"] = self.array_path
        return result


@dataclass
class SystemInfoFieldDetail:
    """A detected system_info field."""

    field: str
    type: str = "string"
    selector_type: str = ""  # "label" or "id"
    selector_value: str = ""
    source: str = ""  # HNAP/JSON source key
    pattern: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the sections output format."""
        result: dict[str, Any] = {"field": self.field, "type": self.type}
        if self.selector_type == "label":
            result["label"] = self.selector_value
        elif self.selector_type == "id":
            result["id"] = self.selector_value
        elif self.source:
            result["source"] = self.source
        if self.pattern:
            result["pattern"] = self.pattern
        return result


@dataclass
class SystemInfoSourceDetail:
    """A detected system_info source page."""

    format: str
    resource: str
    fields: list[SystemInfoFieldDetail]
    response_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the sections output format."""
        result: dict[str, Any] = {
            "format": self.format,
            "resource": self.resource,
            "fields": [f.to_dict() for f in self.fields],
        }
        if self.response_key:
            result["response_key"] = self.response_key
        return result


@dataclass
class SystemInfoDetail:
    """Detected system_info configuration with multi-source support."""

    sources: list[SystemInfoSourceDetail]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the sections output format."""
        return {"sources": [s.to_dict() for s in self.sources]}
