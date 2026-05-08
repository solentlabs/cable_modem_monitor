"""Tests for type conversion utilities.

Table-driven tests covering all field types, unit stripping,
frequency normalization, map application, and edge cases.
"""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_core.parsers.type_conversion import (
    convert_value,
    normalize_frequency,
    strip_unit,
)

# ┌──────────────────┬────────────┬─────────────┬───────────────────────────┐
# │ raw              │ field_type │ expected    │ description               │
# ├──────────────────┼────────────┼─────────────┼───────────────────────────┤
# │ "123"            │ integer    │ 123         │ simple int                │
# │ " 456 "          │ integer    │ 456         │ whitespace stripped       │
# │ "3.14"           │ integer    │ 3           │ float truncated to int    │
# │ ""               │ integer    │ None        │ empty string              │
# │ "abc"            │ integer    │ None        │ non-numeric               │
# │ "3.2"            │ float      │ 3.2         │ simple float              │
# │ "-15.3"          │ float      │ -15.3       │ negative float            │
# │ ""               │ float      │ None        │ empty float               │
# │ "Locked"         │ string     │ "Locked"    │ simple string             │
# │ "  padded  "     │ string     │ "padded"    │ whitespace stripped       │
# │ ""               │ string     │ None        │ empty string              │
# │ "true"           │ boolean    │ True        │ boolean true              │
# │ "false"          │ boolean    │ False       │ boolean false             │
# │ "1"              │ boolean    │ True        │ boolean numeric true      │
# │ "507000000"      │ frequency  │ 507e6       │ Hz passthrough            │
# │ "507"            │ frequency  │ 507e6       │ MHz normalized            │
# │ "Locked"         │ lock_status│ "locked"    │ lock_status Locked        │
# │ "Not Locked"     │ lock_status│ "not_locked"│ lock_status Not Locked    │
# └──────────────────┴────────────┴─────────────┴───────────────────────────┘
#
# fmt: off
CONVERT_VALUE_CASES = [
    # (raw,             type,        expected,     description)
    ("123",             "integer",   123,          "simple integer"),
    (" 456 ",           "integer",   456,          "integer with whitespace"),
    ("3.14",            "integer",   3,            "float truncated to int"),
    ("",                "integer",   None,         "empty string returns None"),
    ("abc",             "integer",   None,         "non-numeric returns None"),
    ("3.2",             "float",     3.2,          "simple float"),
    ("-15.3",           "float",     -15.3,        "negative float"),
    ("0.0",             "float",     0.0,          "zero float"),
    ("",                "float",     None,         "empty string returns None"),
    ("xyz",             "float",     None,         "non-numeric returns None"),
    ("Locked",          "string",    "Locked",     "simple string"),
    ("  padded  ",      "string",    "padded",     "whitespace stripped"),
    ("",                "string",    None,         "empty string returns None"),
    ("true",            "boolean",   True,         "true string"),
    ("false",           "boolean",   False,        "false string"),
    ("1",               "boolean",   True,         "numeric true"),
    ("0",               "boolean",   False,        "numeric false"),
    ("yes",             "boolean",   True,         "yes is truthy"),
    ("no",              "boolean",   False,        "no is falsy"),
    ("507000000",       "frequency", 507_000_000,  "Hz passthrough"),
    ("507",             "frequency", 507_000_000,  "MHz auto-detected"),
    ("Locked",          "lock_status", "locked",   "lock_status Locked"),
    ("Not Locked",      "lock_status", "not_locked", "lock_status Not Locked"),
    ("YES",             "lock_status", "locked",   "lock_status YES"),
    ("Active",          "lock_status", "locked",   "lock_status Active"),
    ("true",            "lock_status", "locked",   "lock_status true"),
    ("1",               "lock_status", "locked",   "lock_status numeric 1"),
    ("on",              "lock_status", "locked",   "lock_status on"),
    ("Unlocked",        "lock_status", "not_locked", "lock_status Unlocked"),
    ("0",               "lock_status", "not_locked", "lock_status numeric 0"),
    ("no",              "lock_status", "not_locked", "lock_status no"),
    ("QAM256",          "modulation", "QAM256",     "modulation canonical pass-through"),
    ("256QAM",          "modulation", "QAM256",     "modulation number-prefix canonicalized"),
    ("256-QAM",         "modulation", "QAM256",     "modulation hyphen separator canonicalized"),
    ("256qam",          "modulation", "QAM256",     "modulation lowercase canonicalized"),
    ("256 QAM",         "modulation", "QAM256",     "modulation space separator canonicalized"),
    ("qpsk",            "modulation", "QPSK",       "modulation QPSK case normalized"),
    ("OFDM",            "modulation", "OFDM",       "modulation unrecognized passes through (validator catches)"),
    ("0,1,3,4",         "modulation", "0,1,3,4",    "modulation IUC list passes through (validator catches)"),
    ("",                "modulation", None,         "modulation empty returns None"),
]
# fmt: on


@pytest.mark.parametrize(
    "raw,field_type,expected,desc",
    CONVERT_VALUE_CASES,
    ids=[c[3] for c in CONVERT_VALUE_CASES],
)
def test_convert_value(raw: str, field_type: str, expected: object, desc: str) -> None:
    """Test type conversion for each field type."""
    result = convert_value(raw, field_type)
    assert result == expected, f"{desc}: expected {expected!r}, got {result!r}"


# --- Unit stripping ---

# fmt: off
UNIT_STRIP_CASES = [
    # (raw,             unit,    expected, description)
    ("3.2 dBmV",        "dBmV",  "3.2",   "strip dBmV suffix"),
    ("-15.3 dB",        "dB",    "-15.3",  "strip dB suffix"),
    ("507 MHz",         "MHz",   "507",    "strip MHz suffix"),
    ("507000000 Hz",    "Hz",    "507000000", "strip Hz suffix"),
    ("3.2",             "dBmV",  "3.2",    "no suffix present"),
    ("3.2 dbmv",        "dBmV",  "3.2",    "case-insensitive strip"),
]
# fmt: on


@pytest.mark.parametrize(
    "raw,unit,expected,desc",
    UNIT_STRIP_CASES,
    ids=[c[3] for c in UNIT_STRIP_CASES],
)
def test_strip_unit(raw: str, unit: str, expected: str, desc: str) -> None:
    """Test unit suffix stripping."""
    result = strip_unit(raw, unit)
    assert result == expected, f"{desc}: expected {expected!r}, got {result!r}"


# --- Unit stripping with convert_value ---

# fmt: off
CONVERT_WITH_UNIT_CASES = [
    # (raw,             type,       unit,    expected, description)
    ("3.2 dBmV",        "float",    "dBmV",  3.2,     "float with unit"),
    ("-15.3 dB",        "float",    "dB",    -15.3,   "negative float with unit"),
    ("507 MHz",         "frequency", "MHz",  507_000_000, "frequency with MHz unit"),
    ("507000000 Hz",    "frequency", "Hz",   507_000_000, "frequency with Hz unit"),
    ("1234",            "integer",  "",      1234,    "integer no unit"),
]
# fmt: on


@pytest.mark.parametrize(
    "raw,field_type,unit,expected,desc",
    CONVERT_WITH_UNIT_CASES,
    ids=[c[4] for c in CONVERT_WITH_UNIT_CASES],
)
def test_convert_value_with_unit(raw: str, field_type: str, unit: str, expected: object, desc: str) -> None:
    """Test type conversion with unit stripping."""
    result = convert_value(raw, field_type, unit=unit)
    assert result == expected, f"{desc}: expected {expected!r}, got {result!r}"


# --- Map application ---


class TestMapApplication:
    """Test value map application in convert_value."""

    def test_map_applied_before_conversion(self) -> None:
        """Map transforms the raw string before type conversion."""
        result = convert_value(
            "Locked",
            "string",
            map_config={"Locked": "locked", "Not Locked": "not_locked"},
        )
        assert result == "locked"

    def test_map_no_match_passes_through(self) -> None:
        """Unmapped values pass through unchanged."""
        result = convert_value(
            "Unknown",
            "string",
            map_config={"Locked": "locked"},
        )
        assert result == "Unknown"

    def test_map_with_none_config(self) -> None:
        """None map_config is a no-op."""
        result = convert_value("Locked", "string", map_config=None)
        assert result == "Locked"

    def test_map_empty_dict(self) -> None:
        """Empty map dict is a no-op."""
        result = convert_value("Locked", "string", map_config={})
        assert result == "Locked"


# --- Frequency normalization ---

# fmt: off
FREQUENCY_CASES = [
    # (raw,            expected,       description)
    (507_000_000,      507_000_000,    "int Hz passthrough"),
    (507.0,            507_000_000,    "float MHz auto-detected"),
    (507_000_000.0,    507_000_000,    "float Hz passthrough"),
    ("507",            507_000_000,    "string MHz auto-detected"),
    ("507000000",      507_000_000,    "string Hz passthrough"),
    ("507 MHz",        507_000_000,    "string with MHz suffix"),
    ("507000000 Hz",   507_000_000,    "string with Hz suffix"),
    (0,                0,              "zero frequency"),
    (108,              108_000_000,    "lowest DS frequency (MHz)"),
    (5,                5_000_000,      "lowest US frequency (MHz)"),
    (1218,             1_218_000_000,  "highest DS frequency (MHz)"),
]
# fmt: on


@pytest.mark.parametrize(
    "raw,expected,desc",
    FREQUENCY_CASES,
    ids=[c[2] for c in FREQUENCY_CASES],
)
def test_normalize_frequency(raw: int | float | str, expected: int, desc: str) -> None:
    """Test frequency normalization to Hz."""
    result = normalize_frequency(raw)
    assert result == expected, f"{desc}: expected {expected}, got {result}"


def test_normalize_frequency_invalid() -> None:
    """Non-numeric strings raise ValueError."""
    with pytest.raises(ValueError):
        normalize_frequency("not-a-number")


# --- Edge cases: unknown type, conversion fallbacks ---


class TestUnknownFieldType:
    """Test handling of unrecognized field types."""

    def test_unknown_type_returns_string(self) -> None:
        """Unknown field type passes through as stripped string."""
        result = convert_value("hello", "custom_type")
        assert result == "hello"


class TestNumericCleanup:
    """Test numeric cleanup for values with embedded non-numeric chars."""

    def test_integer_with_embedded_chars(self) -> None:
        """Integer conversion strips non-numeric characters as fallback."""
        # e.g., "1,234" → strips comma → "1234" → 1234
        result = convert_value("1,234", "integer")
        assert result == 1234

    def test_float_with_embedded_chars(self) -> None:
        """Float conversion strips non-numeric characters as fallback."""
        result = convert_value("3,200.5", "float")
        assert result == 3200.5

    def test_integer_fully_non_numeric(self) -> None:
        """Completely non-numeric string returns None for integer."""
        result = convert_value("N/A", "integer")
        assert result is None

    def test_float_fully_non_numeric(self) -> None:
        """Completely non-numeric string returns None for float."""
        result = convert_value("N/A", "float")
        assert result is None

    def test_frequency_non_numeric(self) -> None:
        """Non-numeric frequency string returns None via convert_value."""
        result = convert_value("N/A", "frequency")
        assert result is None

    def test_integer_multiple_dots(self) -> None:
        """Value with multiple dots fails both parse attempts."""
        result = convert_value("1.2.3", "integer")
        assert result is None

    def test_float_multiple_dots(self) -> None:
        """Value with multiple dots fails both parse attempts."""
        result = convert_value("1.2.3", "float")
        assert result is None


# --- Scale multiplication ---

# fmt: off
SCALE_CASES = [
    # (raw,     type,      scale, expected,  description)
    ("53",      "float",   0.1,   5.3,       "float scale down by 0.1"),
    ("5.12",    "float",   1000,  5120,      "float scale up, whole-number cast to int"),
    ("5120",    "integer", 0.001, 5.12,      "integer scale down to float"),
    ("100",     "integer", 10,    1000,      "integer scale up stays int"),
    ("hello",   "string",  2,     "hello",   "string ignores scale"),
    ("",        "float",   0.1,   None,      "empty value, scale not applied"),
]
# fmt: on


@pytest.mark.parametrize(
    "raw,field_type,scale,expected,desc",
    SCALE_CASES,
    ids=[c[4] for c in SCALE_CASES],
)
def test_convert_value_with_scale(
    raw: str,
    field_type: str,
    scale: float,
    expected: object,
    desc: str,
) -> None:
    """Test scale multiplication after type conversion."""
    result = convert_value(raw, field_type, scale=scale)
    if isinstance(expected, float):
        assert result == pytest.approx(expected), f"{desc}: expected {expected!r}, got {result!r}"
    else:
        assert result == expected, f"{desc}: expected {expected!r}, got {result!r}"


# --- Uptime type with format ---

# fmt: off
UPTIME_CASES = [
    # (raw,        format,     expected,                     description)
    ("1471890",    "seconds",  "17 days 00h:51m:30s",        "Hub 5 uptime"),
    ("0",          "seconds",  "0 days 00h:00m:00s",         "zero seconds"),
    ("86400",      "seconds",  "1 days 00h:00m:00s",         "exactly one day"),
    ("3661",       "seconds",  "0 days 01h:01m:01s",         "1h 1m 1s"),
    ("",           "seconds",  None,                         "empty string"),
    ("abc",        "seconds",  None,                         "non-numeric"),
    ("D: 39 H: 06 M: 24 S: 26",                              # noqa: E501
     "D: {days} H: {hours} M: {minutes} S: {seconds}",
     "39 days 06h:24m:26s", "TG3442DE custom format"),
    ("479h:40m:38s",
     "{hours}h:{minutes}m:{seconds}s",
     "19 days 23h:40m:38s", "hours-only custom format"),
]
# fmt: on


@pytest.mark.parametrize(
    "raw,input_format,expected,desc",
    UPTIME_CASES,
    ids=[c[3] for c in UPTIME_CASES],
)
def test_convert_uptime(
    raw: str,
    input_format: str,
    expected: object,
    desc: str,
) -> None:
    """Test uptime conversion with format parameter."""
    result = convert_value(raw, "uptime", input_format=input_format)
    assert result == expected, f"{desc}: expected {expected!r}, got {result!r}"


# --- Uptime defensive paths ---


def test_uptime_no_format_returns_value_unchanged(caplog) -> None:
    """uptime type without input_format logs warning, returns value as-is."""
    import logging

    with caplog.at_level(logging.WARNING):
        result = convert_value("3600", "uptime")
    # No format specified — value passes through, warning logged
    assert result == "3600"
    assert "uptime type requires a format" in caplog.text


def test_uptime_unknown_format_returns_value_unchanged(caplog) -> None:
    """uptime with non-'seconds' non-placeholder format logs warning, returns value."""
    import logging

    with caplog.at_level(logging.WARNING):
        result = convert_value("3600", "uptime", input_format="unknown_format_string")
    assert result == "3600"
    assert "Unknown uptime format" in caplog.text


def test_uptime_negative_seconds_returns_none() -> None:
    """Negative seconds value yields None (logically not a valid uptime)."""
    result = convert_value("-100", "uptime", input_format="seconds")
    assert result is None


def test_uptime_pattern_no_match_returns_none() -> None:
    """Custom-format pattern that doesn't match the input yields None."""
    result = convert_value(
        "no numbers here",
        "uptime",
        input_format="D: {days} H: {hours} M: {minutes} S: {seconds}",
    )
    assert result is None


def test_uptime_pattern_cached_on_repeat() -> None:
    """Repeat calls with the same format reuse the compiled pattern (cache hit branch)."""
    from solentlabs.cable_modem_monitor_core.parsers.type_conversion import (
        _uptime_pattern_cache,
    )

    fmt = "{days}d {hours}h {minutes}m {seconds}s"
    # Clear the cache slot for hermetic behaviour
    _uptime_pattern_cache.pop(fmt, None)

    convert_value("1d 2h 3m 4s", "uptime", input_format=fmt)
    assert fmt in _uptime_pattern_cache

    # Second call hits the cached-pattern branch
    result = convert_value("5d 6h 7m 8s", "uptime", input_format=fmt)
    assert result == "5 days 06h:07m:08s"
