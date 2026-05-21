"""Tests for catalog_manager — list_modems(), list_variants(), and dataclasses."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from solentlabs.cable_modem_monitor_core.catalog_manager import (
    ModemSummary,
    VariantInfo,
    list_modems,
    list_variants,
)


def _write_modem_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a modem.yaml file to the given directory."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "modem.yaml").write_text(yaml.dump(data))


class TestListModems:
    """list_modems() catalog discovery."""

    def test_discovers_modems(self, tmp_path: Path) -> None:
        """Finds modem.yaml files in nested directories."""
        _write_modem_yaml(
            tmp_path / "solent" / "t100",
            {
                "manufacturer": "Solent Labs",
                "model": "T100",
                "transport": "http",
                "default_host": "192.168.100.1",
                "auth": {"strategy": "none"},
                "hardware": {"docsis_version": "3.0"},
                "status": "confirmed",
            },
        )
        _write_modem_yaml(
            tmp_path / "solent" / "t200",
            {
                "manufacturer": "Solent Labs",
                "model": "T200",
                "transport": "hnap",
                "default_host": "10.0.0.1",
                "auth": {"strategy": "hnap_login"},
                "hardware": {"docsis_version": "3.1"},
                "status": "awaiting_verification",
            },
        )

        results = list_modems(tmp_path)

        assert len(results) == 2
        models = {r.model for r in results}
        assert models == {"T100", "T200"}

    def test_extracts_all_fields(self, tmp_path: Path) -> None:
        """All ModemSummary fields populated from modem.yaml."""
        _write_modem_yaml(
            tmp_path / "solent" / "t100",
            {
                "manufacturer": "Solent Labs",
                "model": "T100",
                "model_aliases": ["Surfboard"],
                "brands": ["Comcast"],
                "transport": "http",
                "default_host": "10.0.0.1",
                "auth": {"strategy": "cookie"},
                "hardware": {"docsis_version": "3.1"},
                "status": "confirmed",
            },
        )

        results = list_modems(tmp_path)
        summary = results[0]

        assert summary.manufacturer == "Solent Labs"
        assert summary.model == "T100"
        assert summary.model_aliases == ["Surfboard"]
        assert summary.brands == ["Comcast"]
        assert summary.docsis_version == "3.1"
        assert summary.status == "confirmed"
        assert summary.default_host == "10.0.0.1"
        assert summary.auth_strategy == "cookie"
        assert summary.transport == "http"
        assert summary.path == tmp_path / "solent" / "t100"
        assert summary.sibling_dirs == []

    def test_groups_same_model(self, tmp_path: Path) -> None:
        """Directories sharing the same manufacturer+model collapse into one entry."""
        _write_modem_yaml(
            tmp_path / "solent" / "t100",
            {"manufacturer": "Solent Labs", "model": "T100", "transport": "http", "auth": {"strategy": "url_token"}},
        )
        _write_modem_yaml(
            tmp_path / "solent" / "t100-hnap",
            {"manufacturer": "Solent Labs", "model": "T100", "transport": "hnap", "auth": {"strategy": "hnap"}},
        )

        results = list_modems(tmp_path)

        assert len(results) == 1
        assert results[0].model == "T100"
        assert results[0].sibling_dirs == [tmp_path / "solent" / "t100-hnap"]

    def test_case_insensitive_grouping(self, tmp_path: Path) -> None:
        """Manufacturer case variations (ARRIS vs Arris) are treated as the same group."""
        _write_modem_yaml(
            tmp_path / "a" / "x",
            {"manufacturer": "ARRIS", "model": "SB8200", "auth": {"strategy": "url_token"}},
        )
        _write_modem_yaml(
            tmp_path / "b" / "x",
            {"manufacturer": "Arris", "model": "SB8200", "auth": {"strategy": "hnap"}},
        )

        results = list_modems(tmp_path)

        assert len(results) == 1
        assert len(results[0].sibling_dirs) == 1

    def test_empty_catalog(self, tmp_path: Path) -> None:
        """Empty catalog returns empty list."""
        results = list_modems(tmp_path)
        assert results == []

    def test_nonexistent_path(self, tmp_path: Path) -> None:
        """Missing catalog path returns empty list."""
        results = list_modems(tmp_path / "does_not_exist")
        assert results == []

    def test_skips_bad_yaml(self, tmp_path: Path) -> None:
        """Invalid YAML files are skipped, not fatal."""
        _write_modem_yaml(
            tmp_path / "good" / "t100",
            {
                "manufacturer": "Solent Labs",
                "model": "T100",
                "transport": "http",
                "default_host": "192.168.100.1",
            },
        )
        # Write invalid YAML
        bad_dir = tmp_path / "bad" / "broken"
        bad_dir.mkdir(parents=True)
        (bad_dir / "modem.yaml").write_text(": : invalid yaml [[[")

        results = list_modems(tmp_path)
        assert len(results) == 1
        assert results[0].model == "T100"

    def test_skips_missing_identity(self, tmp_path: Path) -> None:
        """YAML without manufacturer/model is skipped."""
        _write_modem_yaml(
            tmp_path / "incomplete" / "x1",
            {
                "transport": "http",
                "default_host": "192.168.100.1",
            },
        )

        results = list_modems(tmp_path)
        assert results == []

    def test_defaults_for_optional_fields(self, tmp_path: Path) -> None:
        """Missing optional fields use sensible defaults."""
        _write_modem_yaml(
            tmp_path / "minimal" / "t100",
            {
                "manufacturer": "Solent Labs",
                "model": "T100",
            },
        )

        results = list_modems(tmp_path)
        summary = results[0]

        assert summary.model_aliases == []
        assert summary.brands == []
        assert summary.docsis_version is None
        assert summary.status == "awaiting_verification"
        assert summary.default_host == "192.168.100.1"
        assert summary.auth_strategy == "none"
        assert summary.transport == "http"
        assert summary.sibling_dirs == []

    def test_groups_same_model_primary_is_alphabetically_first(self, tmp_path: Path) -> None:
        """First-encountered directory (sorted path) becomes the primary entry."""
        _write_modem_yaml(
            tmp_path / "solent" / "t100",
            {"manufacturer": "Solent Labs", "model": "T100", "auth": {"strategy": "url_token"}},
        )
        _write_modem_yaml(
            tmp_path / "solent" / "t100-hnap",
            {"manufacturer": "Solent Labs", "model": "T100", "auth": {"strategy": "hnap"}},
        )

        results = list_modems(tmp_path)

        # t100 sorts before t100-hnap, so it's primary
        assert results[0].path == tmp_path / "solent" / "t100"
        assert results[0].auth_strategy == "url_token"

    def test_groups_three_way(self, tmp_path: Path) -> None:
        """Three directories sharing the same model produce one entry with two siblings."""
        for suffix, strategy in [("", "url_token"), ("-hnap", "hnap"), ("-v2", "basic")]:
            _write_modem_yaml(
                tmp_path / "solent" / f"t100{suffix}",
                {"manufacturer": "Solent Labs", "model": "T100", "auth": {"strategy": strategy}},
            )

        results = list_modems(tmp_path)

        assert len(results) == 1
        assert len(results[0].sibling_dirs) == 2

    def test_aggregate_status_named_variant_promotes_model(self, tmp_path: Path) -> None:
        """Named variant confirmed → aggregate is confirmed even if base modem.yaml is not."""
        modem_dir = tmp_path / "solent" / "t100"
        _write_modem_yaml(
            modem_dir,
            {"manufacturer": "Solent Labs", "model": "T100", "status": "awaiting_verification"},
        )
        (modem_dir / "modem-form.yaml").write_text(
            yaml.dump({"manufacturer": "Solent Labs", "model": "T100", "status": "confirmed"})
        )

        results = list_modems(tmp_path)

        assert results[0].status == "confirmed"

    def test_aggregate_status_all_unconfirmed_stays_unconfirmed(self, tmp_path: Path) -> None:
        """All variants unconfirmed → model aggregate remains unconfirmed."""
        modem_dir = tmp_path / "solent" / "t100"
        _write_modem_yaml(
            modem_dir,
            {"manufacturer": "Solent Labs", "model": "T100", "status": "awaiting_verification"},
        )
        (modem_dir / "modem-form.yaml").write_text(
            yaml.dump({"manufacturer": "Solent Labs", "model": "T100", "status": "awaiting_verification"})
        )

        results = list_modems(tmp_path)

        assert results[0].status != "confirmed"

    def test_aggregate_status_sibling_confirmed_promotes_model(self, tmp_path: Path) -> None:
        """Sibling directory has confirmed variant → model aggregate is confirmed."""
        _write_modem_yaml(
            tmp_path / "solent" / "t100",
            {"manufacturer": "Solent Labs", "model": "T100", "status": "awaiting_verification"},
        )
        _write_modem_yaml(
            tmp_path / "solent" / "t100-hnap",
            {"manufacturer": "Solent Labs", "model": "T100", "status": "confirmed"},
        )

        results = list_modems(tmp_path)

        assert results[0].status == "confirmed"

    def test_aggregate_status_primary_confirmed_sibling_unconfirmed(self, tmp_path: Path) -> None:
        """Primary confirmed + sibling unconfirmed → model confirmed (at least one confirmed)."""
        _write_modem_yaml(
            tmp_path / "solent" / "t100",
            {"manufacturer": "Solent Labs", "model": "T100", "status": "confirmed"},
        )
        _write_modem_yaml(
            tmp_path / "solent" / "t100-hnap",
            {"manufacturer": "Solent Labs", "model": "T100", "status": "awaiting_verification"},
        )

        results = list_modems(tmp_path)

        assert results[0].status == "confirmed"


class TestModemSummary:
    """ModemSummary dataclass construction."""

    def test_defaults(self) -> None:
        """Default values for optional fields."""
        summary = ModemSummary(manufacturer="Solent Labs", model="T100")
        assert summary.model_aliases == []
        assert summary.brands == []
        assert summary.docsis_version is None
        assert summary.status == "awaiting_verification"
        assert summary.default_host == "192.168.100.1"
        assert summary.auth_strategy == "none"
        assert summary.transport == "http"
        assert summary.sibling_dirs == []


# =====================================================================
# list_variants()
# =====================================================================


def _write_variant_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a variant YAML file at the given path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data))


class TestListVariants:
    """list_variants() variant discovery."""

    def test_single_variant(self, tmp_path: Path) -> None:
        """Directory with only modem.yaml returns one variant (name=None)."""
        _write_variant_yaml(
            tmp_path / "modem.yaml",
            {"auth": {"strategy": "none"}, "isps": ["Comcast"]},
        )
        results = list_variants(tmp_path)
        assert len(results) == 1
        assert results[0].name is None
        assert results[0].auth_strategy == "none"
        assert results[0].isps == ["Comcast"]

    def test_multiple_variants(self, tmp_path: Path) -> None:
        """Directory with modem.yaml + modem-{name}.yaml returns all."""
        _write_variant_yaml(
            tmp_path / "modem.yaml",
            {"auth": {"strategy": "none"}, "isps": ["Spectrum"]},
        )
        _write_variant_yaml(
            tmp_path / "modem-form-nonce.yaml",
            {"auth": {"strategy": "form_nonce"}, "isps": ["Comcast"]},
        )
        results = list_variants(tmp_path)
        assert len(results) == 2
        # Default variant first
        assert results[0].name is None
        assert results[0].auth_strategy == "none"
        # Named variant second
        assert results[1].name == "form-nonce"
        assert results[1].auth_strategy == "form_nonce"
        assert results[1].isps == ["Comcast"]

    def test_default_variant_sorted_first(self, tmp_path: Path) -> None:
        """Default variant (modem.yaml) always first regardless of sort."""
        _write_variant_yaml(
            tmp_path / "modem-basic.yaml",
            {"auth": {"strategy": "basic"}},
        )
        _write_variant_yaml(
            tmp_path / "modem.yaml",
            {"auth": {"strategy": "none"}},
        )
        results = list_variants(tmp_path)
        assert results[0].name is None
        assert results[1].name == "basic"

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns empty list."""
        results = list_variants(tmp_path)
        assert results == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """Missing directory returns empty list."""
        results = list_variants(tmp_path / "does_not_exist")
        assert results == []

    def test_skips_bad_yaml(self, tmp_path: Path) -> None:
        """Invalid YAML files are skipped, not fatal."""
        _write_variant_yaml(
            tmp_path / "modem.yaml",
            {"auth": {"strategy": "none"}},
        )
        (tmp_path / "modem-bad.yaml").write_text(": : invalid [[[")
        results = list_variants(tmp_path)
        assert len(results) == 1

    def test_notes_field(self, tmp_path: Path) -> None:
        """Notes field is extracted from variant YAML."""
        _write_variant_yaml(
            tmp_path / "modem.yaml",
            {"auth": {"strategy": "basic"}, "notes": "HTTPS variant."},
        )
        results = list_variants(tmp_path)
        assert results[0].notes == "HTTPS variant."

    def test_defaults_for_optional_fields(self, tmp_path: Path) -> None:
        """Missing optional fields use defaults."""
        _write_variant_yaml(tmp_path / "modem.yaml", {})
        results = list_variants(tmp_path)
        assert results[0].auth_strategy == "none"
        assert results[0].hw_version is None
        assert results[0].isps == []
        assert results[0].notes is None

    def test_hw_version_field_loaded(self, tmp_path: Path) -> None:
        """hardware.hw_version is surfaced in VariantInfo."""
        _write_variant_yaml(
            tmp_path / "modem.yaml",
            {"auth": {"strategy": "hnap"}, "hardware": {"docsis_version": "3.1", "hw_version": "v6"}},
        )
        results = list_variants(tmp_path)
        assert results[0].hw_version == "v6"

    def test_hw_version_top_level_ignored(self, tmp_path: Path) -> None:
        """Top-level hw_version is not used — only hardware.hw_version is."""
        _write_variant_yaml(
            tmp_path / "modem.yaml",
            {"hw_version": "WRONG", "hardware": {"docsis_version": "3.1", "hw_version": "v6"}},
        )
        results = list_variants(tmp_path)
        assert results[0].hw_version == "v6"

    def test_ignores_non_modem_yaml(self, tmp_path: Path) -> None:
        """Files like parser.yaml are not picked up."""
        _write_variant_yaml(
            tmp_path / "modem.yaml",
            {"auth": {"strategy": "none"}},
        )
        _write_variant_yaml(
            tmp_path / "parser.yaml",
            {"pages": []},
        )
        results = list_variants(tmp_path)
        assert len(results) == 1

    def test_sibling_dirs_combined(self, tmp_path: Path) -> None:
        """Sibling directories contribute their variants to the combined list."""
        main_dir = tmp_path / "main"
        sibling_dir = tmp_path / "sibling"
        _write_variant_yaml(main_dir / "modem.yaml", {"auth": {"strategy": "url_token"}})
        _write_variant_yaml(sibling_dir / "modem.yaml", {"auth": {"strategy": "hnap"}})

        results = list_variants(main_dir, sibling_dirs=[sibling_dir])

        assert len(results) == 2
        strategies = {v.auth_strategy for v in results}
        assert strategies == {"url_token", "hnap"}

    def test_sibling_dirs_default_first(self, tmp_path: Path) -> None:
        """Primary directory's default variant sorts before sibling's default."""
        main_dir = tmp_path / "main"
        sibling_dir = tmp_path / "sibling"
        _write_variant_yaml(main_dir / "modem.yaml", {"auth": {"strategy": "url_token"}})
        _write_variant_yaml(sibling_dir / "modem.yaml", {"auth": {"strategy": "hnap"}})

        results = list_variants(main_dir, sibling_dirs=[sibling_dir])

        # Primary directory (main) comes first due to stable sort
        assert results[0].path.parent == main_dir
        assert results[1].path.parent == sibling_dir

    def test_sibling_dirs_with_named_variants(self, tmp_path: Path) -> None:
        """Named variants from both primary and sibling directories appear in result."""
        main_dir = tmp_path / "main"
        sibling_dir = tmp_path / "sibling"
        _write_variant_yaml(main_dir / "modem.yaml", {"auth": {"strategy": "url_token"}})
        _write_variant_yaml(main_dir / "modem-v7.yaml", {"auth": {"strategy": "url_token"}})
        _write_variant_yaml(sibling_dir / "modem.yaml", {"auth": {"strategy": "hnap"}})

        results = list_variants(main_dir, sibling_dirs=[sibling_dir])

        assert len(results) == 3
        # Two default variants (name=None) from different directories, one named
        assert sum(1 for v in results if v.name is None) == 2
        assert any(v.name == "v7" for v in results)

    def test_sibling_dirs_none_treated_as_empty(self, tmp_path: Path) -> None:
        """sibling_dirs=None behaves identically to sibling_dirs=[]."""
        _write_variant_yaml(tmp_path / "modem.yaml", {"auth": {"strategy": "none"}})

        results_none = list_variants(tmp_path, sibling_dirs=None)
        results_empty = list_variants(tmp_path, sibling_dirs=[])

        assert len(results_none) == len(results_empty) == 1

    def test_status_loaded_from_yaml(self, tmp_path: Path) -> None:
        """Variant status is read from the YAML status field."""
        _write_variant_yaml(
            tmp_path / "modem.yaml",
            {"auth": {"strategy": "none"}, "status": "confirmed"},
        )
        results = list_variants(tmp_path)
        assert results[0].status == "confirmed"

    def test_status_defaults_to_awaiting_verification(self, tmp_path: Path) -> None:
        """Variant status defaults to awaiting_verification when absent from YAML."""
        _write_variant_yaml(tmp_path / "modem.yaml", {"auth": {"strategy": "none"}})
        results = list_variants(tmp_path)
        assert results[0].status == "awaiting_verification"

    def test_per_variant_status_independent(self, tmp_path: Path) -> None:
        """Each variant carries its own status independently."""
        _write_variant_yaml(
            tmp_path / "modem.yaml",
            {"auth": {"strategy": "none"}, "status": "awaiting_verification"},
        )
        _write_variant_yaml(
            tmp_path / "modem-form.yaml",
            {"auth": {"strategy": "form"}, "status": "confirmed"},
        )
        results = list_variants(tmp_path)
        default = next(v for v in results if v.name is None)
        named = next(v for v in results if v.name == "form")
        assert default.status == "awaiting_verification"
        assert named.status == "confirmed"


class TestVariantInfo:
    """VariantInfo dataclass construction."""

    def test_defaults(self) -> None:
        """Default values for optional fields."""
        info = VariantInfo(name=None)
        assert info.auth_strategy == "none"
        assert info.hw_version is None
        assert info.isps == []
        assert info.notes is None
        assert info.status == "awaiting_verification"
