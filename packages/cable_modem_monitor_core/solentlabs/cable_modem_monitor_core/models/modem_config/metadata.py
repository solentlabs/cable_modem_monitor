"""Metadata models for modem.yaml.

Hardware, attribution, aggregate, and references.
Per MODEM_YAML_SPEC.md.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AggregateField(BaseModel):
    """A derived field computed from channel data."""

    model_config = ConfigDict(extra="forbid")
    sum: str
    channels: str


class HardwareConfig(BaseModel):
    """Hardware metadata."""

    model_config = ConfigDict(extra="forbid")
    docsis_version: Literal["3.0", "3.1"]
    chipset: str = ""
    release_date: str = ""
    end_of_life: str = ""


class ContributorEntry(BaseModel):
    """A contributor attribution."""

    model_config = ConfigDict(extra="forbid")
    github: str
    contribution: str


class AttributionConfig(BaseModel):
    """Attribution metadata."""

    model_config = ConfigDict(extra="forbid")
    contributors: list[ContributorEntry] = Field(default_factory=list)


class ReferencesConfig(BaseModel):
    """Issue and PR references in markdown format."""

    model_config = ConfigDict(extra="forbid")
    issues: list[str] = Field(default_factory=list)
    prs: list[str] = Field(default_factory=list)
