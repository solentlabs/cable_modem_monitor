"""Tier 1 canonical field constants.

Core validates these fields and uses them for entity identity, health checks,
and status derivation. Parsers must use exactly these names.

See FIELD_REGISTRY.md for the full three-tier system.
"""

from __future__ import annotations

from typing import Any

# --- Downstream canonical fields ---

DOWNSTREAM_FIELDS: frozenset[str] = frozenset(
    {
        "channel_id",
        "frequency",
        "power",
        "snr",
        "lock_status",
        "modulation",
        "channel_type",
        "corrected",
        "uncorrected",
    }
)

# --- Upstream canonical fields ---

UPSTREAM_FIELDS: frozenset[str] = frozenset(
    {
        "channel_id",
        "frequency",
        "power",
        "lock_status",
        "modulation",
        "channel_type",
        "symbol_rate",
    }
)

# --- System info canonical fields ---

SYSTEM_INFO_FIELDS: frozenset[str] = frozenset(
    {
        "software_version",
        "hardware_version",
        "system_uptime",
        "docsis_status",
    }
)

# --- Required fields per channel (must be present and non-null) ---

CHANNEL_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {
        "channel_id",
        "channel_type",
    }
)

# --- Canonical channel_type values ---

DOWNSTREAM_CHANNEL_TYPES: frozenset[str] = frozenset({"qam", "ofdm"})
UPSTREAM_CHANNEL_TYPES: frozenset[str] = frozenset({"atdma", "ofdma"})
ALL_CHANNEL_TYPES: frozenset[str] = DOWNSTREAM_CHANNEL_TYPES | UPSTREAM_CHANNEL_TYPES

# --- Canonical lock_status values ---

LOCK_STATUS_VALUES: frozenset[str] = frozenset({"locked", "not_locked"})

# --- Field type names (used in parser.yaml column/row/channel mappings) ---

FIELD_TYPES: frozenset[str] = frozenset(
    {
        "integer",
        "float",
        "string",
        "frequency",
        "boolean",
        "lock_status",
        "modulation",
        "uptime",
    }
)

# --- Canonical channel key order (for JSON serialization) ---

CHANNEL_FIELD_ORDER: tuple[str, ...] = (
    "lock_status",
    "channel_type",
    "channel_id",
    "channel_number",
    "source_channel_number",
    "modulation",
    "frequency",
    "symbol_rate",
    "power",
    "snr",
    "corrected",
    "uncorrected",
)


def canonicalize_channel_keys(channel: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict with keys in canonical presentation order.

    Tier 1 keys (see ``CHANNEL_FIELD_ORDER``) appear first in the declared
    order. Tier 2/3 pass-through keys preserve their original insertion
    order and are appended at the end. Missing keys are skipped.
    """
    ordered: dict[str, Any] = {key: channel[key] for key in CHANNEL_FIELD_ORDER if key in channel}
    for key, value in channel.items():
        if key not in ordered:
            ordered[key] = value
    return ordered
