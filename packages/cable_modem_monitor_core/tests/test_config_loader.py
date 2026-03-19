"""Tests for config_loader — YAML loading and Pydantic validation.

Valid and invalid configs are stored as JSON fixtures in
tests/fixtures/config_loader/{valid,invalid}/.

Each fixture has:
- ``_type``: "modem" or "parser" — selects the loader function
- ``_yaml``: YAML string to write to a temp file and load
- ``_expected_error``: (invalid only) regex match for the error message

Valid fixtures verify that the YAML round-trips through safe_load
and Pydantic validation. Invalid fixtures verify appropriate errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from solentlabs.cable_modem_monitor_core.config_loader import (
    load_modem_config,
    load_parser_config,
    validate_modem_config,
    validate_parser_config,
)

from tests.conftest import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "config_loader"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(tmp_path: Path, yaml_str: str, config_type: str) -> Path:
    """Write YAML string to a temp file and return the path."""
    filename = "modem.yaml" if config_type == "modem" else "parser.yaml"
    path = tmp_path / filename
    path.write_text(yaml_str, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Valid configs — file loading
# ---------------------------------------------------------------------------

VALID_FIXTURES = collect_fixtures(VALID_DIR)


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=[f.stem for f in VALID_FIXTURES],
)
def test_valid_config_loads(fixture_path: Path, tmp_path: Path) -> None:
    """Valid fixture loads from YAML file without error."""
    fixture = load_fixture(fixture_path)
    config_type = fixture["_type"]
    yaml_path = _write_yaml(tmp_path, fixture["_yaml"], config_type)

    if config_type == "modem":
        config = load_modem_config(yaml_path)
        assert config.manufacturer
        assert config.transport in ("http", "hnap")
    else:
        config = load_parser_config(yaml_path)
        has_section = config.downstream is not None or config.upstream is not None or config.system_info is not None
        assert has_section


# ---------------------------------------------------------------------------
# Valid configs — dict validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=[f.stem for f in VALID_FIXTURES],
)
def test_valid_config_validates_from_dict(fixture_path: Path) -> None:
    """Valid fixture validates from parsed dict without error."""
    fixture = load_fixture(fixture_path)
    config_type = fixture["_type"]
    data = yaml.safe_load(fixture["_yaml"])

    if config_type == "modem":
        config = validate_modem_config(data)
        assert config.manufacturer
    else:
        config = validate_parser_config(data)
        assert config is not None


# ---------------------------------------------------------------------------
# Invalid configs — file loading
# ---------------------------------------------------------------------------

INVALID_FIXTURES = collect_fixtures(INVALID_DIR)


@pytest.mark.parametrize(
    "fixture_path",
    INVALID_FIXTURES,
    ids=[f.stem for f in INVALID_FIXTURES],
)
def test_invalid_config_raises(fixture_path: Path, tmp_path: Path) -> None:
    """Invalid fixture raises expected error when loaded."""
    fixture = load_fixture(fixture_path)
    config_type = fixture["_type"]
    expected_error = fixture["_expected_error"]
    yaml_path = _write_yaml(tmp_path, fixture["_yaml"], config_type)

    with pytest.raises((ValidationError, ValueError), match=expected_error):
        if config_type == "modem":
            load_modem_config(yaml_path)
        else:
            load_parser_config(yaml_path)


# ---------------------------------------------------------------------------
# Behavioral tests — edge cases not covered by fixtures
# ---------------------------------------------------------------------------


class TestFileErrors:
    """Tests for file-level error handling."""

    def test_modem_file_not_found(self, tmp_path: Path) -> None:
        """Missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_modem_config(tmp_path / "nonexistent.yaml")

    def test_parser_file_not_found(self, tmp_path: Path) -> None:
        """Missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_parser_config(tmp_path / "nonexistent.yaml")

    def test_invalid_yaml_syntax(self, tmp_path: Path) -> None:
        """Malformed YAML raises yaml.YAMLError."""
        path = tmp_path / "bad.yaml"
        path.write_text("key: [unclosed", encoding="utf-8")
        with pytest.raises(yaml.YAMLError):
            load_modem_config(path)
