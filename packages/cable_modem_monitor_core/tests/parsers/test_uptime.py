"""Characterization tests for uptime parsing.

TEST DATA TABLES
================
REPLAY_CASES holds every distinct (value, format) pair the catalog
replays pass to the uptime parser, with the result each golden records.
TRAP_CASES holds the shapes a looser or stricter matcher would get
wrong. Replay cases also run through ``convert_value``, the path every
format parser takes.
"""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_core.parsers.type_conversion import convert_value
from solentlabs.cable_modem_monitor_core.parsers.uptime import parse_uptime

# =============================================================================
# Test Data Tables
# =============================================================================

# The catalog's uptime formats.
_D_HMS = "{days} days {hours}h:{minutes}m:{seconds}s"
_D_HMS_PAREN = "{days} day(s) {hours}h:{minutes}m:{seconds}s"
_D_HMS_PAREN_TIGHT = "{days}day(s){hours}h:{minutes}m:{seconds}s"
_D_HMS_WORDS = "{days} days {hours} hours {minutes} mins {seconds} secs"
_D_HMS_LETTERS = "{days}d {hours}h {minutes}m {seconds}s"
_D_HMS_LETTERS_COLON = "{days}d {hours}h:{minutes}m:{seconds}s"
_D_HM = "{days} d: {hours} h: {minutes} m"
_D_HMS_LABELS = "D: {days} H: {hours} M: {minutes} S: {seconds}"
_HMS_LETTERS = "{hours}h:{minutes}m:{seconds}s"
_OPT_D_CLOCK = "[{days} days ]{hours}:{minutes}:{seconds}"
_CLOCK = "{hours}:{minutes}:{seconds}"
_SECONDS = "seconds"

_ALL_FORMATS = [
    _D_HMS,
    _D_HMS_PAREN,
    _D_HMS_PAREN_TIGHT,
    _D_HMS_WORDS,
    _D_HMS_LETTERS,
    _D_HMS_LETTERS_COLON,
    _D_HM,
    _D_HMS_LABELS,
    _HMS_LETTERS,
    _OPT_D_CLOCK,
    _CLOCK,
    _SECONDS,
]

# ┌─────────────────────────────┬──────────────┬─────────────────────────────┐
# │ raw (as the parser extracts)│ format       │ expected (golden)           │
# ├─────────────────────────────┼──────────────┼─────────────────────────────┤
# │ "50 days 11h:15m:21s.00"    │ _D_HMS       │ "50 days 11h:15m:21s"       │
# │ "1308:19:22"                │ _CLOCK       │ "54 days 12h:19m:22s"       │
# │ "1471890"                   │ _SECONDS     │ "17 days 00h:51m:30s"       │
# └─────────────────────────────┴──────────────┴─────────────────────────────┘
#
# fmt: off
REPLAY_CASES = [
    # (raw,                               format,              expected)
    ("0 d:  7 h: 40 m",                   _D_HM,               "0 days 07h:40m:00s"),
    ("6 d:  2 h: 33  m",                  _D_HM,               "6 days 02h:33m:00s"),
    ("27 d: 13 h: 39  m",                 _D_HM,               "27 days 13h:39m:00s"),
    ("0 d: 0 h: 32 m",                    _D_HM,               "0 days 00h:32m:00s"),
    ("0 days 00h:27m:33s",                _D_HMS,              "0 days 00h:27m:33s"),
    ("0 days 11h:48m:44s",                _D_HMS,              "0 days 11h:48m:44s"),
    ("0 days 0h:9m:47s",                  _D_HMS,              "0 days 00h:09m:47s"),
    ("98 days 14h:53m:26s",               _D_HMS,              "98 days 14h:53m:26s"),
    ("0 days 03h:14m:09s",                _D_HMS,              "0 days 03h:14m:09s"),
    ("50 days 11h:15m:21s.00",            _D_HMS,              "50 days 11h:15m:21s"),
    ("0 days 00h:03m:46s.00",             _D_HMS,              "0 days 00h:03m:46s"),
    ("9 days 00h:27m:07s.00",             _D_HMS,              "9 days 00h:27m:07s"),
    ("9 days 19h:29m:48s",                _D_HMS,              "9 days 19h:29m:48s"),
    ("12 days 08h:42m:15s",               _D_HMS,              "12 days 08h:42m:15s"),
    ("47 days 21h:15m:38s",               _D_HMS,              "47 days 21h:15m:38s"),
    ("18 days 00h:09m:46s",               _D_HMS,              "18 days 00h:09m:46s"),
    ("4 days 00h:16m:45s",                _D_HMS,              "4 days 00h:16m:45s"),
    ("4 days 16h: 5m: 28s",               _D_HMS,              "4 days 16h:05m:28s"),
    ("0 days 20h: 5m: 44s",               _D_HMS,              "0 days 20h:05m:44s"),
    ("13 days 3h: 13m: 17s",              _D_HMS,              "13 days 03h:13m:17s"),
    ("20 days 7h: 58m: 28s",              _D_HMS,              "20 days 07h:58m:28s"),
    ("0 days 02h:52m:40s",                _D_HMS,              "0 days 02h:52m:40s"),
    ("12 day(s) 19h:53m:41s",             _D_HMS_PAREN,        "12 days 19h:53m:41s"),
    ("0day(s)0h:16m:36s",                 _D_HMS_PAREN_TIGHT,  "0 days 00h:16m:36s"),
    ("1 days 23 hours 43 mins 44 secs",   _D_HMS_WORDS,        "1 days 23h:43m:44s"),
    ("0d 0h 6m 44s",                      _D_HMS_LETTERS,      "0 days 00h:06m:44s"),
    ("0d 0h 6m 27s",                      _D_HMS_LETTERS,      "0 days 00h:06m:27s"),
    ("3d 15h:1m:27s",                     _D_HMS_LETTERS_COLON, "3 days 15h:01m:27s"),
    ("D: 39 H: 06 M: 24 S: 26",           _D_HMS_LABELS,       "39 days 06h:24m:26s"),
    ("479h:40m:38s",                      _HMS_LETTERS,        "19 days 23h:40m:38s"),
    ("39 days 15:47:33",                  _OPT_D_CLOCK,        "39 days 15h:47m:33s"),
    ("13 days 06:59:07",                  _OPT_D_CLOCK,        "13 days 06h:59m:07s"),
    ("10 days 01:41:16",                  _OPT_D_CLOCK,        "10 days 01h:41m:16s"),
    ("65 days 20:18:58",                  _OPT_D_CLOCK,        "65 days 20h:18m:58s"),
    ("16 days 21:14:32",                  _OPT_D_CLOCK,        "16 days 21h:14m:32s"),
    ("05:07:57",                          _OPT_D_CLOCK,        "0 days 05h:07m:57s"),
    ("1308:19:22",                        _CLOCK,              "54 days 12h:19m:22s"),
    ("50221",                             _SECONDS,            "0 days 13h:57m:01s"),
    ("1471890",                           _SECONDS,            "17 days 00h:51m:30s"),
    ("574",                               _SECONDS,            "0 days 00h:09m:34s"),
    ("153513",                            _SECONDS,            "1 days 18h:38m:33s"),
    ("17345",                             _SECONDS,            "0 days 04h:49m:05s"),
]
# fmt: on

# A clock time written where uptime belongs, as captured from firmware.
_CLOCK_TIME = "Fri Feb 27 20:54:00 2026"

# ┌───────────────────────────────┬──────────────┬───────────────────────┬──────────────────────────┐
# │ raw                           │ format       │ expected              │ description              │
# ├───────────────────────────────┼──────────────┼───────────────────────┼──────────────────────────┤
# │ "50 days ...21s.00"           │ _D_HMS       │ "50 days 11h:15m:21s" │ trailing text ignored    │
# │ "x 50 days ..."               │ _D_HMS       │ None                  │ leading text rejected    │
# │ "1308:19:22"                  │ _OPT_D_CLOCK │ "54 days ..."         │ hours past 24, no days   │
# │ ""                            │ _D_HMS       │ None                  │ empty                    │
# └───────────────────────────────┴──────────────┴───────────────────────┴──────────────────────────┘
#
# fmt: off
TRAP_CASES = [
    # (raw,                          format,         expected,               description)
    ("50 days 11h:15m:21s.00",       _D_HMS,         "50 days 11h:15m:21s",  "trailing-fraction-ignored"),
    ("1 days 01h:01m:01s 2 days",    _D_HMS,         "1 days 01h:01m:01s",   "first-match-wins-over-trailing-repeat"),
    ("x 50 days 11h:15m:21s",        _D_HMS,         None,                   "leading-text-rejected"),
    ("  4 days 16h: 5m: 28s  ",      _D_HMS,         "4 days 16h:05m:28s",   "surrounding-whitespace-stripped"),
    ("  D: 39 H: 06 M: 24 S: 26",    _D_HMS_LABELS,  "39 days 06h:24m:26s",  "leading-whitespace-before-literal"),
    ("20 days 7h: 58m: 28s",         _D_HMS,         "20 days 07h:58m:28s",  "spaced-colons"),
    ("1308:19:22",                   _CLOCK,         "54 days 12h:19m:22s",  "clock-hours-past-24"),
    ("1308:19:22",                   _OPT_D_CLOCK,   "54 days 12h:19m:22s",  "optional-days-hours-past-24"),
    ("479h:40m:38s",                 _HMS_LETTERS,   "19 days 23h:40m:38s",  "letter-hours-past-24"),
    ("05:07:57",                     _OPT_D_CLOCK,   "0 days 05h:07m:57s",   "bare-clock-optional-days-absent"),
    ("05:07:57",                     _CLOCK,         "0 days 05h:07m:57s",   "bare-clock"),
    ("05:07",                        _CLOCK,         None,                   "clock-missing-seconds"),
    ("",                             _D_HMS,         None,                   "empty-pattern"),
    ("",                             _SECONDS,       None,                   "empty-seconds"),
    ("0",                            _SECONDS,       "0 days 00h:00m:00s",   "zero-seconds"),
    ("86400",                        _SECONDS,       "1 days 00h:00m:00s",   "exactly-one-day"),
    ("3661.9",                       _SECONDS,       "0 days 01h:01m:01s",   "fractional-seconds-truncated"),
    ("-100",                         _SECONDS,       None,                   "negative-seconds"),
    ("abc",                          _SECONDS,       None,                   "non-numeric-seconds"),
    ("1e400",                        _SECONDS,       None,                   "overflow-seconds"),
    ("02h:30m",                      "{hours}h:{minutes}m[:{seconds}s]",
                                                     "0 days 02h:30m:00s",   "optional-trailing-segment-absent"),
    ("02h:30m:15s",                  "{hours}h:{minutes}m[:{seconds}s]",
                                                     "0 days 02h:30m:15s",   "optional-trailing-segment-present"),
    ("3600",                         "",             "3600",                 "no-format-passthrough"),
    ("3600",                         "minutes",      "3600",                 "unknown-format-passthrough"),
]
# fmt: on


# =============================================================================
# Tests
# =============================================================================


class TestReplayCorpus:
    """Every value the catalog replays extract parses to its golden result."""

    @pytest.mark.parametrize("raw,input_format,expected", REPLAY_CASES, ids=[c[0] for c in REPLAY_CASES])
    def test_parse_uptime(self, raw: str, input_format: str, expected: str) -> None:
        assert parse_uptime(raw, input_format) == expected

    @pytest.mark.parametrize("raw,input_format,expected", REPLAY_CASES, ids=[c[0] for c in REPLAY_CASES])
    def test_convert_value(self, raw: str, input_format: str, expected: str) -> None:
        assert convert_value(raw, "uptime", input_format=input_format) == expected


class TestTraps:
    """Shapes a changed matcher would read differently."""

    @pytest.mark.parametrize(
        "raw,input_format,expected,desc",
        TRAP_CASES,
        ids=[c[3] for c in TRAP_CASES],
    )
    def test_parse_uptime(self, raw: str, input_format: str, expected: str | None, desc: str) -> None:
        assert parse_uptime(raw, input_format) == expected, desc

    @pytest.mark.parametrize("input_format", _ALL_FORMATS)
    def test_clock_time_rejected(self, input_format: str) -> None:
        assert parse_uptime(_CLOCK_TIME, input_format) is None
