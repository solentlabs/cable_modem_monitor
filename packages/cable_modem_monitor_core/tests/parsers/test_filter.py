"""Tests for shared channel filter logic."""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_core.parsers.filter import passes_filter

# ┌──────────────────┬─────────────────────┬──────────┬──────────────────────────┐
# │ channel          │ filter_rules        │ expected │ description              │
# ├──────────────────┼─────────────────────┼──────────┼──────────────────────────┤
# │ {id: 1}          │ {}                  │ True     │ no rules = pass          │
# │ {id: 1}          │ {id: 1}             │ True     │ equality match           │
# │ {id: 0}          │ {id: 1}             │ False    │ equality mismatch        │
# │ {id: 1}          │ {id: {not: 0}}      │ True     │ not-equal pass           │
# │ {id: 0}          │ {id: {not: 0}}      │ False    │ not-equal fail           │
# │ {id: 1, t: "q"}  │ {id: 1, t: "q"}     │ True     │ multi-rule all pass      │
# │ {id: 1, t: "q"}  │ {id: 1, t: "o"}     │ False    │ multi-rule one fails     │
# │ {}               │ {id: 1}             │ False    │ missing field = fail     │
# │ {}               │ {id: {not: 0}}      │ True     │ missing field != 0       │
# └──────────────────┴─────────────────────┴──────────┴──────────────────────────┘
#
# fmt: off
FILTER_CASES = [
    # (channel,              filter_rules,              expected, description)
    ({"id": 1},              {},                         True,    "no rules = pass"),
    ({"id": 1},              {"id": 1},                  True,    "equality match"),
    ({"id": 0},              {"id": 1},                  False,   "equality mismatch"),
    ({"id": 1},              {"id": {"not": 0}},         True,    "not-equal pass"),
    ({"id": 0},              {"id": {"not": 0}},         False,   "not-equal fail"),
    ({"id": 1, "t": "q"},   {"id": 1, "t": "q"},        True,    "multi-rule all pass"),
    ({"id": 1, "t": "q"},   {"id": 1, "t": "o"},        False,   "multi-rule one fails"),
    ({},                     {"id": 1},                  False,   "missing field = fail"),
    ({},                     {"id": {"not": 0}},         True,    "missing field != 0"),
]
# fmt: on


@pytest.mark.parametrize(
    "channel,filter_rules,expected,desc",
    FILTER_CASES,
    ids=[c[3] for c in FILTER_CASES],
)
def test_passes_filter(
    channel: dict,
    filter_rules: dict,
    expected: bool,
    desc: str,
) -> None:
    """Verify filter logic for various rule combinations."""
    assert passes_filter(channel, filter_rules) is expected
