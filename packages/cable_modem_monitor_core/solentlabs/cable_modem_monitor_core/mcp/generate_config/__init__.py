"""Config Generation Tool — MCP tool.

Takes analysis result (from ``analyze_har``) plus metadata and produces
modem.yaml and parser.yaml content. Runs Pydantic validation and
cross-file consistency checks before returning.

Does NOT write files — returns content for the caller to review and place.

Per ONBOARDING_SPEC.md ``generate_config`` tool contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...validation.cross_file import validate_cross_file
from .modem import build_modem_dict
from .parser import build_parser_dict
from .validation import to_yaml, validate_modem, validate_parser


@dataclass
class GenerateConfigResult:
    """Result of config generation."""

    modem_yaml: str
    parser_yaml: str | None
    parser_py: str | None
    validation: ValidationResult


@dataclass
class ValidationResult:
    """Validation outcome for generated configs."""

    valid: bool
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for MCP tool output."""
        return {"valid": self.valid, "errors": self.errors}


def generate_config(
    analysis: dict[str, Any],
    metadata: dict[str, Any],
) -> GenerateConfigResult:
    """Generate modem.yaml and parser.yaml from analysis output.

    Args:
        analysis: Dict from ``AnalysisResult.to_dict()`` — contains
            transport, auth, session, actions, and sections.
        metadata: Caller-provided metadata — manufacturer, model,
            hardware, status, attribution, isps, etc.

    Returns:
        GenerateConfigResult with YAML strings and validation outcome.
    """
    errors: list[str] = []

    # Build modem.yaml dict
    modem_dict = build_modem_dict(analysis, metadata)

    # Build parser.yaml dict (None if no sections)
    sections = analysis.get("sections")
    parser_dict = build_parser_dict(sections) if sections else None

    # Validate via Pydantic
    modem_config = validate_modem(modem_dict, errors)
    parser_config = validate_parser(parser_dict, errors) if parser_dict else None

    # Cross-file checks (only if both validated)
    if modem_config and parser_config:
        cross_errors = validate_cross_file(modem_config, parser_config)
        errors.extend(cross_errors)

    # Serialize to YAML
    modem_yaml = to_yaml(modem_dict)
    parser_yaml = to_yaml(parser_dict) if parser_dict else None

    return GenerateConfigResult(
        modem_yaml=modem_yaml,
        parser_yaml=parser_yaml,
        parser_py=None,
        validation=ValidationResult(valid=len(errors) == 0, errors=errors),
    )
