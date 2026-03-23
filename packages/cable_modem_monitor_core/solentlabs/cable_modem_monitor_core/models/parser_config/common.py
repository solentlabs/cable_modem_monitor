"""Shared types for parser.yaml section models.

Field mappings, selectors, channel type detection, and filter rules.
Used across all format-specific modules.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from ..field_registry import FIELD_TYPES


def _check_field_type(field_type: str) -> None:
    """Validate that a field type is one of the canonical FIELD_TYPES.

    Raises ValueError with the invalid type and the valid set.
    """
    if field_type not in FIELD_TYPES:
        raise ValueError(f"invalid field type '{field_type}', must be one of " f"{sorted(FIELD_TYPES)}")


class ColumnMapping(BaseModel):
    """HTMLTableParser column -> field mapping."""

    model_config = ConfigDict(extra="forbid")
    index: int
    field: str
    type: str
    unit: str = ""
    map: dict[str, str] | None = None

    @model_validator(mode="after")
    def validate_field_type(self) -> ColumnMapping:
        """Ensure type is a valid FIELD_TYPES value."""
        _check_field_type(self.type)
        return self


class RowMapping(BaseModel):
    """HTMLTableTransposedParser row label -> field mapping."""

    model_config = ConfigDict(extra="forbid")
    label: str
    field: str
    type: str
    unit: str = ""
    map: dict[str, str] | None = None

    @model_validator(mode="after")
    def validate_field_type(self) -> RowMapping:
        """Ensure type is a valid FIELD_TYPES value."""
        _check_field_type(self.type)
        return self


class ChannelMapping(BaseModel):
    """Positional field mapping for HNAP and JSEmbedded parsers."""

    model_config = ConfigDict(extra="forbid")
    offset: int | None = None
    index: int | None = None
    field: str
    type: str
    unit: str = ""
    fallback_key: str = ""
    map: dict[str, str] | None = None

    @model_validator(mode="after")
    def validate_has_position(self) -> ChannelMapping:
        """Ensure at least one of offset or index is provided."""
        if self.offset is None and self.index is None:
            raise ValueError("channel mapping requires either 'offset' or 'index'")
        return self

    @model_validator(mode="after")
    def validate_field_type(self) -> ChannelMapping:
        """Ensure type is a valid FIELD_TYPES value."""
        _check_field_type(self.type)
        return self


class JsonChannelMapping(BaseModel):
    """JSONParser key -> field mapping.

    Optional ``separator`` splits the raw value on a delimiter before
    type conversion. ``separator_index`` selects which segment to use
    (default 0 = first). Example: ``"0.3/60.3"`` with
    ``separator: "/"`` and ``separator_index: 0`` yields ``"0.3"``.
    """

    model_config = ConfigDict(extra="forbid")
    key: str
    field: str
    type: str
    unit: str = ""
    fallback_key: str = ""
    truthy: Any | None = None
    map: dict[str, str] | None = None
    separator: str = ""
    separator_index: int = 0

    @model_validator(mode="after")
    def validate_field_type(self) -> JsonChannelMapping:
        """Ensure type is a valid FIELD_TYPES value."""
        _check_field_type(self.type)
        return self


class TableSelector(BaseModel):
    """How to find a table in an HTML page."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["header_text", "css", "id", "nth", "attribute"]
    match: str | int | dict[str, str]
    fallback: TableSelector | None = None


class ChannelTypeFixed(BaseModel):
    """All channels are the same type."""

    model_config = ConfigDict(extra="forbid")
    fixed: str


class ChannelTypeMap(BaseModel):
    """Derive channel type from another field's value via map lookup.

    Used for cross-field derivation (e.g., deriving channel_type from
    a modulation field). For same-field mapping, use inline ``map:``
    on the column/row/field mapping instead.
    """

    model_config = ConfigDict(extra="forbid")
    field: str
    map: dict[str, str]


ChannelTypeConfig = ChannelTypeFixed | ChannelTypeMap

FilterValue = str | dict[str, Any]
