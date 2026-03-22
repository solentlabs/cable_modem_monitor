"""HTMLTableTransposedParser — extract channel data from transposed HTML tables.

Rows are metrics, columns are channels. The parser pivots the data:
for each column index, it collects values from all metric rows to build
one channel dict.

Parameterized by a single ``TransposedTableDefinition`` from parser.yaml.
The coordinator handles multi-table orchestration and merge_by.

See PARSING_SPEC.md HTMLTableTransposedParser section.
"""

from __future__ import annotations

import logging
from typing import Any

from bs4 import Tag

from ..models.parser_config.common import (
    ChannelTypeConfig,
    ChannelTypeFixed,
    ChannelTypeMap,
    RowMapping,
)
from ..models.parser_config.transposed import TransposedTableDefinition
from .base import BaseParser
from .table_selector import find_table
from .type_conversion import convert_value

_logger = logging.getLogger(__name__)


class HTMLTableTransposedParser(BaseParser):
    """Extract channel data from a single transposed HTML table.

    Each instance handles one ``TransposedTableDefinition`` (one table).
    The caller orchestrates multi-table sections.

    Args:
        resource: URL path key in the resource dict.
        table: Transposed table definition from parser.yaml.
    """

    def __init__(self, resource: str, table: TransposedTableDefinition) -> None:
        self._resource = resource
        self._table = table

    def parse(self, resources: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract channels from the configured transposed table.

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

        # Build label → data cells map from table rows.
        label_map = _build_label_map(table_el)
        if not label_map:
            _logger.warning("No data rows found in transposed table")
            return []

        # Determine channel count from the first matched row.
        channel_count = _detect_channel_count(label_map, self._table.rows)
        if channel_count == 0:
            return []

        # Pivot: for each column index, build one channel dict.
        channels: list[dict[str, Any]] = []
        for col_idx in range(channel_count):
            channel = _extract_channel(label_map, self._table.rows, col_idx)
            if channel is None:
                continue

            _apply_channel_type(channel, self._table.channel_type)
            channels.append(channel)

        return channels


def _build_label_map(table_el: Tag) -> dict[str, list[Tag]]:
    """Build a mapping from row label text to data cells.

    The first cell in each row is the label; remaining cells are
    channel values. Labels are lowercased for case-insensitive matching.

    Returns:
        Dict of lowercase label → list of data cells (excluding the label cell).
    """
    label_map: dict[str, list[Tag]] = {}
    for row in table_el.find_all("tr"):
        # recursive=False: only direct child cells, not cells inside
        # nested tables within a cell (e.g., SB6141 "Power Level" row
        # has a nested <TABLE> with explanatory text in the label cell).
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue

        label_text = cells[0].get_text(strip=True).lower()
        if not label_text:
            continue

        # Data cells are everything after the label cell
        label_map[label_text] = list(cells[1:])

    return label_map


def _detect_channel_count(
    label_map: dict[str, list[Tag]],
    rows: list[RowMapping],
) -> int:
    """Determine channel count from the first matched row mapping.

    Uses the first RowMapping whose label matches a row in the table.
    """
    for row_def in rows:
        label_lower = row_def.label.lower()
        for map_label, cells in label_map.items():
            if label_lower in map_label:
                return len(cells)
    return 0


def _extract_channel(
    label_map: dict[str, list[Tag]],
    rows: list[RowMapping],
    col_idx: int,
) -> dict[str, Any] | None:
    """Extract one channel dict from column ``col_idx`` across all rows.

    For each RowMapping, finds the matching row by label substring match
    and extracts the cell at the given column index.

    Returns:
        Channel dict, or ``None`` if no fields could be extracted.
    """
    channel: dict[str, Any] = {}

    for row_def in rows:
        label_lower = row_def.label.lower()
        matched_cells: list[Tag] | None = None

        for map_label, cells in label_map.items():
            if label_lower in map_label:
                matched_cells = cells
                break

        if matched_cells is None or col_idx >= len(matched_cells):
            continue

        raw_text = matched_cells[col_idx].get_text(strip=True)
        value = convert_value(
            raw_text,
            row_def.type,
            unit=row_def.unit,
            map_config=row_def.map,
        )

        if value is not None:
            channel[row_def.field] = value

    return channel if channel else None


def _apply_channel_type(
    channel: dict[str, Any],
    channel_type_config: ChannelTypeConfig | None,
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
