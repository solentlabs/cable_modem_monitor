"""HTMLTableParser — extract channel data from HTML ``<table>`` elements.

Rows are channels, columns are fields. Parameterized by a single
``TableDefinition`` from parser.yaml. The coordinator (or golden file
tool) handles multi-table orchestration and merge_by.

See PARSING_SPEC.md HTMLTableParser section.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..models.parser_config.common import (
    ChannelTypeFixed,
    ChannelTypeMap,
    ColumnMapping,
    FilterValue,
    TableSelector,
)
from ..models.parser_config.table import TableDefinition
from .base import BaseParser
from .type_conversion import convert_value

_logger = logging.getLogger(__name__)


class HTMLTableParser(BaseParser):
    """Extract channel data from a single HTML table.

    Each instance handles one ``TableDefinition`` (one table element).
    The caller orchestrates multi-table sections.

    Args:
        resource: URL path key in the resource dict.
        table: Table definition from parser.yaml.
    """

    def __init__(self, resource: str, table: TableDefinition) -> None:
        self._resource = resource
        self._table = table

    def parse(self, resources: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract channels from the configured table.

        Args:
            resources: Resource dict (path -> BeautifulSoup).

        Returns:
            List of channel dicts with converted field values.
        """
        soup = resources.get(self._resource)
        if soup is None:
            _logger.warning("Resource '%s' not found", self._resource)
            return []

        table_el = _find_table(soup, self._table.selector)
        if table_el is None:
            _logger.warning(
                "Table not found with selector type='%s' match='%s'",
                self._table.selector.type,
                self._table.selector.match,
            )
            return []

        rows = table_el.find_all("tr")
        data_rows = rows[self._table.skip_rows :]

        channels: list[dict[str, Any]] = []
        for row in data_rows:
            cells = row.find_all(["td", "th"])
            channel = _extract_row(cells, self._table.columns)
            if channel is None:
                continue

            _apply_channel_type(channel, self._table.channel_type, cells)

            if not _passes_filter(channel, self._table.filter):
                continue

            channels.append(channel)

        return channels


def _find_table(soup: BeautifulSoup | Tag, selector: TableSelector) -> Tag | None:
    """Find a ``<table>`` element using the configured selector.

    Supports fallback chaining — if the primary selector fails and a
    fallback is configured, tries the fallback.

    Args:
        soup: Parsed HTML document or subtree.
        selector: Table selector configuration.

    Returns:
        The matched ``<table>`` element, or ``None``.
    """
    table = _find_table_by_type(soup, selector)
    if table is not None:
        return table

    if selector.fallback is not None:
        return _find_table(soup, selector.fallback)

    return None


def _find_table_by_type(soup: BeautifulSoup | Tag, selector: TableSelector) -> Tag | None:
    """Dispatch to type-specific table finder."""
    sel_type = selector.type
    match = selector.match

    if sel_type == "header_text":
        return _find_by_header_text(soup, str(match))
    if sel_type == "css":
        return _find_by_css(soup, str(match))
    if sel_type == "id":
        return _find_by_id(soup, str(match))
    if sel_type == "nth":
        return _find_by_nth(soup, int(str(match)))
    if sel_type == "attribute":
        if isinstance(match, dict):
            return _find_by_attribute(soup, match)
        return None

    _logger.warning("Unknown selector type: %s", sel_type)
    return None


def _find_by_header_text(soup: BeautifulSoup | Tag, text: str) -> Tag | None:
    """Find table by header cell text content."""
    for tag_name in ("th", "td"):
        for cell in soup.find_all(tag_name):
            cell_text = cell.get_text(strip=True)
            if text.lower() in cell_text.lower():
                table = cell.find_parent("table")
                if table is not None:
                    return table
    return None


def _find_by_css(soup: BeautifulSoup | Tag, css_selector: str) -> Tag | None:
    """Find table by CSS selector."""
    result = soup.select_one(css_selector)
    if result is not None and isinstance(result, Tag):
        if result.name == "table":
            return result
        # If the selector hit a non-table, look for parent table
        table = result.find_parent("table")
        if table is not None:
            return table
    return None


def _find_by_id(soup: BeautifulSoup | Tag, element_id: str) -> Tag | None:
    """Find table by element id attribute."""
    element = soup.find(id=element_id)
    if element is None:
        return None
    if isinstance(element, Tag) and element.name == "table":
        return element
    if isinstance(element, Tag):
        return element.find_parent("table")
    return None


def _find_by_nth(soup: BeautifulSoup | Tag, index: int) -> Tag | None:
    """Find the Nth table on the page (0-based)."""
    tables = soup.find_all("table")
    if 0 <= index < len(tables):
        result = tables[index]
        if isinstance(result, Tag):
            return result
    return None


def _find_by_attribute(soup: BeautifulSoup | Tag, attrs: Mapping[str, str]) -> Tag | None:
    """Find table by element attributes."""
    # Search for any element with matching attributes, then find parent table
    element = soup.find(attrs=dict(attrs))
    if element is None:
        return None
    if isinstance(element, Tag) and element.name == "table":
        return element
    if isinstance(element, Tag):
        return element.find_parent("table")
    return None


def _extract_row(
    cells: list[Tag],
    columns: list[ColumnMapping],
) -> dict[str, Any] | None:
    """Extract field values from a table row's cells.

    Returns ``None`` if the row has fewer cells than any column index
    (likely a header or malformed row).
    """
    channel: dict[str, Any] = {}

    for col in columns:
        if col.index >= len(cells):
            return None

        raw_text = cells[col.index].get_text(strip=True)
        value = convert_value(
            raw_text,
            col.type,
            unit=col.unit,
            map_config=col.map,
        )

        if value is not None:
            channel[col.field] = value

    return channel if channel else None


def _apply_channel_type(
    channel: dict[str, Any],
    channel_type_config: Any | None,
    cells: list[Tag],
) -> None:
    """Apply channel_type to a channel dict.

    Fixed: sets a static value. Map: looks up a field value in the map.
    Does not overwrite if ``channel_type`` already exists in the channel.
    """
    if channel_type_config is None or "channel_type" in channel:
        return

    if isinstance(channel_type_config, ChannelTypeFixed):
        channel["channel_type"] = channel_type_config.fixed
        return

    if isinstance(channel_type_config, ChannelTypeMap):
        ct_map = channel_type_config
        raw_value: str | None = None

        if ct_map.field is not None:
            # Look up by field name in the already-extracted channel
            raw_value = str(channel.get(ct_map.field, ""))
        elif ct_map.index is not None and ct_map.index < len(cells):
            # Look up by column index in raw cells
            raw_value = cells[ct_map.index].get_text(strip=True)

        if raw_value and raw_value in ct_map.map:
            channel["channel_type"] = ct_map.map[raw_value]
        elif raw_value:
            _logger.warning(
                "Unmapped channel_type value: '%s' (known: %s)",
                raw_value,
                list(ct_map.map.keys()),
            )


def _passes_filter(
    channel: dict[str, Any],
    filter_rules: dict[str, FilterValue],
) -> bool:
    """Check if a channel passes all filter rules.

    Filters apply after type conversion. A channel that fails any
    filter condition is excluded.

    Rules:
    - ``str`` value: keep if ``channel[field] == value``
    - ``dict`` with ``"not"`` key: keep if ``channel[field] != value``
    """
    for field, rule in filter_rules.items():
        actual = channel.get(field)

        if isinstance(rule, dict):
            # {"not": value} — exclude if equal
            not_value = rule.get("not")
            if actual == not_value:
                return False
        else:
            # Equality — keep only if equal
            if actual != rule:
                return False

    return True
