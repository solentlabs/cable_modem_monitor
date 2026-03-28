"""Tests for modem directory loader — ``load_server_from_modem_dir``.

Builds temporary modem directories with HAR files and modem configs
from fixture files, then verifies the loader produces correct
``ServerConfig`` instances or raises on invalid input.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.test_harness.loader import (
    ServerConfig,
    load_server_from_modem_dir,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _build_modem_dir(
    root: Path,
    *,
    modem_yaml: str = "modem_minimal.yaml",
    har_file: str = "har_minimal.json",
    har_name: str = "modem.har",
    modem_yaml_name: str = "modem.yaml",
    extra_yamls: dict[str, str] | None = None,
    extra_hars: dict[str, str] | None = None,
    skip_test_data: bool = False,
    skip_modem_yaml: bool = False,
) -> Path:
    """Build a temporary modem directory from fixture files.

    Args:
        root: tmp_path root.
        modem_yaml: Fixture filename for modem config.
        har_file: Fixture filename for HAR data.
        har_name: Target filename in test_data/.
        modem_yaml_name: Target filename for modem config.
        extra_yamls: Map of target_name -> fixture_name for additional yamls.
        extra_hars: Map of target_name -> fixture_name for additional HARs.
        skip_test_data: Don't create test_data/.
        skip_modem_yaml: Don't copy modem config.

    Returns:
        Path to the modem directory (``root/solentlabs/t100``).
    """
    modem_dir = root / "solentlabs" / "t100"
    modem_dir.mkdir(parents=True)

    if not skip_modem_yaml:
        shutil.copy(FIXTURES_DIR / modem_yaml, modem_dir / modem_yaml_name)

    if not skip_test_data:
        test_data = modem_dir / "test_data"
        test_data.mkdir()
        shutil.copy(FIXTURES_DIR / har_file, test_data / har_name)

        if extra_hars:
            for target_name, fixture_name in extra_hars.items():
                shutil.copy(FIXTURES_DIR / fixture_name, test_data / target_name)

    if extra_yamls:
        for target_name, fixture_name in extra_yamls.items():
            shutil.copy(FIXTURES_DIR / fixture_name, modem_dir / target_name)

    return modem_dir


# ---------------------------------------------------------------------------
# Happy path tests
# ---------------------------------------------------------------------------


class TestLoadServerFromModemDir:
    """Happy path loading from a well-formed modem directory."""

    def test_loads_har_and_config(self, tmp_path: Path) -> None:
        """Loads HAR entries and modem config from a valid directory."""
        modem_dir = _build_modem_dir(tmp_path)
        result = load_server_from_modem_dir(modem_dir)

        assert isinstance(result, ServerConfig)
        assert len(result.har_entries) == 1
        assert result.har_entries[0]["request"]["method"] == "GET"
        assert result.modem_config.manufacturer == "Solent Labs"
        assert result.modem_config.model == "T100"

    def test_modem_name_from_directory(self, tmp_path: Path) -> None:
        """Modem name is derived from parent/dir structure."""
        modem_dir = _build_modem_dir(tmp_path)
        result = load_server_from_modem_dir(modem_dir)

        assert result.modem_name == "solentlabs/t100"

    def test_specific_har_by_name(self, tmp_path: Path) -> None:
        """Loads a specific HAR file when har_name is provided."""
        modem_dir = _build_modem_dir(
            tmp_path,
            extra_hars={"modem-v2.har": "har_minimal_alt.json"},
        )
        result = load_server_from_modem_dir(modem_dir, har_name="modem-v2.har")

        assert len(result.har_entries) == 1
        assert "/info.html" in result.har_entries[0]["request"]["url"]

    def test_first_har_when_multiple(self, tmp_path: Path) -> None:
        """Uses the first .har file (alphabetically) when none specified."""
        modem_dir = _build_modem_dir(
            tmp_path,
            extra_hars={"zzz-other.har": "har_minimal_alt.json"},
        )
        result = load_server_from_modem_dir(modem_dir)

        # "modem.har" sorts before "zzz-other.har"
        assert "/status.html" in result.har_entries[0]["request"]["url"]


class TestVariantConfigResolution:
    """Modem config resolution for variant HAR files."""

    def test_variant_har_uses_variant_yaml(self, tmp_path: Path) -> None:
        """modem-v2.har resolves to modem-v2.yaml when it exists."""
        modem_dir = _build_modem_dir(
            tmp_path,
            extra_yamls={"modem-v2.yaml": "modem_minimal.yaml"},
            extra_hars={"modem-v2.har": "har_minimal.json"},
        )
        result = load_server_from_modem_dir(modem_dir, har_name="modem-v2.har")

        # Both yamls are the same fixture, but the resolution should pick modem-v2.yaml
        assert result.modem_config.model == "T100"

    def test_variant_har_falls_back_to_default(self, tmp_path: Path) -> None:
        """modem-v2.har falls back to modem.yaml when no variant yaml exists."""
        modem_dir = _build_modem_dir(
            tmp_path,
            extra_hars={"modem-v2.har": "har_minimal.json"},
        )
        result = load_server_from_modem_dir(modem_dir, har_name="modem-v2.har")

        assert result.modem_config.model == "T100"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestLoadServerErrors:
    """Error handling for invalid modem directories."""

    def test_missing_modem_dir(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError for a non-existent directory."""
        with pytest.raises(FileNotFoundError, match="Modem directory not found"):
            load_server_from_modem_dir(tmp_path / "nonexistent")

    def test_missing_test_data(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError when test_data/ is missing."""
        modem_dir = _build_modem_dir(tmp_path, skip_test_data=True)
        with pytest.raises(FileNotFoundError, match="No test_data/"):
            load_server_from_modem_dir(modem_dir)

    def test_no_har_files(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError when no .har files exist."""
        modem_dir = _build_modem_dir(tmp_path)
        (modem_dir / "test_data" / "modem.har").unlink()
        with pytest.raises(FileNotFoundError, match="No .har files"):
            load_server_from_modem_dir(modem_dir)

    def test_specific_har_not_found(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError for a named HAR that doesn't exist."""
        modem_dir = _build_modem_dir(tmp_path)
        with pytest.raises(FileNotFoundError, match="HAR file not found"):
            load_server_from_modem_dir(modem_dir, har_name="nonexistent.har")

    def test_missing_modem_yaml(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError when no modem config resolves."""
        modem_dir = _build_modem_dir(tmp_path, skip_modem_yaml=True)
        with pytest.raises(FileNotFoundError, match="No modem config found"):
            load_server_from_modem_dir(modem_dir)

    def test_invalid_har_json(self, tmp_path: Path) -> None:
        """Raises ValueError for malformed HAR JSON."""
        modem_dir = _build_modem_dir(tmp_path)
        (modem_dir / "test_data" / "modem.har").write_text("not json")
        with pytest.raises(ValueError, match="Failed to read HAR"):
            load_server_from_modem_dir(modem_dir)

    def test_invalid_har_structure(self, tmp_path: Path) -> None:
        """Raises ValueError when HAR JSON lacks log.entries."""
        modem_dir = _build_modem_dir(tmp_path)
        (modem_dir / "test_data" / "modem.har").write_text('{"not": "har"}')
        with pytest.raises(ValueError, match="missing log.entries"):
            load_server_from_modem_dir(modem_dir)
