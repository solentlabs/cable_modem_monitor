"""ModemParserCoordinator — factory and orchestrator.

Reads parser.yaml config, creates BaseParser instances per section, runs
them, chains parser.py post-processing, and assembles ModemData.

See PARSING_SPEC.md ModemParserCoordinator section.

Channel parser registry maps section config types to parser callables.
Five format types registered: HTMLTable, HNAP, Transposed, JSEmbedded, JSON.

System info source registry maps source config types to parser callables.
Four source types registered: HTMLFields, HNAP, JavaScript, JSON.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from ..models.parser_config.config import ParserConfig
from ..models.parser_config.hnap import HNAPSection
from ..models.parser_config.javascript import JSEmbeddedSection
from ..models.parser_config.json_format import JSONSection
from ..models.parser_config.system_info import (
    HNAPSystemInfoSource,
    HTMLFieldsSource,
    JSONSystemInfoSource,
    JSSystemInfoSource,
)
from ..models.parser_config.table import HTMLTableSection
from ..models.parser_config.transposed import HTMLTableTransposedSection
from .hnap import HNAPParser
from .hnap_fields import HNAPFieldsParser
from .html_fields import HTMLFieldsParser
from .html_table import HTMLTableParser
from .html_table_transposed import HTMLTableTransposedParser
from .js_embedded import JSEmbeddedParser
from .js_system_info import JSSystemInfoParser
from .json_parser import JSONParser
from .json_system_info import JSONSystemInfoParser

_T = TypeVar("_T")
_logger = logging.getLogger(__name__)

# Section names that contain channel data (list[dict] output).
_CHANNEL_SECTIONS = ("downstream", "upstream")

# Hook method names by section.
_HOOK_NAMES = {
    "downstream": "parse_downstream",
    "upstream": "parse_upstream",
    "system_info": "parse_system_info",
}


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


# Maps section config type → parser callable(section, resources) → list[dict]
_CHANNEL_PARSERS: dict[type, Callable[..., list[dict[str, Any]]]] = {
    HTMLTableSection: _parse_html_table_channels,
    HNAPSection: _parse_hnap_channels,
    HTMLTableTransposedSection: _parse_transposed_channels,
    JSEmbeddedSection: _parse_js_embedded_channels,
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


# Maps source config type → parser callable(source, resources) → dict
_SYSINFO_PARSERS: dict[type, Callable[..., dict[str, Any]]] = {
    HTMLFieldsSource: _parse_html_fields_sysinfo,
    HNAPSystemInfoSource: _parse_hnap_sysinfo,
    JSSystemInfoSource: _parse_js_sysinfo,
    JSONSystemInfoSource: _parse_json_sysinfo,
}


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class ModemParserCoordinator:
    """Factory and orchestrator for parser.yaml-driven extraction.

    Creates BaseParser instances from parser.yaml config, runs them per
    section, applies merge_by for companion tables, invokes parser.py
    post-processing hooks, and assembles the final ModemData dict.

    Args:
        config: Validated ParserConfig from parser.yaml.
        post_processor: Optional parser.py post-processor instance.
            Duck-typed: checked for ``parse_downstream``,
            ``parse_upstream``, ``parse_system_info`` methods via hasattr.
    """

    def __init__(
        self,
        config: ParserConfig,
        post_processor: Any = None,
    ) -> None:
        self._config = config
        self._post_processor = post_processor

    def parse(self, resources: dict[str, Any]) -> dict[str, Any]:
        """Run the full extraction pipeline and assemble ModemData.

        Args:
            resources: Resource dict keyed by URL path. Values are
                format-dependent (BeautifulSoup for HTML, dict for JSON).

        Returns:
            ModemData dict with downstream, upstream, and optional
            system_info.
        """
        result: dict[str, Any] = {}

        for section_name in _CHANNEL_SECTIONS:
            result[section_name] = self._extract_channel_section(section_name, resources)

        system_info = self._extract_system_info(resources)
        if system_info:
            result["system_info"] = system_info

        return result

    def _extract_channel_section(
        self,
        section_name: str,
        resources: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Extract channels for a single section.

        Dispatches to the channel parser registry by section config type.
        """
        section = getattr(self._config, section_name, None)
        if section is None:
            return self._apply_hook(section_name, [], resources)

        parser_fn = _CHANNEL_PARSERS.get(type(section))
        if parser_fn is None:
            raise NotImplementedError(f"{type(section).__name__} has no registered channel parser")

        channels = parser_fn(section, resources)
        return self._apply_hook(section_name, channels, resources)

    def _extract_system_info(
        self,
        resources: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract system_info from all configured sources.

        Dispatches to the system info source registry by source config type.
        Merges results with last-write-wins.
        """
        section = self._config.system_info
        if section is None:
            return self._apply_hook("system_info", {}, resources)

        merged: dict[str, Any] = {}
        for source in section.sources:
            parser_fn = _SYSINFO_PARSERS.get(type(source))
            if parser_fn is None:
                raise NotImplementedError(f"{type(source).__name__} has no registered system_info parser")
            merged.update(parser_fn(source, resources))

        return self._apply_hook("system_info", merged, resources)

    def _apply_hook(
        self,
        section_name: str,
        data: _T,
        resources: dict[str, Any],
    ) -> _T:
        """Invoke parser.py post-processing hook if present.

        The hook receives the extraction output and the full resource
        dict. Its return value replaces the extraction output.
        """
        if self._post_processor is None:
            return data

        hook_name = _HOOK_NAMES.get(section_name)
        if hook_name is None:
            return data

        hook = getattr(self._post_processor, hook_name, None)
        if hook is None:
            return data

        _logger.debug("Invoking parser.py hook: %s", hook_name)
        result: _T = hook(data, resources)
        return result


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
