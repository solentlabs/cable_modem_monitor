"""Row filter detection for field mapping.

Detects lock_status and zero-frequency filters from table data
to exclude inactive channels.

Per docs/ONBOARDING_SPEC.md Phase 6.
"""

from __future__ import annotations

from typing import Any

from ..format.types import DetectedTable
from .types import FieldMapping, find_mapping

# -----------------------------------------------------------------------
# Filter match values
# -----------------------------------------------------------------------

_UNLOCKED_VALUES = frozenset({"not locked", "unlocked", "not_locked"})
_ZERO_FREQ_VALUES = frozenset({"0", "0.0", "0 hz", "0 mhz"})


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------


def detect_filter_table(
    table: DetectedTable,
    mappings: list[FieldMapping],
) -> dict[str, Any] | None:
    """Detect row filter rules from table data.

    Detects lock_status filter and zero-frequency filter.
    """
    filters: dict[str, Any] = {}

    lock_mapping = find_mapping(mappings, "lock_status")
    if (
        lock_mapping is not None
        and lock_mapping.index is not None
        and _column_has_value(table, lock_mapping.index, _UNLOCKED_VALUES)
    ):
        filters["lock_status"] = "locked"

    freq_mapping = find_mapping(mappings, "frequency")
    if (
        freq_mapping is not None
        and freq_mapping.index is not None
        and _column_has_value(table, freq_mapping.index, _ZERO_FREQ_VALUES)
    ):
        filters["frequency"] = {"not": 0}

    return filters if filters else None


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------


def _column_has_value(table: DetectedTable, col_idx: int, match_values: frozenset[str]) -> bool:
    """Check if any row in a table column contains one of the match values."""
    return any(col_idx < len(row) and row[col_idx].strip().lower() in match_values for row in table.rows)
