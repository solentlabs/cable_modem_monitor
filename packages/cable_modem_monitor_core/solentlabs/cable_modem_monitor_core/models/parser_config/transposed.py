"""HTMLTableTransposedParser section config.

Transposed table format: rows are metrics, columns are channels.
Supports flat form (selector + rows) or multi-table form (tables list).
Per PARSING_SPEC.md HTMLTableTransposedParser section.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, NonNegativeInt, model_validator

from .common import ChannelTypeConfig, RowMapping, TableSelector
from .format_registry import DecodeKind


class TransposedTableDefinition(BaseModel):
    """A single table within an HTMLTableTransposedParser multi-table section."""

    model_config = ConfigDict(extra="forbid")
    selector: TableSelector
    rows: list[RowMapping]
    channel_type: ChannelTypeConfig | None = None
    merge_by: list[str] | None = None
    # 0-based data columns whose cells the firmware copies from another
    # column. FORMAT_TABLE_SPEC § Skipping duplicated columns.
    skip_columns: list[NonNegativeInt] | None = None

    @model_validator(mode="after")
    def validate_skip_columns_companion_only(self) -> TransposedTableDefinition:
        """Reject skip_columns on a primary table, where it would drop a channel."""
        if self.skip_columns is not None and self.merge_by is None:
            raise ValueError("skip_columns requires merge_by: only a companion table can skip columns")
        return self


class HTMLTableTransposedSection(BaseModel):
    """HTMLTableTransposedParser section config.

    Supports flat form (selector + rows at top level) or multi-table form
    (tables list). Mutually exclusive.
    """

    format_tag: ClassVar[str] = "table_transposed"
    decode_kind: ClassVar[DecodeKind] = "html"
    transports: ClassVar[frozenset[str]] = frozenset({"http"})

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
