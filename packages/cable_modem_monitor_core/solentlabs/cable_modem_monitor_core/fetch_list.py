"""Fetch list derivation from parser.yaml config and parser.py.

Collects unique resource paths and their formats from parser.yaml
sections, merged with the paths a parser.py PostProcessor declares
via its ``resources`` attribute. The fetch list drives what the
resource loaders request, and what the parser coordinator expects to
find in the resource dict — it sits above both rather than inside
either, so the two cannot disagree about what was asked for.

See RESOURCE_LOADING_SPEC.md Fetch List Derivation section.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .models.parser_config import ParserConfig


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
        method: Request method, from parser.yaml ``requests``; GET
            when the path has no declared request.
        form: Form fields a POST sends, in declaration order.
    """

    path: str
    format: str
    encoding: str = ""
    method: Literal["GET", "POST"] = "GET"
    # Pairs, not a dict, so the frozen target stays hashable.
    form: tuple[tuple[str, str], ...] = ()


def collect_fetch_targets(
    config: ParserConfig,
    post_processor: object | None = None,
) -> list[ResourceTarget]:
    """Collect unique fetch targets from parser.yaml and parser.py.

    Walks all sections (downstream, upstream, system_info) and
    extracts ``(path, format, encoding)`` tuples. Deduplicates by
    path — the first format seen for a path wins, so parser.yaml
    declarations win when parser.py declares the same path.

    HNAP sections are skipped (HNAP uses batched SOAP, not per-page
    fetches).

    Each target carries the request parser.yaml ``requests`` declares
    for its path, GET when none. A ``requests`` key no target reads
    raises ``ValueError``.

    Args:
        config: Validated ``ParserConfig`` instance.
        post_processor: Optional parser.py ``PostProcessor`` instance.
            Duck-typed: a ``resources`` dict (URL path → format)
            declares the resources its hooks read, merged into the
            fetch list. See PARSING_SPEC § parser.py — Post-Processing
            Hooks.

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

    _add_post_processor_resources(post_processor, seen_paths)
    _apply_declared_requests(config, seen_paths)

    return list(seen_paths.values())


def _apply_declared_requests(
    config: ParserConfig,
    seen_paths: dict[str, ResourceTarget],
) -> None:
    """Attach each parser.yaml ``requests`` entry to the target for its path."""
    # The check lives here, not on ParserConfig, because only this merge
    # sees parser.py resources too. A key nothing reads would otherwise
    # be dropped silently, and the page it names fetched with GET.
    unread = sorted(path for path in config.requests if path not in seen_paths)
    if unread:
        raise ValueError(f"parser.yaml requests declares paths no section or parser.py resource reads: {unread}")
    for path, request in config.requests.items():
        seen_paths[path] = replace(
            seen_paths[path],
            method=request.method,
            form=tuple(request.form.items()),
        )


def _add_post_processor_resources(
    post_processor: object | None,
    seen_paths: dict[str, ResourceTarget],
) -> None:
    """Merge parser.py ``resources`` declarations into the fetch list."""
    # A wrongly declared attribute fails fast at startup — silently
    # skipping it would surface later as hooks reading absent resources.
    declared = getattr(post_processor, "resources", None)
    if declared is None:
        return
    if not isinstance(declared, dict) or not all(
        isinstance(path, str) and isinstance(fmt, str) for path, fmt in declared.items()
    ):
        raise TypeError("parser.py resources must be a dict of URL path -> format (str -> str)")
    for path, fmt in declared.items():
        if path not in seen_paths:
            seen_paths[path] = ResourceTarget(path=path, format=fmt)


def _add_section_target(
    section: object | None,
    seen_paths: dict[str, ResourceTarget],
) -> None:
    """Extract resource target(s) from a section and add if unique.

    Handles single-resource sections (HTML table, JSON flat form, etc.),
    multi-resource XML tables, and per-array JSON resources.
    """
    if section is None:
        return

    fmt = getattr(section, "format", "")
    if fmt == "hnap":
        return

    encoding: str = getattr(section, "encoding", "")

    # Single-resource sections (table, json flat form, javascript, etc.)
    resource: str = getattr(section, "resource", "")
    if resource:
        if resource not in seen_paths:
            seen_paths[resource] = ResourceTarget(
                path=resource,
                format=fmt,
                encoding=encoding,
            )
        return

    # Multi-resource: XML tables or JSON arrays with per-item resources
    _add_child_targets(section, "tables", fmt, "", seen_paths)
    _add_child_targets(section, "arrays", fmt, encoding, seen_paths)


def _add_child_targets(
    section: object,
    attr: str,
    fmt: str,
    encoding: str,
    seen_paths: dict[str, ResourceTarget],
) -> None:
    """Collect per-child resources from tables or arrays lists."""
    children: list[object] | None = getattr(section, attr, None)
    if not children:
        return
    for child in children:
        child_resource: str = getattr(child, "resource", "")
        if child_resource and child_resource not in seen_paths:
            seen_paths[child_resource] = ResourceTarget(
                path=child_resource,
                format=fmt,
                encoding=encoding,
            )
