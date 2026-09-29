"""Tests for golden comparison: channels pair by identity first, then by order.

Table-driven: each case is a committed and a generated channel list, and
the matching field count or diff lines the regression must report.
"""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.regression.golden_compare import (
    count_fields,
    count_matching_fields,
    diff_golden_files,
)


def _ch(channel_id: int | None, power: float, channel_type: str = "qam") -> dict[str, Any]:
    """One channel with three graded fields."""
    return {"channel_id": channel_id, "channel_type": channel_type, "power": power}


_A, _B, _C = _ch(32, 1.0), _ch(1, 2.0), _ch(2, 3.0)
_OFDM_1 = _ch(1, 9.0, "ofdm")
_NO_ID = [{"frequency": 1, "power": 1.0}, {"frequency": 2, "power": 2.0}]

# =============================================================================
# count_matching_fields test data (each channel carries 3 fields)
# =============================================================================
#
# ┌──────────────────────────────┬───────────────────────────┬──────────┬───────────────────────────┐
# │ committed                    │ generated                 │ matching │ description               │
# ├──────────────────────────────┼───────────────────────────┼──────────┼───────────────────────────┤
# │ 32, 1, 2                     │ 32, 1, 2                  │ 9        │ identical                 │
# │ 32, 1, 2                     │ 1, 2                      │ 6        │ leading row dropped       │
# │ 32, 1, 2                     │ 2, 32, 1                  │ 9        │ order does not matter     │
# │ qam 1, ofdm 1                │ ofdm 1, qam 1             │ 6        │ type separates same id    │
# │ no channel_id                │ same                      │ 4        │ positional fallback       │
# │ 32, 1, 2                     │ ids all None              │ 6        │ no id: paired in order    │
# └──────────────────────────────┴───────────────────────────┴──────────┴───────────────────────────┘
#
# fmt: off
MATCH_CASES: list[tuple[list[dict[str, Any]], list[dict[str, Any]], int, str]] = [
    # (committed,           generated,                                          matching, id)
    ([_A, _B, _C],          [_A, _B, _C],                                       9,        "identical"),
    ([_A, _B, _C],          [_B, _C],                                           6,        "leading-row-dropped"),
    ([_A, _B, _C],          [_C, _A, _B],                                       9,        "order-free"),
    ([_B, _OFDM_1],         [_OFDM_1, _B],                                      6,        "type-separates-id"),
    (_NO_ID,                _NO_ID,                                             4,        "positional-fallback"),
    ([_A, _B, _C],          [_ch(None, 1.0), _ch(None, 2.0), _ch(None, 3.0)],   6,        "no-id-paired-in-order"),
]
# fmt: on


@pytest.mark.parametrize(
    "committed,generated,matching",
    [c[:3] for c in MATCH_CASES],
    ids=[c[3] for c in MATCH_CASES],
)
def test_count_matching_fields(committed: list[Any], generated: list[Any], matching: int) -> None:
    """A channel scores against the generated channel with its identity, else the next unpaired one in order."""
    assert count_matching_fields({"downstream": generated}, {"downstream": committed}) == matching


def test_count_fields_counts_every_leaf() -> None:
    """The denominator is every committed channel field plus system_info."""
    assert count_fields({"downstream": [_A, _B], "upstream": [_C], "system_info": {"a": 1}}) == 10


def test_diff_names_missing_and_extra_channels() -> None:
    """Diffs name channels by identity, so a dropped row is one line, not a shift."""
    diffs = diff_golden_files(
        {"downstream": [_B, {**_C, "power": 9.9}, _ch(7, 1.0), _ch(8, 1.0)]},
        {"downstream": [_A, _B, _C]},
    )
    assert diffs == [
        "downstream[qam/2].power: 9.9 vs 3.0",
        "downstream[qam/32].channel_id: 7 vs 32",
        "downstream: extra channel qam/8",
    ]


def test_diff_names_a_channel_nothing_can_pair() -> None:
    """A committed channel with no generated channel left to pair is missing."""
    assert diff_golden_files({"downstream": [_B, _C]}, {"downstream": [_A, _B, _C]}) == [
        "downstream: missing channel qam/32",
    ]
