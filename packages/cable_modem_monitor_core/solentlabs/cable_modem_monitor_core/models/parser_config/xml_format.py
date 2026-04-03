"""XMLParser section config.

XML format: element navigation and tag-based extraction from XML API
responses. Used by the ``cbn`` transport where each resource is a
``defusedxml.ElementTree.Element``.
Per PARSING_SPEC.md XMLParser section.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import ChannelTypeConfig, FilterValue, _check_field_type


class XMLColumnMapping(BaseModel):
    """Mapping from an XML sub-element tag to a canonical field.

    The optional ``scale`` multiplier applies after type conversion.
    Use it for unit normalization (e.g., Msym/s → ksym/s with
    ``scale: 1000``). Whole-number results are cast to int.
    """

    model_config = ConfigDict(extra="forbid")
    source: str
    field: str
    type: str
    scale: int | float | None = None

    @model_validator(mode="after")
    def validate_field_type(self) -> XMLColumnMapping:
        """Ensure type is a valid FIELD_TYPES value."""
        _check_field_type(self.type)
        return self


class LockStatusAllOf(BaseModel):
    """Derive ``lock_status`` from AND of multiple boolean XML fields.

    Each source is an XML sub-element tag name. The element's text is
    converted to boolean (``"1"`` / ``"true"`` → True). All sources
    must be true for ``lock_status`` to be ``"locked"``.
    """

    model_config = ConfigDict(extra="forbid")
    all_of: list[str] = Field(min_length=1)


class XMLTableDefinition(BaseModel):
    """Single XML table within a channel section.

    Defines one resource fetch and its column extraction rules.
    Multiple tables in a section are fetched independently and their
    channel results concatenated in order.

    Each table has its own resource (``fun`` parameter for CBN),
    root/child element paths, column mappings, and channel type.
    """

    model_config = ConfigDict(extra="forbid")
    resource: str
    root_element: str
    child_element: str
    columns: list[XMLColumnMapping]
    channel_type: ChannelTypeConfig | None = None
    lock_status: LockStatusAllOf | None = None
    fixed_fields: dict[str, str] = Field(default_factory=dict)
    filter: dict[str, FilterValue] = Field(default_factory=dict)


class XMLSection(BaseModel):
    """XML channel section config.

    Contains one or more tables, each fetching from a different XML
    resource. Results are concatenated in order. This supports modems
    that serve QAM and OFDM channels from separate API calls.

    See PARSING_SPEC.md § XML Tables.
    """

    model_config = ConfigDict(extra="forbid")
    format: Literal["xml"]
    tables: list[XMLTableDefinition] = Field(min_length=1)
