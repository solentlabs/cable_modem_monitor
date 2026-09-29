"""Ambiguities: judgments the capture supports but the tool does not make.

Analysis lists candidates with their wire evidence; the LLM resolves
them and the user confirms at review. Confirmed catalog entries
corroborate candidates, so the pipeline learns from every confirmed
modem without a pattern edit.

Per docs/ONBOARDING_SPEC.md § Ambiguities.
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field as dataclass_field,
)
from typing import Any


@dataclass
class Evidence:
    """Where a candidate was seen: a captured resource and the text that shows it."""

    source: str
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for MCP tool output."""
        return {"source": self.source, "snippet": self.snippet}


@dataclass
class Candidate:
    """One value a judgment could take, with its evidence and corroborating entries."""

    value: str
    evidence: list[Evidence] = dataclass_field(default_factory=list)
    corroborated_by: list[str] = dataclass_field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for MCP tool output."""
        return {
            "value": self.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "corroborated_by": self.corroborated_by,
        }


@dataclass
class Ambiguity:
    """A config field the LLM resolves from candidates; blocking ones stop generate_config."""

    field: str
    blocking: bool
    candidates: list[Candidate] = dataclass_field(default_factory=list)
    resolution: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for MCP tool output."""
        return {
            "field": self.field,
            "blocking": self.blocking,
            "candidates": [c.to_dict() for c in self.candidates],
            "resolution": self.resolution,
        }


def corroborate(ambiguities: list[Ambiguity], confirmed_config_values: dict[str, dict[str, list[str]]]) -> None:
    """Annotate candidates confirmed entries declare; pre-fill a resolution when exactly one is."""
    for ambiguity in ambiguities:
        declared = confirmed_config_values.get(ambiguity.field, {})
        for candidate in ambiguity.candidates:
            candidate.corroborated_by = list(declared.get(candidate.value, []))
        corroborated = [c for c in ambiguity.candidates if c.corroborated_by]
        # Still reviewed: fleet evidence narrows the judgment, the user confirms it.
        if ambiguity.resolution is None and len(corroborated) == 1:
            ambiguity.resolution = {"value": corroborated[0].value, "source": "fleet"}


# A channel key's meaning lives in parser.yaml, not modem.yaml; this prefix
# addresses it (ONBOARDING_SPEC § Ambiguities, Channel key meanings).
PARSER_PATH_PREFIX = "parser."


def parser_path(section: str, key: str) -> str:
    """The ambiguity path for a channel JSON key in a parser.yaml section."""
    return f"{PARSER_PATH_PREFIX}{section}.{key}"


def split_parser_path(path: str) -> tuple[str, str] | None:
    """The (section, key) a parser path names, or None for a modem.yaml path."""
    if not path.startswith(PARSER_PATH_PREFIX):
        return None
    # The key is the rest of the path, so a dotted wire key survives.
    section, _, key = path[len(PARSER_PATH_PREFIX) :].partition(".")
    return section, key
