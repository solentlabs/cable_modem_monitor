"""Phase 5-6 dispatcher - format detection and section assembly.

Routes to transport-specific modules (http / hnap) for format
classification, then delegates to mapping and mapping.system_info
for Phase 6 extraction. Assembles the ``sections`` output dict.

Per docs/ONBOARDING_SPEC.md Phases 5-6.
"""

from __future__ import annotations

from typing import Any

from ...validation.har_utils import WARNING_PREFIX
from ..mapping import extract_section_mappings
from ..mapping.system_info import detect_system_info
from .hnap import detect_hnap_sections
from .http import (
    analyze_page,
    classify_page_format,
    identify_data_pages,
)
from .table_analysis import (
    detect_row_start,
    detect_table_direction,
    detect_table_selector,
)
from .types import PageAnalysis


def detect_sections(
    entries: list[dict[str, Any]],
    transport: str,
    warnings: list[str],
    hard_stops: list[str],
) -> dict[str, Any]:
    """Run Phases 5-6: format detection, field mapping, section assembly.

    Args:
        entries: HAR ``log.entries`` list.
        transport: Detected transport ("http" or "hnap").
        warnings: Mutable list to append warnings to.
        hard_stops: Mutable list to append hard stops to.

    Returns:
        Sections dict with downstream, upstream, and system_info keys.
        Each section uses format-agnostic ``mappings``.
    """
    if transport == "hnap":
        return detect_hnap_sections(entries, warnings, hard_stops)

    return _detect_http_sections(entries, warnings, hard_stops)


def _detect_http_sections(
    entries: list[dict[str, Any]],
    warnings: list[str],
    hard_stops: list[str],
) -> dict[str, Any]:
    """Detect HTTP format sections from data pages.

    Identifies data pages, classifies format per page, extracts field
    mappings for channel sections, and detects system_info sources.
    """
    data_pages = identify_data_pages(entries)
    if not data_pages:
        warnings.append(f"{WARNING_PREFIX} No data pages found in HAR. " "Cannot detect format or field mappings.")
        return {}

    # Phase 5: Analyze each data page
    page_analyses: list[PageAnalysis] = []
    for entry in data_pages:
        page = analyze_page(entry)
        page_analyses.append(page)

    # Phase 5-6: Assemble channel sections from table/JS/JSON pages
    sections: dict[str, Any] = {}
    _assemble_channel_sections(page_analyses, sections, warnings)

    # Phase 6: Detect system_info sources
    system_info = detect_system_info(page_analyses, warnings)
    if system_info:
        sections["system_info"] = system_info.to_dict()

    return sections


def _assemble_channel_sections(
    pages: list[PageAnalysis],
    sections: dict[str, Any],
    warnings: list[str],
) -> None:
    """Assemble downstream and upstream sections from page analyses."""
    for page in pages:
        fmt = classify_page_format(page)

        if fmt == "json":
            _assemble_json_sections(page, sections, warnings)
        elif fmt == "javascript":
            _assemble_js_sections(page, sections, warnings)
        elif fmt in ("table", "table_transposed"):
            _assemble_table_sections(page, fmt, sections, warnings)


def _assemble_table_sections(
    page: PageAnalysis,
    fmt: str,
    sections: dict[str, Any],
    warnings: list[str],
) -> None:
    """Assemble channel sections from HTML table pages."""
    for table in page.tables:
        direction = detect_table_direction(table)
        if direction == "unknown":
            warnings.append(
                f"{WARNING_PREFIX} Cannot determine direction for table "
                f"on {page.resource} (index {table.table_index}). "
                "Manual review required."
            )
            continue

        # Skip if section already populated (first table wins)
        if direction in sections:
            continue

        selector = detect_table_selector(table)
        row_start = detect_row_start(table)

        # Phase 6: Extract field mappings
        section = extract_section_mappings(
            fmt=fmt,
            table=table,
            resource=page.resource,
            direction=direction,
            warnings=warnings,
        )

        if section is None:
            continue

        section.selector = selector
        section.row_start = row_start
        sections[direction] = section.to_dict()


def _assemble_js_sections(
    page: PageAnalysis,
    sections: dict[str, Any],
    warnings: list[str],
) -> None:
    """Assemble channel sections from JavaScript-embedded data."""
    for js_func in page.js_functions:
        # Infer direction from function name
        direction = _direction_from_js_name(js_func.name)
        if direction == "unknown":
            warnings.append(
                f"{WARNING_PREFIX} Cannot determine direction for JS function " f"'{js_func.name}' on {page.resource}."
            )
            continue

        # Skip if section already populated
        if direction in sections:
            # Append as additional function (e.g., OFDM after QAM)
            # For now, only the first function per direction is used
            continue

        section = extract_section_mappings(
            fmt="javascript",
            js_function=js_func,
            resource=page.resource,
            direction=direction,
            warnings=warnings,
        )

        if section is None:
            continue

        sections[direction] = section.to_dict()


def _assemble_json_sections(
    page: PageAnalysis,
    sections: dict[str, Any],
    warnings: list[str],
) -> None:
    """Assemble channel sections from JSON API responses."""
    if page.json_data is None:
        return

    section = extract_section_mappings(
        fmt="json",
        json_data=page.json_data,
        resource=page.resource,
        warnings=warnings,
    )

    if section is None:
        return

    # Infer direction from resource path or JSON structure
    direction = _direction_from_resource(page.resource)
    if direction == "unknown":
        direction = _direction_from_json(page.json_data)

    if direction == "unknown":
        warnings.append(
            f"{WARNING_PREFIX} Cannot determine direction for JSON data " f"on {page.resource}. Manual review required."
        )
        return

    if direction not in sections:
        sections[direction] = section.to_dict()


def _direction_from_js_name(name: str) -> str:
    """Infer downstream/upstream from JS function name."""
    lower = name.lower()
    if "ds" in lower or "downstream" in lower:
        return "downstream"
    if "us" in lower or "upstream" in lower:
        return "upstream"
    return "unknown"


def _direction_from_resource(resource: str) -> str:
    """Infer downstream/upstream from resource path."""
    lower = resource.lower()
    if "downstream" in lower:
        return "downstream"
    if "upstream" in lower:
        return "upstream"
    return "unknown"


def _direction_from_json(data: dict[str, Any]) -> str:
    """Infer downstream/upstream from JSON structure keys."""
    for key in data:
        lower = key.lower()
        if "downstream" in lower:
            return "downstream"
        if "upstream" in lower:
            return "upstream"
    return "unknown"
