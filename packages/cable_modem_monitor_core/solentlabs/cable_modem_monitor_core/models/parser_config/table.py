"""HTMLTableParser section config.

Standard table format: rows are channels, columns are fields.
Per PARSING_SPEC.md HTMLTableParser section.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import ChannelTypeConfig, ColumnMapping, FilterValue, TableSelector


class TableDefinition(BaseModel):
    """A single table within an HTMLTableParser section."""

    model_config = ConfigDict(extra="forbid")
    selector: TableSelector
    skip_rows: int = 0
    columns: list[ColumnMapping]
    channel_type: ChannelTypeConfig | None = None
    filter: dict[str, FilterValue] = Field(default_factory=dict)
    merge_by: list[str] | None = None


class HTMLTableSection(BaseModel):
    """HTMLTableParser section config."""

    model_config = ConfigDict(extra="forbid")
    format: Literal["table"]
    resource: str
    tables: list[TableDefinition]
    encoding: str = ""
