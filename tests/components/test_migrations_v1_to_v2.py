"""Tests for v1 → v2 config entry migration.

TEST DATA TABLES
================
This module uses table-driven tests. Tables are defined at the top
of the file with ASCII box-drawing comments for readability.

Tests the pure helper functions (extract_model, derive_protocol) and
the resolve_modem_dir three-pass algorithm with synthetic catalog data.
Full migration shape tests verify the schema transform without
depending on specific modem data. Catalog validity is tested in the
catalog test suite.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from solentlabs.cable_modem_monitor_core.catalog_manager import ModemSummary

from custom_components.cable_modem_monitor.migrations.v1_to_v2 import (
    V1_STALE_KEYS,
    async_migrate,
    derive_protocol,
    extract_model,
    resolve_modem_dir,
)

# =============================================================================
# Synthetic catalog for resolve_modem_dir algorithm tests
# =============================================================================

_FAKE_CATALOG = Path("/fake/catalog")

_SYNTHETIC_SUMMARIES: list[ModemSummary] = [
    ModemSummary(
        manufacturer="Solent Labs",
        model="TPS-2000",
        model_aliases=["TPS-2000-Alt"],
        path=_FAKE_CATALOG / "solentlabs" / "tps-2000",
    ),
    ModemSummary(
        manufacturer="Solent Labs",
        model="TPS-3000",
        path=_FAKE_CATALOG / "solentlabs" / "tps-3000",
    ),
    ModemSummary(
        manufacturer="Other Vendor",
        model="X500",
        path=_FAKE_CATALOG / "othervendor" / "x500",
    ),
]


# =============================================================================
# extract_model — strip manufacturer prefix from display name
# =============================================================================
#
# ┌──────────────────────────┬─────────────────┬──────────────────┬─────────────────────────┐
# │ detected_modem           │ manufacturer    │ expected         │ description             │
# ├──────────────────────────┼─────────────────┼──────────────────┼─────────────────────────┤
# │ "Vendor Model"           │ "Vendor"        │ "Model"          │ standard prefix strip   │
# │ "Multi Word Suffix"      │ "Multi Word"    │ "Suffix"         │ multi-word manufacturer │
# │ "A/B Model"              │ "A/B"           │ "Model"          │ slash in manufacturer   │
# │ "Vendor Long Model Name" │ "Vendor"        │ "Long Model Name"│ multi-word model        │
# │ "Unknown"                │ ""              │ "Unknown"        │ empty manufacturer      │
# │ ""                       │ ""              │ ""               │ empty everything        │
# └──────────────────────────┴─────────────────┴──────────────────┴─────────────────────────┘
#
# fmt: off
EXTRACT_MODEL_CASES = [
    # (detected_modem,           manufacturer,    expected,           id)
    ("Vendor Model",             "Vendor",        "Model",            "standard-prefix"),
    ("Multi Word Suffix",        "Multi Word",    "Suffix",           "multi-word-mfr"),
    ("A/B Model",                "A/B",           "Model",            "slash-in-mfr"),
    ("Vendor Long Model Name",   "Vendor",        "Long Model Name",  "multi-word-model"),
    ("Unknown",                  "",              "Unknown",          "empty-mfr-fallback"),
    ("",                         "",              "",                 "empty-everything"),
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
# │ "https://10.0.0.1/data" + legacy_ssl      │ True       │ "https"  │ url takes priority  │
# │ "http://10.0.0.1/data" + legacy_ssl       │ True       │ "http"   │ url overrides ssl   │
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
# resolve_modem_dir — three-pass algorithm (synthetic catalog)
# =============================================================================
#
# ┌──────────────────┬─────────────┬────────────────────┬───────────────────────────┐
# │ manufacturer     │ model       │ expected           │ description               │
# ├──────────────────┼─────────────┼────────────────────┼───────────────────────────┤
# │ "Solent Labs"    │ "TPS-2000"      │ "solentlabs/tps-2000"  │ pass-1 exact match        │
# │ "solent labs"    │ "tps-2000"  │ "solentlabs/tps-2000"  │ pass-1 case-insensitive   │
# │ "Solent Labs"    │ "TPS-2000-Alt"  │ "solentlabs/tps-2000"  │ pass-2 alias match        │
# │ "Solent Labs"    │ "TPS-3000"      │ "solentlabs/tps-3000"  │ pass-1 second modem       │
# │ "Wrong Mfr"      │ "TPS-3000"      │ "solentlabs/tps-3000"  │ pass-3 model-only unique  │
# │ "Unknown"        │ "X999"      │ None               │ no match                  │
# └──────────────────┴─────────────┴────────────────────┴───────────────────────────┘
#
# fmt: off
RESOLVE_CASES = [
    # (manufacturer,      model,       expected,              id)
    ("Solent Labs",       "TPS-2000",      "solentlabs/tps-2000",     "pass-1-exact"),
    ("solent labs",       "tps-2000",  "solentlabs/tps-2000",     "pass-1-case-insensitive"),
    ("Solent Labs",       "TPS-2000-Alt",  "solentlabs/tps-2000",     "pass-2-alias"),
    ("Solent Labs",       "TPS-3000",      "solentlabs/tps-3000",     "pass-1-second-modem"),
    ("Wrong Mfr",         "TPS-3000",      "solentlabs/tps-3000",     "pass-3-model-only-unique"),
    ("Unknown",           "X999",      None,                  "no-match"),
]
# fmt: on


class TestResolveModemDir:
    """Test three-pass catalog resolution with synthetic data.

    Mocks list_modems and CATALOG_PATH to test the algorithm without
    touching the real catalog. Catalog validity is tested in the
    catalog test suite.
    """

    @pytest.mark.parametrize(
        "manufacturer,model,expected,desc",
        RESOLVE_CASES,
        ids=[c[3] for c in RESOLVE_CASES],
    )
    def test_resolve(self, manufacturer, model, expected, desc):
        with (
            patch(
                "custom_components.cable_modem_monitor.migrations.v1_to_v2.list_modems",
                return_value=_SYNTHETIC_SUMMARIES,
            ),
            patch(
                "custom_components.cable_modem_monitor.migrations.v1_to_v2.CATALOG_PATH",
                _FAKE_CATALOG,
            ),
        ):
            result = resolve_modem_dir(manufacturer, model)
        assert result == expected

    def test_pass3_ambiguous_returns_none(self):
        """Pass-3 returns None when model matches multiple catalog entries."""
        # Add a second modem with the same model name
        ambiguous_summaries = [
            *_SYNTHETIC_SUMMARIES,
            ModemSummary(
                manufacturer="Another Vendor",
                model="TPS-3000",
                path=_FAKE_CATALOG / "anothervendor" / "tps-3000",
            ),
        ]
        with (
            patch(
                "custom_components.cable_modem_monitor.migrations.v1_to_v2.list_modems",
                return_value=ambiguous_summaries,
            ),
            patch(
                "custom_components.cable_modem_monitor.migrations.v1_to_v2.CATALOG_PATH",
                _FAKE_CATALOG,
            ),
        ):
            # "Wrong Mfr" + "TPS-3000" — pass-1 fails, pass-2 fails, pass-3 finds 2 matches
            result = resolve_modem_dir("Wrong Mfr", "TPS-3000")
        assert result is None


# =============================================================================
# Full migration data transform — verify v2 shape (generic names)
# =============================================================================

# v2 schema: the complete set of keys that must exist after migration
V2_REQUIRED_KEYS = frozenset(
    {
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
)


def _build_v1_entry() -> dict:
    """Build a representative v1 config entry with generic names."""
    return {
        "host": "192.168.100.1",
        "username": "admin",
        "password": "p@ssw0rd",
        "scan_interval": 600,
        "modem_choice": "Vendor Model",
        "parser_name": "Vendor Model",
        "detected_modem": "Vendor Model",
        "detected_manufacturer": "Vendor",
        "docsis_version": "3.1",
        "parser_selected_at": "2024-06-15T10:30:00",
        "supports_icmp": True,
        "supports_head": False,
        "legacy_ssl": False,
        "entity_prefix": "none",
        "working_url": "http://192.168.100.1/status.htm",
        "actual_model": "Model-100",
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


def _transform_v1_to_v2(v1: dict, modem_dir: str) -> dict:
    """Apply the v1 → v2 key mapping (pure, no HA dependency).

    Mirrors the transform in async_migrate but without async/HA calls.
    """
    mfr = v1["detected_manufacturer"]
    model = extract_model(v1["detected_modem"], mfr)
    protocol = derive_protocol(v1)

    return {
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


class TestFullMigrationShape:
    """Test that a complete v1 → v2 transform produces correct keys and values."""

    def test_v2_has_all_required_keys(self):
        """After transform, all v2 keys are present."""
        v1 = _build_v1_entry()
        v2 = _transform_v1_to_v2(v1, modem_dir="vendor/model")
        assert set(v2.keys()) == V2_REQUIRED_KEYS

    def test_no_v1_stale_keys_remain(self):
        """After transform, no v1-only keys leak into v2."""
        v1 = _build_v1_entry()
        v2 = _transform_v1_to_v2(v1, modem_dir="vendor/model")
        leftover = V1_STALE_KEYS & set(v2.keys())
        assert leftover == set(), f"Stale v1 keys in v2 data: {leftover}"

    def test_values_are_correct(self):
        """Spot-check migrated values from the generic v1 entry."""
        v1 = _build_v1_entry()
        v2 = _transform_v1_to_v2(v1, modem_dir="vendor/model")

        assert v2["manufacturer"] == "Vendor"
        assert v2["model"] == "Model"
        assert v2["protocol"] == "http"
        assert v2["modem_dir"] == "vendor/model"
        assert v2["host"] == "192.168.100.1"
        assert v2["supports_icmp"] is True
        assert v2["supports_head"] is False
        assert v2["health_check_interval"] == 30
        assert v2["variant"] is None

    def test_defaults_when_optional_keys_missing(self):
        """Missing optional v1 keys get correct v2 defaults."""
        v1_minimal = {
            "detected_modem": "Vendor Model",
            "detected_manufacturer": "Vendor",
            "host": "10.0.0.1",
            "username": "",
            "password": "",
        }
        v2 = _transform_v1_to_v2(v1_minimal, modem_dir="vendor/model")

        assert v2["entity_prefix"] == "none"
        assert v2["legacy_ssl"] is False
        assert v2["supports_icmp"] is False
        assert v2["supports_head"] is False
        assert v2["scan_interval"] == 600
        assert v2["health_check_interval"] == 30


# =============================================================================
# async_migrate — HA wrapper (mocked executor + catalog)
# =============================================================================


class TestAsyncMigrate:
    """Test the async_migrate HA wrapper with mocked I/O."""

    async def test_success(self):
        """Successful migration updates entry to v2."""
        hass = MagicMock()
        entry = MagicMock()
        entry.data = _build_v1_entry()
        entry.entry_id = "test_id"

        async def _mock_executor(func, *args):
            return func(*args)

        hass.async_add_executor_job = _mock_executor

        with patch(
            "custom_components.cable_modem_monitor.migrations.v1_to_v2.resolve_modem_dir",
            return_value="vendor/model",
        ):
            result = await async_migrate(hass, entry)

        assert result is True
        hass.config_entries.async_update_entry.assert_called_once()
        call_kwargs = hass.config_entries.async_update_entry.call_args
        assert call_kwargs.kwargs["version"] == 2
        new_data = call_kwargs.kwargs["data"]
        assert set(new_data.keys()) == V2_REQUIRED_KEYS

    async def test_resolution_failure(self):
        """Failed catalog resolution returns False without updating."""
        hass = MagicMock()
        entry = MagicMock()
        entry.data = _build_v1_entry()
        entry.entry_id = "test_id"

        async def _mock_executor(func, *args):
            return func(*args)

        hass.async_add_executor_job = _mock_executor

        with patch(
            "custom_components.cable_modem_monitor.migrations.v1_to_v2.resolve_modem_dir",
            return_value=None,
        ):
            result = await async_migrate(hass, entry)

        assert result is False
        hass.config_entries.async_update_entry.assert_not_called()
