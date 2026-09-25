"""Top-level ParserConfig model.

Assembles format-specific sections, system_info, and aggregate
declarations into a unified config.
"""

from __future__ import annotations

from functools import reduce
from operator import or_
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, model_validator

from .format_registry import FormatModel
from .hnap import HNAPSection
from .javascript import JSEmbeddedSection
from .js_json import JSJsonSection
from .json_format import JSONSection
from .json_transposed import JSONTransposedSection
from .system_info import SYSTEM_INFO_SOURCE_MODELS, SystemInfoSection
from .table import HTMLTableSection
from .transposed import HTMLTableTransposedSection
from .xml_format import XMLSection


def _get_section_format(data: Any) -> str:
    """Extract format from section data for discrimination."""
    if isinstance(data, dict):
        return str(data.get("format", ""))
    return str(getattr(data, "format", ""))


# Single source of truth for channel-section format metadata.
# Adding a format = define the model with its ClassVars and append
# here. The discriminated union below, the loader's decode dispatch,
# the cross-file validator, and the parser registry all derive from
# this list (combined with SYSTEM_INFO_SOURCE_MODELS where relevant).
#
# The static ChannelSection alias (visible to mypy/Pyright via the
# TYPE_CHECKING block below) must enumerate the same models in the
# same order. ``test_channel_section_registry_alignment`` enforces
# this — the static alias and the runtime list cannot drift.
CHANNEL_SECTION_MODELS: list[type[FormatModel]] = [
    HTMLTableSection,
    HTMLTableTransposedSection,
    JSEmbeddedSection,
    JSJsonSection,
    HNAPSection,
    JSONSection,
    JSONTransposedSection,
    XMLSection,
]

# Combined registry — every parser-format model in the system.
# Loaders and cross-cutting validators iterate this; per-section
# behaviour iterates the section list alone.
ALL_FORMAT_MODELS: list[type[FormatModel]] = [
    *CHANNEL_SECTION_MODELS,
    *SYSTEM_INFO_SOURCE_MODELS,
]


if TYPE_CHECKING:
    # Static type alias for type-checkers (mypy/Pyright cannot infer a
    # union built at runtime from a registry list). Must mirror
    # CHANNEL_SECTION_MODELS exactly — drift is caught by the
    # alignment test.
    ChannelSection = Annotated[
        Annotated[HTMLTableSection, Tag("table")]
        | Annotated[HTMLTableTransposedSection, Tag("table_transposed")]
        | Annotated[JSEmbeddedSection, Tag("javascript")]
        | Annotated[JSJsonSection, Tag("javascript_json")]
        | Annotated[HNAPSection, Tag("hnap")]
        | Annotated[JSONSection, Tag("json")]
        | Annotated[JSONTransposedSection, Tag("json_transposed")]
        | Annotated[XMLSection, Tag("xml")],
        Discriminator(_get_section_format),
    ]
else:
    ChannelSection = Annotated[
        reduce(or_, (Annotated[m, Tag(m.format_tag)] for m in CHANNEL_SECTION_MODELS)),
        Discriminator(_get_section_format),
    ]


class AggregateField(BaseModel):
    """A derived field computed from channel data.

    Declares a scoped sum over a channel field. Only ``sum`` is
    supported — this is purpose-built for error totals, not a general
    aggregation engine.

    See PARSING_SPEC.md § Aggregate (Derived system_info Fields).

    Attributes:
        sum: Channel field to sum (e.g., ``corrected``, ``uncorrected``).
        channels: Scope — ``downstream``, ``upstream``, or type-qualified
            (``downstream.qam``, ``downstream.ofdm``, ``upstream.atdma``,
            ``upstream.ofdma``).
    """

    model_config = ConfigDict(extra="forbid")
    sum: str
    channels: str


class ComputedField(BaseModel):
    """A derived field computed from other system_info fields.

    Declares a named operation applied to input fields. The ``inputs``
    dict maps operation-defined parameter names to system_info field
    names. Each operation defines what keys it expects.

    See PARSING_SPEC.md § Computed (Derived system_info Fields).

    Attributes:
        operation: Named operation to apply (e.g., ``percent_used``).
        inputs: Mapping of operation parameter names to system_info
            field names (e.g., ``{total: memory_total, free: memory_free}``).
        precision: Decimal places for numeric results (default 1).
    """

    model_config = ConfigDict(extra="forbid")
    operation: Literal["percent_used", "combined_status"]
    inputs: dict[str, str]
    precision: int = 1


class ResourceRequest(BaseModel):
    """How one resource path is fetched when GET is not enough (PARSING_SPEC § Fetch List Derivation)."""

    model_config = ConfigDict(extra="forbid")
    method: Literal["POST"]
    # Sent application/x-www-form-urlencoded, verbatim as the capture shows it.
    form: dict[str, str] = Field(default_factory=dict)


class ParserConfig(BaseModel):
    """Full parser.yaml schema.

    Sections are optional -- a modem may have downstream only, or downstream
    + upstream, or all three. At least one section must be present.

    The ``aggregate`` section declares derived fields computed from
    channel data (e.g., error totals). See PARSING_SPEC.md § Aggregate.
    """

    model_config = ConfigDict(extra="forbid")

    # First field: parser.yaml key order follows this field order
    # (MODEM_YAML_SPEC § Layout). Keyed by the path a section or a
    # parser.py resource reads; fetch_list.collect_fetch_targets rejects
    # a key nothing reads, because only it also sees parser.py.
    requests: dict[str, ResourceRequest] = Field(default_factory=dict)
    downstream: ChannelSection | None = None
    upstream: ChannelSection | None = None
    system_info: SystemInfoSection | None = None
    aggregate: dict[str, AggregateField] = Field(default_factory=dict)
    computed: dict[str, ComputedField] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_has_sections(self) -> ParserConfig:
        """Ensure at least one section is present."""
        if self.downstream is None and self.upstream is None and self.system_info is None:
            raise ValueError("parser.yaml must have at least one section " "(downstream, upstream, or system_info)")
        return self
