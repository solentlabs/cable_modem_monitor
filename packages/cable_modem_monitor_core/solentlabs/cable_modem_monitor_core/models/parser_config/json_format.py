"""JSONParser section config.

JSON format: path navigation and key access in JSON API responses.
Per PARSING_SPEC.md JSONParser section.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import ChannelTypeConfig, FilterValue, JsonChannelMapping


class JSONSection(BaseModel):
    """JSONParser section config."""

    model_config = ConfigDict(extra="forbid")
    format: Literal["json"]
    resource: str
    array_path: str
    channels: list[JsonChannelMapping]
    channel_type: ChannelTypeConfig | None = None
    filter: dict[str, FilterValue] = Field(default_factory=dict)
    encoding: str = ""
