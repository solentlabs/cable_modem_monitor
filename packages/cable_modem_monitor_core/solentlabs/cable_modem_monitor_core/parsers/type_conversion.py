"""Type conversion for parser field values.

Handles field type conversion (integer, float, string, frequency, boolean),
unit suffix stripping, value mapping, and frequency normalization.

See PARSING_SPEC.md Field Types for the authoritative type definitions.
"""

from __future__ import annotations

import logging
import re
from typing import Any

_logger = logging.getLogger(__name__)

# Frequency magnitude threshold: values below this are treated as MHz.
# DOCSIS downstream: 108–1218 MHz. Upstream: 5–204 MHz.
# The maximum MHz value (1218) is well below 1M.
# The minimum Hz value (5,000,000 upstream) is well above 1M.
_FREQUENCY_MHZ_THRESHOLD = 1_000_000

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

    Auto-detects Hz vs MHz by magnitude: values below the threshold
    (1,000,000) are treated as MHz and multiplied by 1e6. Values at or
    above the threshold are treated as Hz.

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
    else:
        cleaned = raw.strip()
        # Strip common frequency unit suffixes (longest first to avoid
        # "hz" matching the tail of "mhz")
        for suffix in ("ghz", "mhz", "khz", "hz"):
            if cleaned.lower().endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
                break
        value = float(cleaned)

    if value == 0:
        return 0

    if abs(value) < _FREQUENCY_MHZ_THRESHOLD:
        # Value is in MHz — convert to Hz
        value = value * 1_000_000

    return int(round(value))


def convert_value(
    raw: Any,
    field_type: str,
    *,
    unit: str = "",
    map_config: dict[str, str] | None = None,
) -> int | float | str | bool | None:
    """Convert a raw value to the declared field type.

    Processing order:
    1. Stringify and strip whitespace
    2. Apply map (on raw stripped text, before type conversion)
    3. Strip unit suffix
    4. Type conversion

    Args:
        raw: The raw value (typically a string from HTML cell text).
        field_type: One of ``"integer"``, ``"float"``, ``"string"``,
            ``"frequency"``, ``"boolean"``.
        unit: Unit suffix to strip before numeric conversion.
        map_config: Optional value mapping (e.g., ``{"Locked": "locked"}``).

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

    # Step 4: type conversion
    if field_type == "string":
        return value

    if field_type == "integer":
        return _to_integer(value)

    if field_type == "float":
        return _to_float(value)

    if field_type == "frequency":
        return _to_frequency(value)

    if field_type == "boolean":
        return _to_boolean(value)

    # Unknown type — pass through as string
    _logger.warning("Unknown field type '%s', returning as string", field_type)
    return value


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
