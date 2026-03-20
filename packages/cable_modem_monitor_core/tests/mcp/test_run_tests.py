"""Tests for run_tests MCP tool.

Verifies the tool wires discovery + runner correctly and returns
structured output. Uses ``tmp_path`` with minimal modem directories.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_core.mcp.run_tests import (
    run_tests,
)

# ---------------------------------------------------------------------------
# Fixture paths — shared pipeline fixtures
# ---------------------------------------------------------------------------

_PIPELINE_FIXTURES = Path(__file__).parent.parent / "fixtures" / "pipeline"

_MODEM_YAML = (_PIPELINE_FIXTURES / "modem.yaml").read_text()
_PARSER_YAML = (_PIPELINE_FIXTURES / "parser.yaml").read_text()
_HAR_DATA: dict[str, Any] = json.loads((_PIPELINE_FIXTURES / "har_1ch.json").read_text())
_GOLDEN_FILE: dict[str, Any] = json.loads((_PIPELINE_FIXTURES / "golden_1ch.json").read_text())


@pytest.fixture(autouse=True)
def _allow_sockets(socket_enabled: None) -> None:  # noqa: ARG001
    """Enable sockets for mock server integration tests."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_modem_dir(
    tmp_path: Path,
    *,
    golden: dict[str, Any] | None = _GOLDEN_FILE,
) -> Path:
    """Build a single modem directory and return its path."""
    modem_dir = tmp_path / "modems" / "solentlabs" / "t100"
    tests_dir = modem_dir / "test_data"
    tests_dir.mkdir(parents=True)

    (modem_dir / "modem.yaml").write_text(_MODEM_YAML)
    (modem_dir / "parser.yaml").write_text(_PARSER_YAML)
    (tests_dir / "modem.har").write_text(json.dumps(_HAR_DATA))
    if golden is not None:
        (tests_dir / "modem.expected.json").write_text(json.dumps(golden))

    return modem_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunTests:
    """run_tests MCP tool integration."""

    def test_pass(self, tmp_path: Path) -> None:
        """All tests pass returns passed=True."""
        modem_dir = _build_modem_dir(tmp_path)

        result = run_tests(str(modem_dir))

        assert result.passed is True
        assert len(result.results) == 1
        assert result.results[0]["passed"] is True
        assert result.errors == []

    def test_failure(self, tmp_path: Path) -> None:
        """Golden file mismatch returns passed=False with diff."""
        bad_golden = {
            "downstream": [
                {"channel_id": 1, "frequency": 999000000, "power": 2.5},
            ],
            "upstream": [],
        }
        modem_dir = _build_modem_dir(tmp_path, golden=bad_golden)

        result = run_tests(str(modem_dir))

        assert result.passed is False
        assert len(result.results) == 1
        assert result.results[0]["passed"] is False
        assert "diff" in result.results[0]
        assert "failures" in result.results[0]

    def test_nonexistent_directory(self) -> None:
        """Nonexistent path returns tool-level error."""
        result = run_tests("/nonexistent/path")

        assert result.passed is False
        assert len(result.errors) == 1
        assert "Directory not found" in result.errors[0]

    def test_no_test_cases(self, tmp_path: Path) -> None:
        """Directory with no test cases returns tool-level error."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = run_tests(str(empty_dir))

        assert result.passed is False
        assert len(result.errors) == 1
        assert "No test cases" in result.errors[0]

    def test_to_dict(self, tmp_path: Path) -> None:
        """to_dict produces valid MCP output structure."""
        modem_dir = _build_modem_dir(tmp_path)

        result = run_tests(str(modem_dir))
        d = result.to_dict()

        assert isinstance(d, dict)
        assert d["passed"] is True
        assert isinstance(d["results"], list)
        assert isinstance(d["errors"], list)

    def test_missing_golden_file_error(self, tmp_path: Path) -> None:
        """Missing golden file returns per-test error, not tool error."""
        modem_dir = _build_modem_dir(tmp_path, golden=None)

        result = run_tests(str(modem_dir))

        assert result.passed is False
        assert result.errors == []
        assert len(result.results) == 1
        assert "error" in result.results[0]
        assert "Golden file not found" in result.results[0]["error"]
