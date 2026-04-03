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


class XMLSection(BaseModel):
    """XML channel section config.

    Navigates to a root element by tag name, iterates child elements,
    and extracts fields from sub-element text content.

    ``fixed_fields`` assigns static values to every channel (e.g.,
    ``lock_status: "locked"`` when presence in the table implies lock).

    ``lock_status`` derives the lock status from multiple boolean XML
    fields via AND (e.g., IsQamLocked AND IsFECLocked AND IsMpegLocked).
    """

    model_config = ConfigDict(extra="forbid")
    format: Literal["xml"]
    resource: str
    root_element: str
    child_element: str
    columns: list[XMLColumnMapping]
    channel_type: ChannelTypeConfig | None = None
    lock_status: LockStatusAllOf | None = None
    fixed_fields: dict[str, str] = Field(default_factory=dict)
    filter: dict[str, FilterValue] = Field(default_factory=dict)
