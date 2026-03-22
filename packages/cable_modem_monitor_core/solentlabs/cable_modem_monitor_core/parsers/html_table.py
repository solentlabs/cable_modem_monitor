"""HTMLTableParser — extract channel data from HTML ``<table>`` elements.

Rows are channels, columns are fields. Parameterized by a single
``TableDefinition`` from parser.yaml. The coordinator (or golden file
tool) handles multi-table orchestration and merge_by.

See PARSING_SPEC.md HTMLTableParser section.
"""

from __future__ import annotations

import logging
from typing import Any

from bs4 import Tag

from ..models.parser_config.common import (
    ChannelTypeFixed,
    ChannelTypeMap,
    ColumnMapping,
)
from ..models.parser_config.table import TableDefinition
from .base import BaseParser
from .filter import passes_filter
from .table_selector import find_table
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

        table_el = find_table(soup, self._table.selector)
        if table_el is None:
            _logger.warning(
                "Table not found with selector type='%s' match='%s'",
                self._table.selector.type,
                self._table.selector.match,
            )
            return []

        rows = table_el.find_all("tr")
        data_rows = rows[self._table.row_start :]

        channels: list[dict[str, Any]] = []
        for row in data_rows:
            cells = row.find_all(["td", "th"])
            channel = _extract_row(cells, self._table.columns)
            if channel is None:
                continue

            _apply_channel_type(channel, self._table.channel_type)

            if not passes_filter(channel, self._table.filter):
                continue

            channels.append(channel)

        return channels


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
) -> None:
    """Apply channel_type to a channel dict.

    Fixed: sets a static value. Map: derives from another field's value.
    Does not overwrite if ``channel_type`` already exists in the channel.
    """
    if channel_type_config is None or "channel_type" in channel:
        return

    if isinstance(channel_type_config, ChannelTypeFixed):
        channel["channel_type"] = channel_type_config.fixed
        return

    if isinstance(channel_type_config, ChannelTypeMap):
        ct_map = channel_type_config
        raw_value = str(channel.get(ct_map.field, ""))

        if raw_value and raw_value in ct_map.map:
            channel["channel_type"] = ct_map.map[raw_value]
        elif raw_value:
            _logger.warning(
                "Unmapped channel_type value: '%s' (known: %s)",
                raw_value,
                list(ct_map.map.keys()),
            )
