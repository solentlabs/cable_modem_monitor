"""Tier 1 canonical field constants.

Core validates these fields and uses them for entity identity, health checks,
and status derivation. Parsers must use exactly these names.

See FIELD_REGISTRY.md for the full three-tier system.
"""

from __future__ import annotations

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
        "network_access",
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
    }
)
