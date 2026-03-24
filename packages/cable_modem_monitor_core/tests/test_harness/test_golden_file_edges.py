"""Tests for golden file comparison edge cases.

Covers channel_id type mismatch diagnostic hints and frequency
normalization hints.
"""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_core.test_harness.golden_file import (
    _hint_for_field,
)

# ┌──────────┬──────────────┬──────────────┬──────────────────────────┐
# │ field    │ actual       │ expected     │ expected_hint            │
# ├──────────┼──────────────┼──────────────┼──────────────────────────┤
# │ chan_id  │ "1" (str)    │ 1 (int)      │ "string, expected int"   │
# │ chan_id  │ 1 (int)      │ "1" (str)    │ "int, expected string"   │
# │ chan_id  │ 1 (int)      │ 2 (int)      │ "" (no hint)             │
# │ freq     │ 0.50 (float) │ 500000 (int) │ "in MHz"                 │
# │ freq     │ 500e6 (int)  │ 500 (int)    │ "double Hz"              │
# │ other    │ "a"          │ "b"          │ "" (no hint)             │
# └──────────┴──────────────┴──────────────┴──────────────────────────┘
#
# fmt: off
HINT_CASES = [
    ("channel_id",  "1",       1,       "string, expected int",  "string→int mismatch"),
    ("channel_id",  1,         "1",     "int, expected string",  "int→string mismatch"),
    ("channel_id",  1,         2,       "",                      "same type — no hint"),
    ("frequency",   0.500001,  500000,  "in MHz",                "MHz normalization"),
    ("frequency",   500000000, 500,     "double Hz",             "double normalization"),
    ("snr",         35,        36,      "",                      "non-hinted field"),
]
# fmt: on


@pytest.mark.parametrize(
    "field,actual,expected,expected_hint,desc",
    HINT_CASES,
    ids=[c[4] for c in HINT_CASES],
)
def test_hint_for_field(
    field: str,
    actual: object,
    expected: object,
    expected_hint: str,
    desc: str,
) -> None:
    """_hint_for_field generates correct diagnostic hints."""
    hint = _hint_for_field(field, actual, expected)
    if expected_hint:
        assert expected_hint in hint
    else:
        assert hint == ""
