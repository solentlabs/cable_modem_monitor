"""JSJsonParser section config.

JavaScript JSON format: JSON arrays assigned to variables inside
``<script>`` tags. Distinct from the ``javascript`` format which
handles pipe-delimited ``tagValueList`` strings in function bodies.

Example source HTML::

    <script>
    json_dsData = [{"ChannelID": "1", "Frequency": 570}, ...];
    </script>

Per parser.yaml, configured as::

    downstream:
      format: js_json
      resource: /status.php
      variable: json_dsData
      mappings:
        - key: ChannelID
          field: channel_id
          type: integer
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import ChannelTypeConfig, FilterValue, JsonChannelMapping


class JSJsonSection(BaseModel):
    """JSJsonParser section config — JSON arrays from JS variable assignments."""

    model_config = ConfigDict(extra="forbid")
    format: Literal["javascript_json"]
    resource: str
    variable: str
    mappings: list[JsonChannelMapping]
    channel_type: ChannelTypeConfig | None = None
    filter: dict[str, FilterValue] = Field(default_factory=dict)
