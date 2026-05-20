"""Tests for the dispatcher's row-counter filter.

Covers ``_remove_row_counters`` and ``_is_row_counter`` — defensive
post-processing that drops table columns whose values are perfectly
sequential 1..N (those are display counters, not real channel IDs).
"""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.format.types import (
    DetectedTable,
)
from solentlabs.cable_modem_monitor_catalog_tools.analysis.mapping.dispatcher import (
    _is_row_counter,
    _remove_row_counters,
)
from solentlabs.cable_modem_monitor_catalog_tools.analysis.mapping.types import (
    FieldMapping,
)


def _table(rows: list[list[str]]) -> DetectedTable:
    """Build a minimal DetectedTable with the given data rows."""
    return DetectedTable(
        table_id="t",
        css_class="",
        headers=["a", "b"],
        rows=rows,
        preceding_text="",
        title_row_text="",
        table_index=0,
    )


# -----------------------------------------------------------------------
# _is_row_counter — sequential detection with trailing summary tolerance
# -----------------------------------------------------------------------


# ┌──────────────────────────────────┬────────────┬───────────┬──────────┐
# │ scenario                         │ col_index  │ row_count │ expected │
# ├──────────────────────────────────┼────────────┼───────────┼──────────┤
# │ perfect 1..3 sequence            │ 0          │ 3         │ True     │
# │ break in sequence (1,3)          │ 0          │ 2         │ False    │
# │ trailing 'Total' summary         │ 0          │ 3         │ True     │
# │ column index out of range        │ 5          │ 2         │ False    │
# │ single row (below 2-row min)     │ 0          │ 1         │ False    │
# └──────────────────────────────────┴────────────┴───────────┴──────────┘
#
# fmt: off
ROW_COUNTER_CASES = [
    # (description,                   data_rows,                                    col_index, row_count, expected)
    ("perfect_sequence",               [["1", "x"], ["2", "y"], ["3", "z"]],         0,         3,         True),
    ("break_in_sequence",              [["1", "x"], ["3", "y"]],                     0,         2,         False),
    ("trailing_summary_tolerated",     [["1", "x"], ["2", "y"], ["Total", "z"]],     0,         3,         True),
    ("col_index_out_of_range",         [["1"], ["2"]],                               5,         2,         False),
    ("single_row_below_min_threshold", [["1", "x"]],                                 0,         1,         False),
]
# fmt: on


@pytest.mark.parametrize(
    "data_rows,col_index,row_count,expected",
    [(c[1], c[2], c[3], c[4]) for c in ROW_COUNTER_CASES],
    ids=[c[0] for c in ROW_COUNTER_CASES],
)
def test_is_row_counter(data_rows: list[list[str]], col_index: int, row_count: int, expected: bool) -> None:
    """A column is a row counter only when values form a perfect 1..N+ sequence."""
    assert _is_row_counter(col_index, data_rows, row_count) is expected


# -----------------------------------------------------------------------
# _remove_row_counters — duplicate-field disambiguation
# -----------------------------------------------------------------------


def test_remove_row_counters_no_duplicates_passes_through() -> None:
    """No field appears twice → mappings returned unchanged."""
    mappings = [
        FieldMapping(field="channel_id", type="int", index=0),
        FieldMapping(field="frequency", type="int", index=1),
    ]
    table = _table([["1", "500"], ["2", "506"]])
    assert _remove_row_counters(mappings, table) is mappings


def test_remove_row_counters_no_data_rows_passes_through() -> None:
    """Table has duplicates but no data rows → return unchanged."""
    mappings = [
        FieldMapping(field="channel_id", type="int", index=0),
        FieldMapping(field="channel_id", type="int", index=1),
    ]
    table = _table([])
    result = _remove_row_counters(mappings, table)
    assert result is mappings


def test_remove_row_counters_keeps_real_data_remaps_counter() -> None:
    """A channel_id row counter (1,2,3) alongside a real id column (101,102,103)
    is remapped to channel_number (not dropped) — it's the display row number."""
    mappings = [
        # Column 0: counter values 1,2,3 → remapped to channel_number
        FieldMapping(field="channel_id", type="int", index=0),
        # Column 1: real channel IDs 101,102,103 → kept as channel_id
        FieldMapping(field="channel_id", type="int", index=1),
    ]
    table = _table([["1", "101"], ["2", "102"], ["3", "103"]])
    result = _remove_row_counters(mappings, table)
    assert len(result) == 2
    assert result[0].field == "channel_number"
    assert result[0].index == 0
    assert result[1].field == "channel_id"
    assert result[1].index == 1


def test_remove_row_counters_all_counters_keeps_highest_index() -> None:
    """All mappings look like counters (e.g., real IDs happen to be 1..N) → keep highest column index."""
    mappings = [
        FieldMapping(field="channel_id", type="int", index=0),
        FieldMapping(field="channel_id", type="int", index=2),
        FieldMapping(field="channel_id", type="int", index=5),
    ]
    # All three columns contain perfect 1..3 sequences
    table = _table([["1", "x", "1", "y", "z", "1"], ["2", "x", "2", "y", "z", "2"], ["3", "x", "3", "y", "z", "3"]])
    result = _remove_row_counters(mappings, table)
    assert len(result) == 1
    # Highest column index wins (the explicit "Channel ID" column)
    assert result[0].index == 5
