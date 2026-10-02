"""Type conversion for parser field values.

Handles field type conversion (integer, float, string, frequency, boolean,
lock_status, modulation, uptime via parsers.uptime), unit suffix stripping,
value mapping, scale multiplication, and frequency normalization.

See PARSING_SPEC.md Field Types for the authoritative type definitions.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..spec_conformance import canonicalize_modulation
from .uptime import parse_uptime

_logger = logging.getLogger(__name__)

# Frequency magnitude threshold: values below this are treated as MHz.
# DOCSIS downstream: 108–1218 MHz. Upstream: 5–204 MHz.
# The maximum MHz value (1218) is well below 1M.
# The minimum Hz value (5,000,000 upstream) is well above 1M.
_FREQUENCY_MHZ_THRESHOLD = 1_000_000

# Explicit suffix → multiplier to convert to Hz.
_SUFFIX_MULTIPLIERS: dict[str, int] = {
    "ghz": 1_000_000_000,
    "mhz": 1_000_000,
    "khz": 1_000,
    "hz": 1,
}

# Strip non-numeric characters except decimal point, minus, and plus.
_NUMERIC_CLEANUP_RE = re.compile(r"[^\d.+\-eE]")


def strip_unit(raw: str, unit: str) -> str:
    """Strip a unit suffix from a raw value string.

    Case-insensitive suffix match. Returns the value with the suffix removed
    and whitespace stripped.

    Args:
        raw: The raw string value (e.g., ``"3.2 dBmV"``).
        unit: The unit suffix to strip (e.g., ``"dBmV"``).

    Returns:
        The value with the unit suffix removed.
    """
    stripped = raw.strip()
    if unit and stripped.lower().endswith(unit.lower()):
        stripped = stripped[: -len(unit)].strip()
    return stripped


def normalize_frequency(raw: str | int | float) -> int:
    """Normalize a frequency value to Hz.

    When the string contains an explicit unit suffix (GHz, MHz, kHz, Hz),
    the suffix determines the conversion factor. When no suffix is
    present (or the input is numeric), a magnitude heuristic is used:
    values below 1,000,000 are treated as MHz.

    Args:
        raw: Frequency value as string, int, or float. String values may
            include unit suffixes (stripped before conversion).

    Returns:
        Frequency in Hz as an integer.

    Raises:
        ValueError: If the value cannot be parsed as a number.
    """
    if isinstance(raw, int | float):
        value = float(raw)
        suffix_found = ""
    else:
        cleaned = raw.strip()
        suffix_found = ""
        # Strip common frequency unit suffixes (longest first to avoid
        # "hz" matching the tail of "mhz")
        for suffix in ("ghz", "mhz", "khz", "hz"):
            if cleaned.lower().endswith(suffix):
                suffix_found = suffix
                cleaned = cleaned[: -len(suffix)].strip()
                break
        value = float(cleaned)

    if value == 0:
        return 0

    # When an explicit suffix was found, use it for conversion
    if suffix_found:
        multiplier = _SUFFIX_MULTIPLIERS.get(suffix_found, 1)
        return int(round(value * multiplier))

    # No suffix — fall back to magnitude heuristic
    if abs(value) < _FREQUENCY_MHZ_THRESHOLD:
        # Value is in MHz — convert to Hz
        value = value * 1_000_000

    return int(round(value))


_TYPE_HANDLERS: dict[str, Any] = {}  # populated after handler definitions


def convert_value(
    raw: Any,
    field_type: str,
    *,
    unit: str = "",
    map_config: dict[str, str] | None = None,
    scale: int | float | None = None,
    input_format: str = "",
) -> int | float | str | bool | None:
    """Convert a raw value to the declared field type.

    Processing order:
    1. Stringify and strip whitespace
    2. Apply map (on raw stripped text, before type conversion)
    3. Strip unit suffix
    4. Type conversion
    5. Scale multiplication (numeric types only)

    Args:
        raw: The raw value (typically a string from HTML cell text).
        field_type: One of ``"integer"``, ``"float"``, ``"string"``,
            ``"frequency"``, ``"boolean"``, ``"lock_status"``,
            ``"uptime"``.
        unit: Unit suffix to strip before numeric conversion.
        map_config: Optional value mapping (e.g., ``{"Locked": "locked"}``).
        scale: Optional multiplier applied after type conversion.
            Only affects numeric results (int/float). Whole-number
            float results are cast to int.
        input_format: Sub-format selector for types that accept
            multiple raw formats (e.g., ``"seconds"`` for ``uptime``).

    Returns:
        Converted value, or ``None`` if the raw value is empty or
        conversion fails.
    """
    # Step 1: stringify and strip whitespace
    value = str(raw).strip()
    if not value:
        return None

    # Step 2: apply map (on raw stripped text)
    if map_config is not None and value in map_config:
        value = map_config[value]

    # Step 3: strip unit suffix
    if unit:
        value = strip_unit(value, unit)

    # Step 4: type conversion via dispatch table
    handler = _TYPE_HANDLERS.get(field_type)
    if handler is None:
        _logger.warning("Unknown field type '%s', returning as string", field_type)
        result = value
    elif field_type == "uptime":
        result = handler(value, input_format)
    else:
        result = handler(value)

    # Step 5: scale multiplication (numeric types only)
    if result is not None and scale is not None and isinstance(result, int | float):
        result = round(result * scale, 10)
        if isinstance(result, float) and result == int(result):
            result = int(result)

    return result


def _to_integer(value: str) -> int | None:
    """Convert string to integer, stripping non-numeric characters."""
    try:
        return int(float(value))
    except (ValueError, OverflowError):
        cleaned = _NUMERIC_CLEANUP_RE.sub("", value)
        if not cleaned:
            return None
        try:
            return int(float(cleaned))
        except (ValueError, OverflowError):
            _logger.debug("Cannot convert '%s' to integer", value)
            return None


def _to_float(value: str) -> float | None:
    """Convert string to float, stripping non-numeric characters."""
    try:
        return float(value)
    except (ValueError, OverflowError):
        cleaned = _NUMERIC_CLEANUP_RE.sub("", value)
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except (ValueError, OverflowError):
            _logger.debug("Cannot convert '%s' to float", value)
            return None


def _to_frequency(value: str) -> int | None:
    """Convert string to frequency in Hz."""
    try:
        return normalize_frequency(value)
    except (ValueError, OverflowError):
        _logger.debug("Cannot convert '%s' to frequency", value)
        return None


def _to_boolean(value: str) -> bool:
    """Convert string to boolean.

    Truthy values: "true", "1", "yes", "on", "locked", "active".
    Everything else is falsy.
    """
    return value.lower() in {"true", "1", "yes", "on", "locked", "active"}


_LOCKED_VALUES = {"locked", "yes", "active", "true", "1", "on"}


def _to_lock_status(value: str) -> str:
    """Normalize lock status to canonical ``"locked"`` or ``"not_locked"``.

    Handles common modem representations: ``"Locked"``, ``"Not Locked"``,
    ``"YES"``, ``"True"``, ``"Active"``, etc.
    """
    return "locked" if value.lower() in _LOCKED_VALUES else "not_locked"


def _to_modulation(value: str) -> str | None:
    """Canonicalize a modulation value to its standard form.

    Recognized variants (``256QAM``, ``256-QAM``, ``256qam``, etc.)
    return canonical form (``QAM256``). Unrecognized strings pass
    through unchanged so the spec-conformance gate surfaces them as
    real violations rather than silently dropping data — a passthrough
    here is preferable to opaque field omission for non-modulation
    strings the modem might emit (channel-type sentinels, profile IDs,
    IUC lists, etc.). Empty input returns ``None``.
    """
    if not value:
        return None
    canonical = canonicalize_modulation(value)
    return canonical if canonical is not None else value


# Populate the dispatch table now that all handlers are defined.
_TYPE_HANDLERS.update(
    {
        "string": lambda v: v,
        "integer": _to_integer,
        "float": _to_float,
        "frequency": _to_frequency,
        "boolean": _to_boolean,
        "lock_status": _to_lock_status,
        "modulation": _to_modulation,
        "uptime": parse_uptime,
    }
)
