"""JSONParser section config.

JSON format: path navigation and key access in JSON API responses.
Supports flat form (single array_path + fields) or multi-array form
(arrays list) for modems with multiple channel arrays in one response.
Per PARSING_SPEC.md JSONParser section.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import ChannelTypeConfig, FilterValue, JsonChannelMapping


class JSONArrayDefinition(BaseModel):
    """A single array within a multi-array JSONParser section."""

    model_config = ConfigDict(extra="forbid")
    array_path: str
    fields: list[JsonChannelMapping]
    channel_type: ChannelTypeConfig | None = None
    filter: dict[str, FilterValue] = Field(default_factory=dict)


class JSONSection(BaseModel):
    """JSONParser section config.

    Supports flat form (array_path + fields at top level) or
    multi-array form (arrays list). Mutually exclusive.
    """

    model_config = ConfigDict(extra="forbid")
    format: Literal["json"]
    resource: str
    encoding: str = ""

    # Flat form
    array_path: str = ""
    fields: list[JsonChannelMapping] | None = None
    channel_type: ChannelTypeConfig | None = None
    filter: dict[str, FilterValue] = Field(default_factory=dict)

    # Multi-array form
    arrays: list[JSONArrayDefinition] | None = None

    @model_validator(mode="after")
    def validate_form_exclusivity(self) -> JSONSection:
        """Ensure flat form and multi-array form are mutually exclusive."""
        has_flat = bool(self.array_path) or self.fields is not None
        has_multi = self.arrays is not None
        if has_flat and has_multi:
            raise ValueError("json: use either flat form (array_path/fields) or " "multi-array form (arrays), not both")
        if not has_flat and not has_multi:
            raise ValueError("json: must have either array_path/fields or arrays")
        if has_flat and (not self.array_path or self.fields is None):
            raise ValueError("json flat form requires both array_path and fields")
        return self
