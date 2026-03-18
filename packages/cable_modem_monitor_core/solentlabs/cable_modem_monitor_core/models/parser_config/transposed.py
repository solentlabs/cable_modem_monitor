"""HTMLTableTransposedParser section config.

Transposed table format: rows are metrics, columns are channels.
Supports flat form (selector + rows) or multi-table form (tables list).
Per PARSING_SPEC.md HTMLTableTransposedParser section.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from .common import ChannelTypeConfig, RowMapping, TableSelector


class TransposedTableDefinition(BaseModel):
    """A single table within an HTMLTableTransposedParser multi-table section."""

    model_config = ConfigDict(extra="forbid")
    selector: TableSelector
    rows: list[RowMapping]
    channel_type: ChannelTypeConfig | None = None
    merge_by: list[str] | None = None


class HTMLTableTransposedSection(BaseModel):
    """HTMLTableTransposedParser section config.

    Supports flat form (selector + rows at top level) or multi-table form
    (tables list). Mutually exclusive.
    """

    model_config = ConfigDict(extra="forbid")
    format: Literal["table_transposed"]
    resource: str
    encoding: str = ""

    # Flat form
    selector: TableSelector | None = None
    rows: list[RowMapping] | None = None
    channel_type: ChannelTypeConfig | None = None

    # Multi-table form
    tables: list[TransposedTableDefinition] | None = None

    @model_validator(mode="after")
    def validate_form_exclusivity(self) -> HTMLTableTransposedSection:
        """Ensure flat form and multi-table form are mutually exclusive."""
        has_flat = self.selector is not None or self.rows is not None
        has_multi = self.tables is not None
        if has_flat and has_multi:
            raise ValueError(
                "table_transposed: use either flat form (selector/rows) or " "multi-table form (tables), not both"
            )
        if not has_flat and not has_multi:
            raise ValueError("table_transposed: must have either selector/rows or tables")
        if has_flat and (self.selector is None or self.rows is None):
            raise ValueError("table_transposed flat form requires both selector and rows")
        return self
