"""Tests for lib/utils.py — get_device_name, extract_number/float, parse_uptime_to_seconds."""

from __future__ import annotations

import pytest

from custom_components.cable_modem_monitor.const import EntityPrefix
from custom_components.cable_modem_monitor.lib.utils import (
    extract_float,
    extract_number,
    get_device_name,
    parse_uptime_to_seconds,
)

# fmt: off
# ┌──────────────────┬─────────┬────────────────────┬────────────────────────────┐
# │ entity_prefix    │ model   │ host               │ expected                   │
# ├──────────────────┼─────────┼────────────────────┼────────────────────────────┤
DEVICE_NAME_CASES = [
    (EntityPrefix.NONE,  "",        "",               "Cable Modem"),
    (EntityPrefix.MODEL, "SB8200",  "",               "Cable Modem SB8200"),
    (EntityPrefix.IP,    "",        "192.168.100.1",  "Cable Modem 192.168.100.1"),
    (EntityPrefix.MODEL, "SB8200",  "192.168.100.1",  "Cable Modem SB8200"),  # model wins
    (EntityPrefix.IP,    "SB8200",  "192.168.100.1",  "Cable Modem 192.168.100.1"),
]
# └──────────────────┴─────────┴────────────────────┴────────────────────────────┘
# fmt: on


@pytest.mark.parametrize("prefix,model,host,expected", DEVICE_NAME_CASES)
def test_get_device_name(prefix: EntityPrefix, model: str, host: str, expected: str) -> None:
    assert get_device_name(prefix, model=model, host=host) == expected


# fmt: off
# ┌──────────────┬──────────┐
# │ input        │ expected │
# ├──────────────┼──────────┤
EXTRACT_NUMBER_CASES = [
    ("123",       123),
    ("-5",        -5),
    ("  42  ",    42),
    ("3 dBmV",   3),
    ("no digits", None),
    ("",          None),
    ("-",         None),   # only sign char → ValueError branch
]

EXTRACT_FLOAT_CASES = [
    ("3.5",       3.5),
    ("-1.2",      -1.2),
    ("6.0 dBmV",  6.0),
    ("no digits", None),
    ("",          None),
    ("-.",        None),   # sign + decimal only → ValueError branch
]
# └──────────────┴──────────┘
# fmt: on


@pytest.mark.parametrize("text,expected", EXTRACT_NUMBER_CASES)
def test_extract_number(text: str, expected: int | None) -> None:
    assert extract_number(text) == expected


@pytest.mark.parametrize("text,expected", EXTRACT_FLOAT_CASES)
def test_extract_float(text: str, expected: float | None) -> None:
    assert extract_float(text) == expected


# fmt: off
# ┌──────────────────────────────┬──────────┬──────────────────────────────────────────────┐
# │ uptime_str                   │ expected │ description                                  │
# ├──────────────────────────────┼──────────┼──────────────────────────────────────────────┤
UPTIME_CASES = [
    (None,                        None,     "none_returns_none"),
    ("Unknown",                   None,     "unknown_string"),
    ("0",                         None,     "zero_seconds_returns_none"),
    ("1471890",                   1471890,  "plain_numeric_seconds"),
    ("1308:19:22",                4709962,  "hours_colon_mm_ss"),
    ("7 days 12:34:56",           650096,   "days_plus_embedded_hms"),
    ("2 days 5 hours",            190800,   "days_and_hours"),
    ("0 days 08h:37m:20s",        31040,    "arris_zero_days"),
    ("47d 12h 34m 56s",           4106096,  "short_form_d_h_m_s"),
    ("1 day 0 hours 0 minutes",   86400,    "one_day_singular"),
    ("!!!",                       None,     "unparseable_returns_none"),
]
# └──────────────────────────────┴──────────┴──────────────────────────────────────────────┘
# fmt: on


@pytest.mark.parametrize("uptime_str,expected,_desc", UPTIME_CASES, ids=[c[2] for c in UPTIME_CASES])
def test_parse_uptime_to_seconds(uptime_str: str | None, expected: int | None, _desc: str) -> None:
    assert parse_uptime_to_seconds(uptime_str) == expected
