"""HNAPParser section config.

HNAP format: delimiter-separated values in HNAP JSON responses.
Per PARSING_SPEC.md HNAPParser section.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import ChannelMapping, ChannelTypeConfig, FilterValue


class HNAPSection(BaseModel):
    """HNAPParser section config."""

    model_config = ConfigDict(extra="forbid")
    format: Literal["hnap"]
    response_key: str
    data_key: str
    record_delimiter: str
    field_delimiter: str
    channels: list[ChannelMapping]
    channel_type: ChannelTypeConfig | None = None
    filter: dict[str, FilterValue] = Field(default_factory=dict)
