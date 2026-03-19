"""Tests for cross-file consistency validation.

Each fixture has ``_modem`` and ``_parser`` dicts that are independently
valid Pydantic configs. The cross-file check validates constraints that
span both files.

Valid fixtures pass with no errors. Invalid fixtures produce errors
matching ``_expected_error``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.models.modem_config import ModemConfig
from solentlabs.cable_modem_monitor_core.models.parser_config import ParserConfig
from solentlabs.cable_modem_monitor_core.validation.cross_file import (
    validate_cross_file,
)

from tests.conftest import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "cross_file"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"


# ---------------------------------------------------------------------------
# Valid configs — cross-file checks pass
# ---------------------------------------------------------------------------

VALID_FIXTURES = collect_fixtures(VALID_DIR)


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=[f.stem for f in VALID_FIXTURES],
)
def test_valid_cross_file(fixture_path: Path) -> None:
    """Valid fixture pair passes cross-file validation."""
    fixture = load_fixture(fixture_path)
    modem = ModemConfig(**fixture["_modem"])
    parser = ParserConfig(**fixture["_parser"])
    errors = validate_cross_file(modem, parser)
    assert errors == [], f"Unexpected errors: {errors}"


# ---------------------------------------------------------------------------
# Invalid configs — cross-file checks catch errors
# ---------------------------------------------------------------------------

INVALID_FIXTURES = collect_fixtures(INVALID_DIR)


@pytest.mark.parametrize(
    "fixture_path",
    INVALID_FIXTURES,
    ids=[f.stem for f in INVALID_FIXTURES],
)
def test_invalid_cross_file(fixture_path: Path) -> None:
    """Invalid fixture pair produces expected cross-file error."""
    fixture = load_fixture(fixture_path)
    modem = ModemConfig(**fixture["_modem"])
    parser = ParserConfig(**fixture["_parser"])
    expected_error = fixture["_expected_error"]

    errors = validate_cross_file(modem, parser)
    assert errors, "Expected cross-file errors but got none"
    combined = " | ".join(errors)
    assert re.search(expected_error, combined), f"Expected error matching '{expected_error}', got: {errors}"


# ---------------------------------------------------------------------------
# Behavioral tests — edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Cross-file edge cases not covered by fixtures."""

    def test_no_aggregate_no_system_info(self) -> None:
        """No aggregate and no system_info skips collision check."""
        modem = ModemConfig(
            manufacturer="Solent Labs",
            model="T100",
            transport="http",
            default_host="192.168.100.1",
            auth={"strategy": "none"},
            hardware={"docsis_version": "3.0"},
            status="verified",
            attribution={"contributors": [{"github": "t", "contribution": "t"}]},
            isps=["ISP"],
        )
        parser = ParserConfig(
            downstream={
                "format": "table",
                "resource": "/status.html",
                "tables": [
                    {
                        "selector": {"type": "header_text", "match": "DS"},
                        "columns": [{"index": 0, "field": "channel_id", "type": "integer"}],
                        "channel_type": {"fixed": "qam"},
                    }
                ],
            }
        )
        assert validate_cross_file(modem, parser) == []

    def test_aggregate_without_system_info(self) -> None:
        """Aggregate with no system_info has no collision possible."""
        modem = ModemConfig(
            manufacturer="Solent Labs",
            model="T100",
            transport="http",
            default_host="192.168.100.1",
            auth={"strategy": "none"},
            aggregate={"total_corrected": {"sum": "corrected", "channels": "downstream"}},
            hardware={"docsis_version": "3.0"},
            status="verified",
            attribution={"contributors": [{"github": "t", "contribution": "t"}]},
            isps=["ISP"],
        )
        parser = ParserConfig(
            downstream={
                "format": "table",
                "resource": "/status.html",
                "tables": [
                    {
                        "selector": {"type": "header_text", "match": "DS"},
                        "columns": [{"index": 0, "field": "channel_id", "type": "integer"}],
                        "channel_type": {"fixed": "qam"},
                    }
                ],
            }
        )
        assert validate_cross_file(modem, parser) == []
