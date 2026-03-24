"""Parser registries — type-to-callable dispatch tables.

Maps parser.yaml section config types to parser callables. Six channel
format types and four system info source types are registered.

Channel parsers: ``(section, resources) -> list[dict]``
System info parsers: ``(source, resources) -> dict``

See PARSING_SPEC.md Parser Registry section.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..models.parser_config.hnap import HNAPSection
from ..models.parser_config.javascript import JSEmbeddedSection
from ..models.parser_config.js_json import JSJsonSection
from ..models.parser_config.json_format import JSONSection
from ..models.parser_config.system_info import (
    HNAPSystemInfoSource,
    HTMLFieldsSource,
    JSONSystemInfoSource,
    JSSystemInfoSource,
)
from ..models.parser_config.table import HTMLTableSection
from ..models.parser_config.transposed import HTMLTableTransposedSection
from .formats.hnap import HNAPParser
from .formats.hnap_fields import HNAPFieldsParser
from .formats.html_fields import HTMLFieldsParser
from .formats.html_table import HTMLTableParser
from .formats.html_table_transposed import HTMLTableTransposedParser
from .formats.js_embedded import JSEmbeddedParser
from .formats.js_json_parser import JSJsonParser
from .formats.js_system_info import JSSystemInfoParser
from .formats.json_parser import JSONParser
from .formats.json_system_info import JSONSystemInfoParser

# ---------------------------------------------------------------------------
# Channel parser registry
# ---------------------------------------------------------------------------


def _parse_hnap_channels(
    section: Any,
    resources: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse channels from an HNAP section."""
    hnap_parser = HNAPParser(section)
    channels = hnap_parser.parse(resources)
    if not isinstance(channels, list):
        return []
    return channels


def _parse_html_table_channels(
    section: HTMLTableSection,
    resources: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse channels from HTML table section(s) with merge_by support."""
    primary_channels: list[dict[str, Any]] = []
    companion_tables: list[tuple[list[dict[str, Any]], list[str]]] = []

    for table_def in section.tables:
        parser = HTMLTableParser(section.resource, table_def)
        channels = parser.parse(resources)
        if not isinstance(channels, list):
            continue

        if table_def.merge_by is not None:
            companion_tables.append((channels, table_def.merge_by))
        else:
            primary_channels.extend(channels)

    for companion_channels, merge_by in companion_tables:
        _merge_channels(primary_channels, companion_channels, merge_by)

    return primary_channels


def _parse_transposed_channels(
    section: HTMLTableTransposedSection,
    resources: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse channels from transposed HTML table section(s) with merge_by support."""
    # Normalize flat form to tables list
    if section.tables is not None:
        tables = section.tables
    else:
        from ..models.parser_config.transposed import TransposedTableDefinition

        assert section.selector is not None and section.rows is not None
        tables = [
            TransposedTableDefinition(
                selector=section.selector,
                rows=section.rows,
                channel_type=section.channel_type,
            )
        ]

    primary_channels: list[dict[str, Any]] = []
    companion_tables: list[tuple[list[dict[str, Any]], list[str]]] = []

    for table_def in tables:
        parser = HTMLTableTransposedParser(section.resource, table_def)
        channels = parser.parse(resources)
        if not isinstance(channels, list):
            continue

        if table_def.merge_by is not None:
            companion_tables.append((channels, table_def.merge_by))
        else:
            primary_channels.extend(channels)

    for companion_channels, merge_by in companion_tables:
        _merge_channels(primary_channels, companion_channels, merge_by)

    return primary_channels


def _parse_js_embedded_channels(
    section: JSEmbeddedSection,
    resources: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse channels from JS-embedded section — all functions concatenated."""
    channels: list[dict[str, Any]] = []
    for func in section.functions:
        parser = JSEmbeddedParser(section.resource, func)
        result = parser.parse(resources)
        if isinstance(result, list):
            channels.extend(result)
    return channels


def _parse_json_channels(
    section: JSONSection,
    resources: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse channels from a JSON API section."""
    parser = JSONParser(section)
    channels = parser.parse(resources)
    if not isinstance(channels, list):
        return []
    return channels


def _parse_js_json_channels(
    section: JSJsonSection,
    resources: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse channels from a js_json section — JSON arrays in JS variables."""
    parser = JSJsonParser(section)
    channels = parser.parse(resources)
    if not isinstance(channels, list):
        return []
    return channels


# Maps section config type -> parser callable(section, resources) -> list[dict]
CHANNEL_PARSERS: dict[type, Callable[..., list[dict[str, Any]]]] = {
    HTMLTableSection: _parse_html_table_channels,
    HNAPSection: _parse_hnap_channels,
    HTMLTableTransposedSection: _parse_transposed_channels,
    JSEmbeddedSection: _parse_js_embedded_channels,
    JSJsonSection: _parse_js_json_channels,
    JSONSection: _parse_json_channels,
}


# ---------------------------------------------------------------------------
# System info source registry
# ---------------------------------------------------------------------------


def _parse_html_fields_sysinfo(
    source: HTMLFieldsSource,
    resources: dict[str, Any],
) -> dict[str, Any]:
    """Parse system_info from HTML label/value pairs."""
    html_si = HTMLFieldsParser(source)
    result = html_si.parse(resources)
    return result if isinstance(result, dict) else {}


def _parse_hnap_sysinfo(
    source: HNAPSystemInfoSource,
    resources: dict[str, Any],
) -> dict[str, Any]:
    """Parse system_info from HNAP response fields."""
    hnap_si = HNAPFieldsParser(source)
    result = hnap_si.parse(resources)
    return result if isinstance(result, dict) else {}


def _parse_js_sysinfo(
    source: JSSystemInfoSource,
    resources: dict[str, Any],
) -> dict[str, Any]:
    """Parse system_info from JS-embedded tagValueList variables."""
    js_si = JSSystemInfoParser(source)
    result = js_si.parse(resources)
    return result if isinstance(result, dict) else {}


def _parse_json_sysinfo(
    source: JSONSystemInfoSource,
    resources: dict[str, Any],
) -> dict[str, Any]:
    """Parse system_info from a JSON API response."""
    json_si = JSONSystemInfoParser(source)
    result = json_si.parse(resources)
    return result if isinstance(result, dict) else {}


# Maps source config type -> parser callable(source, resources) -> dict
SYSINFO_PARSERS: dict[type, Callable[..., dict[str, Any]]] = {
    HTMLFieldsSource: _parse_html_fields_sysinfo,
    HNAPSystemInfoSource: _parse_hnap_sysinfo,
    JSSystemInfoSource: _parse_js_sysinfo,
    JSONSystemInfoSource: _parse_json_sysinfo,
}


# ---------------------------------------------------------------------------
# Merge utility (used by table and transposed factory functions)
# ---------------------------------------------------------------------------


def _merge_channels(
    primary: list[dict[str, Any]],
    merge_table: list[dict[str, Any]],
    merge_by: list[str],
) -> None:
    """Merge fields from a companion table into primary channels.

    Builds a lookup by the declared key fields, then enriches primary
    channels. Primary always wins on field conflicts.

    Per PARSING_SPEC.md Companion Tables (merge_by) section.
    """
    merge_map: dict[tuple[Any, ...], dict[str, Any]] = {}
    for ch in merge_table:
        key = tuple(ch.get(field) for field in merge_by)
        merge_map[key] = ch

    for ch in primary:
        key = tuple(ch.get(field) for field in merge_by)
        extra = merge_map.get(key, {})
        for field, value in extra.items():
            if field not in ch:
                ch[field] = value
