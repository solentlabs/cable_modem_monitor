"""Field name resolution and type/unit detection.

Three-tier header-to-field matching (T1: canonical, T2: registered,
T3: snake_case fallback), JSON key mapping, and value-based type
and unit inference.

Maps are loaded from ``field_registry.json`` via ``registry_loader``.

Per docs/ONBOARDING_SPEC.md Phase 6 and docs/FIELD_REGISTRY.md.
"""

from __future__ import annotations

import re

from .registry_loader import (
    get_field_type_map,
    get_header_field_map,
    get_header_unit_map,
    get_json_key_map,
)

# -----------------------------------------------------------------------
# Module-level map caches (built once from registry JSON)
# -----------------------------------------------------------------------

HEADER_FIELD_MAP: dict[str, tuple[str, int]] = get_header_field_map()
JSON_KEY_MAP: dict[str, tuple[str, int]] = get_json_key_map()
_HEADER_UNIT_MAP: dict[str, str] = get_header_unit_map()
_FIELD_TYPE_MAP: dict[str, str] = get_field_type_map()

# Unit patterns for value-based type and unit detection
_UNIT_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # Frequency: Hz or MHz suffix
    (re.compile(r"^-?\d[\d,]*\s*Hz$", re.IGNORECASE), "frequency", "Hz"),
    (re.compile(r"^-?\d[\d,]*\.?\d*\s*MHz$", re.IGNORECASE), "frequency", "MHz"),
    # Power: dBmV suffix
    (re.compile(r"^-?\d+\.?\d*\s*dBmV$", re.IGNORECASE), "float", "dBmV"),
    # SNR: dB suffix
    (re.compile(r"^-?\d+\.?\d*\s*dB$", re.IGNORECASE), "float", "dB"),
    # Frequency: large integer without suffix (likely Hz)
    (re.compile(r"^[1-9]\d{6,}$"), "frequency", ""),
]

# Type sets derived from registry
_KNOWN_INTEGER_FIELDS = frozenset(name for name, ftype in _FIELD_TYPE_MAP.items() if ftype == "integer")
_KNOWN_STRING_FIELDS = frozenset(name for name, ftype in _FIELD_TYPE_MAP.items() if ftype == "string")


# -----------------------------------------------------------------------
# Three-tier matching
# -----------------------------------------------------------------------


def match_header_to_field(header: str) -> tuple[str, int, str]:
    """Map a table header or row label to a canonical field name.

    Returns (field_name, tier, header_unit) or ("", 0, "") if no match.
    Tier 1/2 from registry; Tier 3 via snake_case fallback.

    ``header_unit`` is non-empty only when the header itself declares
    a unit (e.g., ``"Freq. (MHz)"`` -> unit ``"MHz"``).
    """
    normalized = header.strip().lower()

    # Tier 1/2 lookup
    if normalized in HEADER_FIELD_MAP:
        field_name, tier = HEADER_FIELD_MAP[normalized]
        unit = _HEADER_UNIT_MAP.get(normalized, "")
        return field_name, tier, unit

    # Tier 3: snake_case fallback for non-empty headers
    if normalized and not normalized.isdigit():
        return to_snake_case(header.strip()), 3, ""

    return "", 0, ""


def match_json_key_to_field(key: str) -> tuple[str, int]:
    """Map a JSON key to a canonical field name.

    Returns (field_name, tier) or ("", 0) if no match.
    """
    normalized = key.strip().lower()

    if normalized in JSON_KEY_MAP:
        return JSON_KEY_MAP[normalized]

    # Tier 3: snake_case fallback
    if normalized:
        return to_snake_case(key.strip()), 3

    return "", 0


def to_snake_case(text: str) -> str:
    """Convert text to snake_case per FIELD_REGISTRY naming rules."""
    # Insert underscores before uppercase letters (camelCase -> snake_case)
    result = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    # Replace non-alphanumeric with underscores
    result = re.sub(r"[^a-zA-Z0-9]", "_", result)
    # Collapse multiple underscores
    result = re.sub(r"_+", "_", result)
    return result.strip("_").lower()


# -----------------------------------------------------------------------
# Type and unit detection
# -----------------------------------------------------------------------


def detect_field_type(
    field_name: str,
    sample_values: list[str],
    header_unit: str = "",
) -> tuple[str, str]:
    """Infer field type and unit from field name and sample values.

    Args:
        field_name: Canonical field name from matching.
        sample_values: Sample data values from the column/row.
        header_unit: Unit declared in the header text (takes priority).

    Returns:
        Tuple of (type_name, unit_suffix).
    """
    # Known field types override value-based detection
    result = _detect_known_field_type(field_name, sample_values, header_unit)
    if result is not None:
        return result

    # Header unit provides type hint even for unknown fields
    if header_unit:
        inferred_type = _type_from_unit(header_unit)
        if inferred_type:
            return inferred_type, header_unit

    # Value-based inference
    return _infer_type_from_values(sample_values)


def _detect_known_field_type(
    field_name: str,
    sample_values: list[str],
    header_unit: str,
) -> tuple[str, str] | None:
    """Check if field_name has a known type. Returns None if unknown."""
    if field_name == "frequency":
        # Header unit takes priority over value-based detection
        unit = header_unit if header_unit else _detect_frequency_unit(sample_values)
        return "frequency", unit
    if field_name in _KNOWN_INTEGER_FIELDS:
        return "integer", header_unit
    if field_name == "power":
        unit = header_unit if header_unit else _detect_unit_suffix(sample_values, ("dBmV", "dBmv"))
        return "float", unit
    if field_name == "snr":
        unit = header_unit if header_unit else _detect_unit_suffix(sample_values, ("dB", "db"))
        return "float", unit
    if field_name in _KNOWN_STRING_FIELDS:
        return "string", ""
    return None


def _type_from_unit(unit: str) -> str:
    """Infer type from a unit string."""
    lower = unit.lower()
    if lower in ("hz", "mhz", "khz", "ghz"):
        return "frequency"
    if lower in ("dbmv", "db"):
        return "float"
    return ""


def _infer_type_from_values(sample_values: list[str]) -> tuple[str, str]:
    """Infer type and unit from sample data values."""
    for value in sample_values:
        if not value or not value.strip():
            continue

        # Check unit patterns
        for pattern, ftype, unit in _UNIT_PATTERNS:
            if pattern.match(value.strip()):
                return ftype, unit

        # Try integer then float
        stripped = value.strip()
        try:
            int(stripped)
            return "integer", ""
        except ValueError:
            pass
        try:
            float(stripped.split()[0])
            return "float", ""
        except ValueError:
            pass

    return "string", ""


def _detect_frequency_unit(values: list[str]) -> str:
    """Detect whether frequency values include a unit suffix."""
    for value in values:
        stripped = value.strip()
        if not stripped:
            continue
        if stripped.lower().endswith("hz"):
            if stripped.lower().endswith("mhz"):
                return "MHz"
            return "Hz"
    return ""


def _detect_unit_suffix(values: list[str], candidates: tuple[str, ...]) -> str:
    """Check if sample values include a known unit suffix."""
    for value in values:
        stripped = value.strip()
        for unit in candidates:
            if stripped.endswith(unit) or stripped.endswith(unit.lower()):
                return candidates[0]  # Return canonical form
    return ""
