"""generate_golden_file MCP tool.

Reads HAR response bodies and uses the ModemParserCoordinator to extract
ModemData. The coordinator is the single extraction path — the same
engine used by the live pipeline and test harness.

See ONBOARDING_SPEC.md generate_golden_file section.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config_loader import validate_parser_config
from ..har import build_resource_dict
from ..parsers.coordinator import ModemParserCoordinator


@dataclass
class GenerateGoldenFileResult:
    """Result from generate_golden_file.

    Attributes:
        golden_file: The extracted ModemData dict.
        channel_counts: Downstream and upstream channel counts.
        system_info_fields: Field names present in system_info.
        errors: Any errors encountered during extraction.
    """

    golden_file: dict[str, Any]
    channel_counts: dict[str, int] = field(default_factory=dict)
    system_info_fields: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def generate_golden_file(
    har_path: str,
    parser_yaml_content: str,
) -> GenerateGoldenFileResult:
    """Generate a golden file from HAR response bodies.

    Loads the HAR, builds a resource dict from response bodies, and
    runs the coordinator to extract ModemData.

    Args:
        har_path: Path to the HAR file.
        parser_yaml_content: parser.yaml content as a YAML string.

    Returns:
        Result with golden_file dict, channel counts, and any errors.
    """
    errors: list[str] = []

    # Load and validate parser.yaml
    try:
        parser_config = _load_parser_yaml(parser_yaml_content)
    except Exception as e:
        return GenerateGoldenFileResult(
            golden_file={},
            errors=[f"Invalid parser.yaml: {e}"],
        )

    # Load HAR and build resource dict
    try:
        resources = build_resource_dict(har_path)
    except Exception as e:
        return GenerateGoldenFileResult(
            golden_file={},
            errors=[f"Failed to load HAR: {e}"],
        )

    if not resources:
        errors.append("No resources found in HAR")

    # Extract via coordinator (single extraction path)
    coordinator = ModemParserCoordinator(parser_config)
    golden = coordinator.parse(resources)

    # Build result
    downstream = golden.get("downstream", [])
    upstream = golden.get("upstream", [])
    system_info = golden.get("system_info", {})

    channel_counts = {
        "downstream": len(downstream),
        "upstream": len(upstream),
    }

    system_info_fields = sorted(system_info.keys()) if system_info else []

    return GenerateGoldenFileResult(
        golden_file=golden,
        channel_counts=channel_counts,
        system_info_fields=system_info_fields,
        errors=errors,
    )


def _load_parser_yaml(content: str) -> Any:
    """Parse and validate parser.yaml content.

    Returns the validated ParserConfig model.
    """
    import yaml

    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        raise ValueError("parser.yaml must be a YAML mapping")
    return validate_parser_config(data)
