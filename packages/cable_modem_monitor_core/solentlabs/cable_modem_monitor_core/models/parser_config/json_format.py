"""JSONParser section config.

JSON format: path navigation and key access in JSON API responses.
Supports flat form (single array_path + fields) or multi-array form
(arrays list). In multi-array form, each array may specify its own
resource endpoint — following the same per-table resource pattern
used by XMLSection. Per PARSING_SPEC.md JSONParser section.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import ChannelTypeConfig, FilterValue, JsonChannelMapping
from .format_registry import DecodeKind


class JSONArrayDefinition(BaseModel):
    """A single array within a multi-array JSONParser section.

    When ``resource`` is set, the array fetches from that endpoint
    instead of the section-level resource. This allows a single
    channel section to combine data from multiple API endpoints
    (e.g., QAM from one endpoint, OFDM from another).
    """

    model_config = ConfigDict(extra="forbid")
    resource: str = ""
    array_path: str
    fields: list[JsonChannelMapping]
    channel_type: ChannelTypeConfig | None = None
    fixed_fields: dict[str, str] = Field(default_factory=dict)
    filter: dict[str, FilterValue] = Field(default_factory=dict)


class JSONSection(BaseModel):
    """JSONParser section config.

    Supports flat form (array_path + fields at top level) or
    multi-array form (arrays list). Mutually exclusive.
    """

    format_tag: ClassVar[str] = "json"
    decode_kind: ClassVar[DecodeKind] = "json"
    transports: ClassVar[frozenset[str]] = frozenset({"http"})

    model_config = ConfigDict(extra="forbid")
    format: Literal["json"]
    resource: str = ""
    encoding: str = ""

    # Flat form
    array_path: str = ""
    fields: list[JsonChannelMapping] | None = None
    channel_type: ChannelTypeConfig | None = None
    fixed_fields: dict[str, str] = Field(default_factory=dict)
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
        if has_flat and not self.resource:
            raise ValueError("json flat form requires a resource")
        if has_multi:
            # These are flat-form-only: the multi-array parser reads them
            # per array, so a section-level value would validate and then
            # be silently ignored. Reject rather than surprise.
            ignored = [
                name
                for name, value in (
                    ("channel_type", self.channel_type),
                    ("fixed_fields", self.fixed_fields),
                    ("filter", self.filter),
                )
                if value
            ]
            if ignored:
                raise ValueError(
                    f"json multi-array form: {', '.join(ignored)} must be set "
                    "per array, not at section level (section-level values "
                    "are not applied to arrays)"
                )
        return self

    @model_validator(mode="after")
    def validate_resource_coverage(self) -> JSONSection:
        """In multi-array form, ensure every array can resolve a resource."""
        if self.arrays is None:
            return self
        if self.resource:
            return self  # section resource is the shared default
        missing = [i for i, a in enumerate(self.arrays) if not a.resource]
        if missing:
            raise ValueError(
                "json arrays: either provide section-level 'resource' " "or give every array its own 'resource'"
            )
        return self
