"""Fetch list derivation from parser.yaml config.

Collects unique resource paths and their formats from parser.yaml
sections. The fetch list drives what the HTTP resource loader requests.

See RESOURCE_LOADING_SPEC.md Fetch List Derivation section.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.parser_config import ParserConfig


@dataclass(frozen=True)
class ResourceTarget:
    """A single resource to fetch.

    Attributes:
        path: URL path (e.g., ``/status.html``).
        format: Parser format that determines how to decode the
            response (``table``, ``table_transposed``, ``javascript``,
            ``json``, ``html_fields``).
        encoding: Optional response encoding (e.g., ``base64``).
            Empty string for no special encoding.
    """

    path: str
    format: str
    encoding: str = ""


def collect_fetch_targets(config: ParserConfig) -> list[ResourceTarget]:
    """Collect unique fetch targets from parser.yaml.

    Walks all sections (downstream, upstream, system_info) and
    extracts ``(path, format, encoding)`` tuples. Deduplicates by
    path — the first format seen for a path wins.

    HNAP sections are skipped (HNAP uses batched SOAP, not per-page
    fetches).

    Args:
        config: Validated ``ParserConfig`` instance.

    Returns:
        List of unique ``ResourceTarget`` objects to fetch.
    """
    seen_paths: dict[str, ResourceTarget] = {}

    # Channel sections (downstream, upstream)
    for section_name in ("downstream", "upstream"):
        section = getattr(config, section_name, None)
        _add_section_target(section, seen_paths)

    # System info sources
    if config.system_info is not None:
        for source in config.system_info.sources:
            _add_section_target(source, seen_paths)

    return list(seen_paths.values())


def _add_section_target(
    section: object | None,
    seen_paths: dict[str, ResourceTarget],
) -> None:
    """Extract resource target(s) from a section and add if unique.

    Handles both single-resource sections (HTML table, JSON, etc.)
    and multi-resource sections (XML tables where each table has its
    own resource).
    """
    if section is None:
        return

    fmt = getattr(section, "format", "")
    if fmt == "hnap":
        return

    # Single-resource sections (table, json, javascript, etc.)
    resource: str = getattr(section, "resource", "")
    if resource:
        if resource not in seen_paths:
            encoding: str = getattr(section, "encoding", "")
            seen_paths[resource] = ResourceTarget(
                path=resource,
                format=fmt,
                encoding=encoding,
            )
        return

    # Multi-resource sections (XML tables — each table has its own resource)
    tables: list[object] | None = getattr(section, "tables", None)
    if tables:
        for table in tables:
            table_resource: str = getattr(table, "resource", "")
            if table_resource and table_resource not in seen_paths:
                seen_paths[table_resource] = ResourceTarget(
                    path=table_resource,
                    format=fmt,
                )
