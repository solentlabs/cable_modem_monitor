"""System info section config.

Multi-source system_info with format-discriminated sources.
Per PARSING_SPEC.md System Info section.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Tag, model_validator

from .common import _check_field_type


class HTMLFieldMapping(BaseModel):
    """A single field extracted from HTML via label text, element id, or CSS."""

    model_config = ConfigDict(extra="forbid")
    field: str
    type: str
    label: str = ""
    id: str = ""
    css: str = ""
    pattern: str = ""
    attribute: str = ""

    @model_validator(mode="after")
    def validate_has_locator(self) -> HTMLFieldMapping:
        """Ensure at least one locator (label, id, or css) is provided."""
        if not self.label and not self.id and not self.css:
            raise ValueError("html_fields mapping requires at least one of: label, id, css")
        return self

    @model_validator(mode="after")
    def validate_field_type(self) -> HTMLFieldMapping:
        """Ensure type is a valid FIELD_TYPES value."""
        _check_field_type(self.type)
        return self


class HTMLFieldsSource(BaseModel):
    """html_fields source for system_info."""

    model_config = ConfigDict(extra="forbid")
    format: Literal["html_fields"]
    resource: str
    fields: list[HTMLFieldMapping]


class HNAPFieldMapping(BaseModel):
    """A single field from an HNAP response."""

    model_config = ConfigDict(extra="forbid")
    source: str
    field: str
    type: str

    @model_validator(mode="after")
    def validate_field_type(self) -> HNAPFieldMapping:
        """Ensure type is a valid FIELD_TYPES value."""
        _check_field_type(self.type)
        return self


class HNAPSystemInfoSource(BaseModel):
    """HNAP source for system_info."""

    model_config = ConfigDict(extra="forbid")
    format: Literal["hnap"]
    response_key: str
    fields: list[HNAPFieldMapping]


class JSSystemInfoFieldMapping(BaseModel):
    """A field extracted from a JS function for system_info."""

    model_config = ConfigDict(extra="forbid")
    offset: int
    field: str
    type: str

    @model_validator(mode="after")
    def validate_field_type(self) -> JSSystemInfoFieldMapping:
        """Ensure type is a valid FIELD_TYPES value."""
        _check_field_type(self.type)
        return self


class JSSystemInfoFunction(BaseModel):
    """A JS function that produces system_info fields."""

    model_config = ConfigDict(extra="forbid")
    name: str
    delimiter: str
    fields: list[JSSystemInfoFieldMapping]


class JSSystemInfoSource(BaseModel):
    """JavaScript-embedded source for system_info."""

    model_config = ConfigDict(extra="forbid")
    format: Literal["javascript"]
    resource: str
    functions: list[JSSystemInfoFunction]


class JSONSystemInfoFieldMapping(BaseModel):
    """A field extracted from a JSON response for system_info."""

    model_config = ConfigDict(extra="forbid")
    key: str
    field: str
    type: str
    path: str = ""

    @model_validator(mode="after")
    def validate_field_type(self) -> JSONSystemInfoFieldMapping:
        """Ensure type is a valid FIELD_TYPES value."""
        _check_field_type(self.type)
        return self


class JSONSystemInfoSource(BaseModel):
    """JSON API source for system_info."""

    model_config = ConfigDict(extra="forbid")
    format: Literal["json"]
    resource: str
    fields: list[JSONSystemInfoFieldMapping]


def _get_source_format(data: Any) -> str:
    """Extract format from source data for discrimination."""
    if isinstance(data, dict):
        return str(data.get("format", ""))
    return str(getattr(data, "format", ""))


SystemInfoSource = Annotated[
    Annotated[HTMLFieldsSource, Tag("html_fields")]
    | Annotated[HNAPSystemInfoSource, Tag("hnap")]
    | Annotated[JSSystemInfoSource, Tag("javascript")]
    | Annotated[JSONSystemInfoSource, Tag("json")],
    Discriminator(_get_source_format),
]


class SystemInfoSection(BaseModel):
    """system_info section config -- multi-source."""

    model_config = ConfigDict(extra="forbid")
    sources: list[SystemInfoSource]
