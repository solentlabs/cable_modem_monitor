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
                "status": "verified",
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
                "status": "verified",
            },
        )

        results = list_modems(tmp_path)
        summary = results[0]

        assert summary.manufacturer == "Solent Labs"
        assert summary.model == "T100"
        assert summary.model_aliases == ["Surfboard"]
        assert summary.brands == ["Comcast"]
        assert summary.docsis_version == "3.1"
        assert summary.status == "verified"
        assert summary.default_host == "10.0.0.1"
        assert summary.auth_strategy == "cookie"
        assert summary.path == tmp_path / "solent" / "t100"

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
        assert results[0].isps == []
        assert results[0].notes is None

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


class TestVariantInfo:
    """VariantInfo dataclass construction."""

    def test_defaults(self) -> None:
        """Default values for optional fields."""
        info = VariantInfo(name=None)
        assert info.auth_strategy == "none"
        assert info.isps == []
        assert info.notes is None
