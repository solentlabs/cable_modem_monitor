"""ModemParserCoordinator — factory and orchestrator.

Reads parser.yaml config, creates BaseParser instances per section, runs
them, chains parser.py post-processing, and assembles ModemData.

See PARSING_SPEC.md ModemParserCoordinator section.

Format coverage: currently dispatches HTMLTableSection (channels) and
HTMLFieldsSource (system_info). Other formats (JSEmbedded, HNAP, JSON,
Transposed, XML) log a warning and fall through to the post-processor
hook. They will be wired as modems in the catalog require them.
"""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from ..models.parser_config.config import ParserConfig
from ..models.parser_config.system_info import HTMLFieldsSource
from ..models.parser_config.table import HTMLTableSection
from .html_fields import HTMLFieldsParser
from .html_table import HTMLTableParser

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

        Creates one parser per table definition, concatenates primary
        tables, merges companion tables, and invokes the parser.py hook.
        """
        section = getattr(self._config, section_name, None)
        if section is None:
            return self._apply_hook(section_name, [], resources)

        if not isinstance(section, HTMLTableSection):
            _logger.warning(
                "%s: format '%s' not yet supported by coordinator",
                section_name,
                getattr(section, "format", "?"),
            )
            return self._apply_hook(section_name, [], resources)

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

        return self._apply_hook(section_name, primary_channels, resources)

    def _extract_system_info(
        self,
        resources: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract system_info from all configured sources.

        Creates one parser per source, merges results with last-write-wins.
        """
        section = self._config.system_info
        if section is None:
            return self._apply_hook("system_info", {}, resources)

        merged: dict[str, Any] = {}
        for source in section.sources:
            if isinstance(source, HTMLFieldsSource):
                parser = HTMLFieldsParser(source)
                result = parser.parse(resources)
                if isinstance(result, dict):
                    merged.update(result)
            else:
                _logger.warning(
                    "system_info source format '%s' not yet supported",
                    getattr(source, "format", "?"),
                )

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
