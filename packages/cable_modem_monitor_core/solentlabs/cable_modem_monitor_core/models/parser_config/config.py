"""Top-level ParserConfig model.

Assembles format-specific sections and system_info into a unified config.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Discriminator, Tag, model_validator

from .hnap import HNAPSection
from .javascript import JSEmbeddedSection
from .json_format import JSONSection
from .system_info import SystemInfoSection
from .table import HTMLTableSection
from .transposed import HTMLTableTransposedSection


def _get_section_format(data: Any) -> str:
    """Extract format from section data for discrimination."""
    if isinstance(data, dict):
        return str(data.get("format", ""))
    return str(getattr(data, "format", ""))


ChannelSection = Annotated[
    Annotated[HTMLTableSection, Tag("table")]
    | Annotated[HTMLTableTransposedSection, Tag("table_transposed")]
    | Annotated[JSEmbeddedSection, Tag("javascript")]
    | Annotated[HNAPSection, Tag("hnap")]
    | Annotated[JSONSection, Tag("json")],
    Discriminator(_get_section_format),
]


class ParserConfig(BaseModel):
    """Full parser.yaml schema.

    Sections are optional -- a modem may have downstream only, or downstream
    + upstream, or all three. At least one section must be present.
    """

    model_config = ConfigDict(extra="forbid")

    downstream: ChannelSection | None = None
    upstream: ChannelSection | None = None
    system_info: SystemInfoSection | None = None

    @model_validator(mode="after")
    def validate_has_sections(self) -> ParserConfig:
        """Ensure at least one section is present."""
        if self.downstream is None and self.upstream is None and self.system_info is None:
            raise ValueError("parser.yaml must have at least one section " "(downstream, upstream, or system_info)")
        return self
