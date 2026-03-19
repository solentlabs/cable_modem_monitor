"""generate_golden_file MCP tool.

Reads HAR response bodies and uses the ModemParserCoordinator to extract
ModemData. The coordinator is the single extraction path — the same
engine used by the live pipeline and test harness.

See ONBOARDING_SPEC.md generate_golden_file section.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..config_loader import validate_parser_config
from ..parsers.coordinator import ModemParserCoordinator

_logger = logging.getLogger(__name__)


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
        errors.append("No HTML resources found in HAR")

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


def build_resource_dict(har_path: str) -> dict[str, BeautifulSoup]:
    """Build resource dict from HAR response bodies.

    Extracts HTML response bodies from the HAR, keyed by URL path.
    For duplicate paths, last successful (200) response wins.

    Args:
        har_path: Path to the HAR file.

    Returns:
        Dict mapping URL paths to BeautifulSoup objects.
    """
    path = Path(har_path)
    har_data = json.loads(path.read_text(encoding="utf-8"))

    entries = har_data.get("log", {}).get("entries", [])
    resources: dict[str, BeautifulSoup] = {}

    for entry in entries:
        request = entry.get("request", {})
        response = entry.get("response", {})

        status = response.get("status", 0)
        if status != 200:
            continue

        url = request.get("url", "")
        url_path = urlparse(url).path
        if not url_path:
            continue

        content = response.get("content", {})
        text = content.get("text", "")
        if not text:
            continue

        # Decode base64 if needed
        encoding = content.get("encoding", "")
        if encoding == "base64":
            try:
                text = base64.b64decode(text).decode("utf-8", errors="replace")
            except Exception:
                _logger.debug("Failed to base64-decode response for %s", url_path)
                continue

        mime_type = content.get("mimeType", "")
        if _is_html_content(mime_type, text):
            resources[url_path] = BeautifulSoup(text, "html.parser")

    return resources


def _is_html_content(mime_type: str, text: str) -> bool:
    """Check if content is HTML based on MIME type or content sniffing."""
    mime_lower = mime_type.lower()
    if "html" in mime_lower or "text/plain" in mime_lower:
        return True
    # Content sniffing fallback — look for HTML markers
    text_start = text[:500].strip().lower()
    return text_start.startswith(("<!doctype", "<html", "<table", "<head"))
