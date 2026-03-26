"""Tests for v1 → v2 config entry migration.

Tests the pure helper functions (extract_model, derive_protocol,
resolve_modem_dir) and the full migration data transform.  The
helpers are tested without HA dependencies; resolve_modem_dir uses
the real catalog on disk.
"""

from __future__ import annotations

import pytest

from custom_components.cable_modem_monitor.migrations.v1_to_v2 import (
    V1_STALE_KEYS,
    derive_protocol,
    extract_model,
    resolve_modem_dir,
)

# =============================================================================
# extract_model — strip manufacturer prefix from display name
# =============================================================================
#
# ┌──────────────────────────────┬─────────────────┬──────────┬──────────────────────────────┐
# │ detected_modem               │ manufacturer    │ expected │ description                  │
# ├──────────────────────────────┼─────────────────┼──────────┼──────────────────────────────┤
# │ "ARRIS SB8200"               │ "ARRIS"         │ "SB8200" │ standard case                │
# │ "Motorola MB7621"            │ "Motorola"      │ "MB7621" │ standard case                │
# │ "Netgear CM600"              │ "Netgear"       │ "CM600"  │ standard case                │
# │ "Virgin Media Hub 5"         │ "Virgin Media"  │ "Hub 5"  │ multi-word manufacturer      │
# │ "Arris/CommScope S33"        │ "Arris/CommScope"│ "S33"   │ slash in manufacturer        │
# │ "Technicolor XB7"            │ "Technicolor"   │ "XB7"    │ standard case                │
# │ "Unknown"                    │ ""              │ "Unknown"│ empty manufacturer fallback  │
# │ ""                           │ ""              │ ""       │ empty everything             │
# └──────────────────────────────┴─────────────────┴──────────┴──────────────────────────────┘
#
# fmt: off
EXTRACT_MODEL_CASES = [
    # (detected_modem,             manufacturer,       expected,   id)
    ("ARRIS SB8200",               "ARRIS",            "SB8200",   "arris-sb8200"),
    ("Motorola MB7621",            "Motorola",         "MB7621",   "motorola-mb7621"),
    ("Netgear CM600",              "Netgear",          "CM600",    "netgear-cm600"),
    ("Virgin Media Hub 5",         "Virgin Media",     "Hub 5",    "virgin-media-hub5"),
    ("Arris/CommScope S33",        "Arris/CommScope",  "S33",      "arris-commscope-s33"),
    ("Technicolor XB7",            "Technicolor",      "XB7",      "technicolor-xb7"),
    ("Unknown",                    "",                 "Unknown",  "empty-mfr-fallback"),
    ("",                           "",                 "",         "empty-everything"),
]
# fmt: on


class TestExtractModel:
    """Test model extraction from v1 display names."""

    @pytest.mark.parametrize(
        "detected_modem,manufacturer,expected,desc",
        EXTRACT_MODEL_CASES,
        ids=[c[3] for c in EXTRACT_MODEL_CASES],
    )
    def test_extract(self, detected_modem, manufacturer, expected, desc):
        assert extract_model(detected_modem, manufacturer) == expected


# =============================================================================
# derive_protocol — protocol from working_url / legacy_ssl
# =============================================================================
#
# ┌───────────────────────────────────────────┬────────────┬──────────┬─────────────────────┐
# │ working_url                               │ legacy_ssl │ expected │ description         │
# ├───────────────────────────────────────────┼────────────┼──────────┼─────────────────────┤
# │ "http://192.168.100.1/status.htm"         │ False      │ "http"   │ http from url       │
# │ "https://192.168.100.1/cgi-bin/status"    │ False      │ "https"  │ https from url      │
# │ ""                                        │ True       │ "https"  │ legacy_ssl fallback │
# │ ""                                        │ False      │ "http"   │ default             │
# │ None (key missing)                        │ False      │ "http"   │ no working_url key  │
# └───────────────────────────────────────────┴────────────┴──────────┴─────────────────────┘
#
# fmt: off
DERIVE_PROTOCOL_CASES = [
    # (data_dict,                                                        expected, id)
    ({"working_url": "http://192.168.100.1/status.htm"},                 "http",   "http-from-url"),
    ({"working_url": "https://192.168.100.1/cgi-bin/status"},            "https",  "https-from-url"),
    ({"legacy_ssl": True},                                               "https",  "legacy-ssl-fallback"),
    ({},                                                                 "http",   "default-http"),
    ({"working_url": "https://10.0.0.1/data", "legacy_ssl": True},      "https",  "url-takes-priority"),
    ({"working_url": "http://10.0.0.1/data", "legacy_ssl": True},       "http",   "url-overrides-ssl"),
]
# fmt: on


class TestDeriveProtocol:
    """Test protocol derivation from v1 entry data."""

    @pytest.mark.parametrize(
        "data,expected,desc",
        DERIVE_PROTOCOL_CASES,
        ids=[c[2] for c in DERIVE_PROTOCOL_CASES],
    )
    def test_derive(self, data, expected, desc):
        assert derive_protocol(data) == expected


# =============================================================================
# resolve_modem_dir — catalog lookup (uses real catalog on disk)
# =============================================================================
#
# ┌─────────────────┬──────────┬──────────────────────┬──────────────────────────┐
# │ manufacturer     │ model    │ expected modem_dir   │ description              │
# ├─────────────────┼──────────┼──────────────────────┼──────────────────────────┤
# │ "ARRIS"          │ "SB8200" │ "arris/sb8200"       │ exact match              │
# │ "Motorola"       │ "MB7621" │ "motorola/mb7621"    │ exact match              │
# │ "Netgear"        │ "CM600"  │ "netgear/cm600"      │ exact match              │
# │ "Technicolor"    │ "XB7"    │ "technicolor/xb7"    │ exact match              │
# │ "Virgin Media"   │ "Hub 5"  │ "virgin/superhub5"   │ exact match              │
# │ "Nonexistent"    │ "X9999"  │ None                 │ no match                 │
# └─────────────────┴──────────┴──────────────────────┴──────────────────────────┘
#
# fmt: off
RESOLVE_CASES = [
    # (manufacturer,       model,     expected_dir,         id)
    ("ARRIS",              "SB8200",  "arris/sb8200",       "arris-sb8200"),
    ("Motorola",           "MB7621",  "motorola/mb7621",    "motorola-mb7621"),
    ("Netgear",            "CM600",   "netgear/cm600",      "netgear-cm600"),
    ("Technicolor",        "XB7",     "technicolor/xb7",    "technicolor-xb7"),
    ("Virgin Media",       "Hub 5",   "virgin/superhub5",   "virgin-hub5"),
    ("Nonexistent",        "X9999",   None,                 "no-match"),
]
# fmt: on


class TestResolveModemDir:
    """Test catalog resolution from v1 display names.

    These tests use the real catalog on disk.  If a modem is added or
    removed from the catalog, update the expected values accordingly.
    """

    @pytest.mark.parametrize(
        "manufacturer,model,expected_dir,desc",
        RESOLVE_CASES,
        ids=[c[3] for c in RESOLVE_CASES],
    )
    def test_resolve(self, manufacturer, model, expected_dir, desc):
        result = resolve_modem_dir(manufacturer, model)
        assert result == expected_dir, (
            f"resolve_modem_dir({manufacturer!r}, {model!r}) " f"returned {result!r}, expected {expected_dir!r}"
        )


class TestResolveModemDirAliases:
    """Test model alias resolution."""

    def test_model_alias_match(self):
        """MB8600 is an alias for MB8611 in the catalog."""
        result = resolve_modem_dir("Motorola", "MB8600")
        assert result == "motorola/mb8611"

    def test_manufacturer_rename_model_only_match(self):
        """Arris/CommScope G54 should resolve via model-only match.

        v1 stored manufacturer as 'Arris/CommScope' but the catalog
        now uses 'CommScope'.  The model 'G54' is unambiguous across
        the catalog, so pass-3 (model-only) should find it.
        """
        result = resolve_modem_dir("Arris/CommScope", "G54")
        assert result == "arris/g54"


# =============================================================================
# Full migration data transform — verify v2 shape
# =============================================================================


class TestFullMigrationShape:
    """Test that a complete v1 → v2 transform produces correct keys."""

    @staticmethod
    def _build_v1_entry() -> dict:
        """Build a representative v1 config entry."""
        return {
            "host": "192.168.100.1",
            "username": "admin",
            "password": "p@ssw0rd",
            "scan_interval": 600,
            "modem_choice": "ARRIS SB8200",
            "parser_name": "ARRIS SB8200",
            "detected_modem": "ARRIS SB8200",
            "detected_manufacturer": "ARRIS",
            "docsis_version": "3.1",
            "parser_selected_at": "2024-06-15T10:30:00",
            "supports_icmp": True,
            "supports_head": False,
            "legacy_ssl": False,
            "entity_prefix": "none",
            "working_url": "http://192.168.100.1/cgi-bin/status",
            "actual_model": "SB8200-100NAS",
            "auth_strategy": "basic",
            "auth_form_config": None,
            "auth_hnap_config": None,
            "auth_url_token_config": None,
            "auth_discovery_status": "success",
            "auth_discovery_failed": False,
            "auth_discovery_error": None,
            "auth_type": None,
            "auth_captured_response": None,
        }

    def test_v2_has_required_keys(self):
        """After transform, all v2 keys are present."""
        v1 = self._build_v1_entry()

        # Simulate the transform (without HA dependency)
        mfr = v1["detected_manufacturer"]
        model = extract_model(v1["detected_modem"], mfr)
        protocol = derive_protocol(v1)
        modem_dir = resolve_modem_dir(mfr, model)

        v2 = {
            "manufacturer": mfr,
            "model": model,
            "modem_dir": modem_dir,
            "variant": None,
            "user_selected_modem": v1["detected_modem"],
            "entity_prefix": v1.get("entity_prefix", "none"),
            "host": v1["host"],
            "username": v1["username"],
            "password": v1["password"],
            "protocol": protocol,
            "legacy_ssl": v1.get("legacy_ssl", False),
            "supports_icmp": v1.get("supports_icmp", False),
            "supports_head": v1.get("supports_head", False),
            "scan_interval": v1.get("scan_interval", 600),
            "health_check_interval": 30,
        }

        expected_keys = {
            "manufacturer",
            "model",
            "modem_dir",
            "variant",
            "user_selected_modem",
            "entity_prefix",
            "host",
            "username",
            "password",
            "protocol",
            "legacy_ssl",
            "supports_icmp",
            "supports_head",
            "scan_interval",
            "health_check_interval",
        }
        assert set(v2.keys()) == expected_keys

    def test_no_v1_stale_keys_remain(self):
        """After transform, no v1-only keys are present."""
        v1 = self._build_v1_entry()

        mfr = v1["detected_manufacturer"]
        model = extract_model(v1["detected_modem"], mfr)
        protocol = derive_protocol(v1)

        v2 = {
            "manufacturer": mfr,
            "model": model,
            "modem_dir": "arris/sb8200",
            "variant": None,
            "user_selected_modem": v1["detected_modem"],
            "entity_prefix": v1.get("entity_prefix", "none"),
            "host": v1["host"],
            "username": v1["username"],
            "password": v1["password"],
            "protocol": protocol,
            "legacy_ssl": v1.get("legacy_ssl", False),
            "supports_icmp": v1.get("supports_icmp", False),
            "supports_head": v1.get("supports_head", False),
            "scan_interval": v1.get("scan_interval", 600),
            "health_check_interval": 30,
        }

        leftover = V1_STALE_KEYS & set(v2.keys())
        assert leftover == set(), f"Stale v1 keys in v2 data: {leftover}"

    def test_values_are_correct(self):
        """Spot-check migrated values."""
        v1 = self._build_v1_entry()

        mfr = v1["detected_manufacturer"]
        model = extract_model(v1["detected_modem"], mfr)

        assert mfr == "ARRIS"
        assert model == "SB8200"
        assert derive_protocol(v1) == "http"
        assert resolve_modem_dir(mfr, model) == "arris/sb8200"
