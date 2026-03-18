"""Field name resolution and type/unit detection.

Three-tier header-to-field matching (T1: canonical, T2: registered,
T3: snake_case fallback), JSON key mapping, and value-based type
and unit inference.

Per docs/ONBOARDING_SPEC.md Phase 6 and docs/FIELD_REGISTRY.md.
"""

from __future__ import annotations

import re

# -----------------------------------------------------------------------
# Header-to-field mapping table (ONBOARDING_SPEC Phase 6)
# -----------------------------------------------------------------------

# Maps lowercase header text -> (canonical_field, tier)
HEADER_FIELD_MAP: dict[str, tuple[str, int]] = {
    # Tier 1 canonical fields
    "channel id": ("channel_id", 1),
    "channel": ("channel_id", 1),
    "ch": ("channel_id", 1),
    "frequency": ("frequency", 1),
    "freq": ("frequency", 1),
    "power": ("power", 1),
    "power level": ("power", 1),
    "pwr": ("power", 1),
    "snr": ("snr", 1),
    "snr/mer": ("snr", 1),
    "mer": ("snr", 1),
    "signal to noise": ("snr", 1),
    "signal to noise ratio": ("snr", 1),
    "corrected": ("corrected", 1),
    "correctable": ("corrected", 1),
    "total correctable codewords": ("corrected", 1),
    "uncorrected": ("uncorrected", 1),
    "uncorrectable": ("uncorrected", 1),
    "total uncorrectable codewords": ("uncorrected", 1),
    "modulation": ("modulation", 1),
    "mod": ("modulation", 1),
    "lock status": ("lock_status", 1),
    "status": ("lock_status", 1),
    "symbol rate": ("symbol_rate", 1),
    "symb. rate": ("symbol_rate", 1),
    # Tier 2 registered fields
    "channel width": ("channel_width", 2),
    "bandwidth": ("channel_width", 2),
    "active subcarriers": ("active_subcarriers", 2),
    "fft size": ("fft_size", 2),
    "profile id": ("profile_id", 2),
    "ranging status": ("ranging_status", 2),
}

# JSON key mapping -- camelCase keys common in JSON APIs
JSON_KEY_MAP: dict[str, tuple[str, int]] = {
    "channelid": ("channel_id", 1),
    "channel_id": ("channel_id", 1),
    "frequency": ("frequency", 1),
    "freq": ("frequency", 1),
    "power": ("power", 1),
    "powerlevel": ("power", 1),
    "power_level": ("power", 1),
    "snr": ("snr", 1),
    "rxmer": ("snr", 1),
    "rx_mer": ("snr", 1),
    "corrected": ("corrected", 1),
    "correctederrors": ("corrected", 1),
    "corrected_errors": ("corrected", 1),
    "uncorrected": ("uncorrected", 1),
    "uncorrectederrors": ("uncorrected", 1),
    "uncorrected_errors": ("uncorrected", 1),
    "modulation": ("modulation", 1),
    "lockstatus": ("lock_status", 1),
    "lock_status": ("lock_status", 1),
    "symbolrate": ("symbol_rate", 1),
    "symbol_rate": ("symbol_rate", 1),
    "channeltype": ("channel_type", 1),
    "channel_type": ("channel_type", 1),
    # Tier 2
    "channelwidth": ("channel_width", 2),
    "channel_width": ("channel_width", 2),
}

# Unit patterns for type and unit detection
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

# Known field -> type mappings
_KNOWN_INTEGER_FIELDS = frozenset(
    {"channel_id", "corrected", "uncorrected", "symbol_rate", "fft_size", "active_subcarriers"}
)
_KNOWN_STRING_FIELDS = frozenset({"modulation", "lock_status", "channel_type", "ranging_status"})


# -----------------------------------------------------------------------
# Three-tier matching
# -----------------------------------------------------------------------


def match_header_to_field(header: str) -> tuple[str, int]:
    """Map a table header or row label to a canonical field name.

    Returns (field_name, tier) or ("", 0) if no match.
    Tier 1/2 from HEADER_FIELD_MAP; Tier 3 via snake_case fallback.
    """
    normalized = header.strip().lower()

    # Tier 1/2 lookup
    if normalized in HEADER_FIELD_MAP:
        return HEADER_FIELD_MAP[normalized]

    # Tier 3: snake_case fallback for non-empty headers
    if normalized and not normalized.isdigit():
        return to_snake_case(header.strip()), 3

    return "", 0


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


def detect_field_type(field_name: str, sample_values: list[str]) -> tuple[str, str]:
    """Infer field type and unit from field name and sample values.

    Returns (type_name, unit_suffix).
    """
    # Known field types override value-based detection
    result = _detect_known_field_type(field_name, sample_values)
    if result is not None:
        return result

    # Value-based inference
    return _infer_type_from_values(sample_values)


def _detect_known_field_type(field_name: str, sample_values: list[str]) -> tuple[str, str] | None:
    """Check if field_name has a known type. Returns None if unknown."""
    if field_name == "frequency":
        return "frequency", _detect_frequency_unit(sample_values)
    if field_name in _KNOWN_INTEGER_FIELDS:
        return "integer", ""
    if field_name == "power":
        return "float", _detect_unit_suffix(sample_values, ("dBmV", "dBmv"))
    if field_name == "snr":
        return "float", _detect_unit_suffix(sample_values, ("dB", "db"))
    if field_name in _KNOWN_STRING_FIELDS:
        return "string", ""
    return None


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
