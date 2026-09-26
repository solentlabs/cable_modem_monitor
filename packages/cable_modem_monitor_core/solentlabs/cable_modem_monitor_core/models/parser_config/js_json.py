"""JSJsonParser section config.

JavaScript JSON format: JSON values assigned to variables inside
``<script>`` tags. Distinct from the ``javascript`` format which
handles pipe-delimited ``tagValueList`` strings in function bodies.

Two forms, mutually exclusive:

- flat: ``variable`` holds an array of channel objects, mapped by
  section-level ``mappings``.
- arrays: ``variable`` holds an object; each ``arrays[]`` entry selects
  one array in it by ``array_path``. Entries with ``merge_by`` are
  companions merged into the primary entries' channels.

Example source HTML::

    <script>
    json_dsData = [{"ChannelID": "1", "Frequency": 570}, ...];
    </script>

Per parser.yaml, configured as::

    downstream:
      format: javascript_json
      resource: /status.php
      variable: json_dsData
      mappings:
        - key: ChannelID
          field: channel_id
          type: integer

Per FORMAT_JAVASCRIPT_SPEC.md JSJsonParser section.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import ChannelTypeConfig, FilterValue, JsonChannelMapping
from .format_registry import DecodeKind


class JSJsonArrayDefinition(BaseModel):
    """One array inside an object variable; a companion when ``merge_by`` is set."""

    model_config = ConfigDict(extra="forbid")
    array_path: str
    mappings: list[JsonChannelMapping]
    channel_type: ChannelTypeConfig | None = None
    filter: dict[str, FilterValue] = Field(default_factory=dict)
    merge_by: list[str] | None = None


class JSJsonSection(BaseModel):
    """JSJsonParser section config — JSON arrays from JS variable assignments."""

    format_tag: ClassVar[str] = "javascript_json"
    decode_kind: ClassVar[DecodeKind] = "html"
    transports: ClassVar[frozenset[str]] = frozenset({"http"})

    model_config = ConfigDict(extra="forbid")
    format: Literal["javascript_json"]
    resource: str
    variable: str

    # Flat form
    mappings: list[JsonChannelMapping] | None = None
    channel_type: ChannelTypeConfig | None = None
    filter: dict[str, FilterValue] = Field(default_factory=dict)

    # Arrays form
    arrays: list[JSJsonArrayDefinition] | None = None

    @model_validator(mode="after")
    def validate_form_exclusivity(self) -> JSJsonSection:
        """Ensure exactly one of the flat and arrays forms, and a primary array."""
        has_flat = self.mappings is not None
        has_arrays = self.arrays is not None
        if has_flat and has_arrays:
            raise ValueError("javascript_json: use either flat form (mappings) or arrays form (arrays), not both")
        if not has_flat and not has_arrays:
            raise ValueError("javascript_json: must have either mappings or arrays")
        if self.arrays is not None:
            # These are flat-form-only: the arrays form reads them per
            # array, so a section-level value would validate and then be
            # silently ignored. Reject rather than surprise.
            ignored = [name for name, value in (("channel_type", self.channel_type), ("filter", self.filter)) if value]
            if ignored:
                raise ValueError(
                    f"javascript_json arrays form: {', '.join(ignored)} must be set "
                    "per array, not at section level (section-level values "
                    "are not applied to arrays)"
                )
            # Companions only enrich primary channels, so without a
            # primary the section could never yield a channel.
            if all(a.merge_by is not None for a in self.arrays):
                raise ValueError("javascript_json arrays form needs at least one primary array (no merge_by)")
        return self
