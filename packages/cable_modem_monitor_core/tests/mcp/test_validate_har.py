"""Tests for validate_har MCP tool.

Valid and invalid HAR structures are stored as JSON fixtures in
tests/mcp/fixtures/validate_har/{valid,invalid}/.

Valid fixtures have `_har` (the HAR dict), `_expected_auth` (bool),
and `_expected_hints` (list of transport/auth hint strings).

Invalid fixtures have `_har` (the bad HAR dict) and `_expected_error`
(substring to find in the issues list).

Two tests remain inline: missing file and invalid JSON — these test
file-level errors that can't be expressed as fixture content.

Integration tests against real modem HARs belong in Catalog (Step 8).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.mcp.validate_har import (
    ValidationResult,
    validate_har,
)

from tests.conftest import collect_fixtures, load_fixture, write_har

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "validate_har"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"

# ---------------------------------------------------------------------------
# Valid HARs — must pass validation with expected auth and hints
# ---------------------------------------------------------------------------

VALID_FIXTURES = collect_fixtures(VALID_DIR)


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=[f.stem for f in VALID_FIXTURES],
)
def test_valid_har(fixture_path: Path, tmp_path):
    """Valid HAR passes validation with expected auth and transport hints."""
    raw = load_fixture(fixture_path)
    har_file = write_har(tmp_path, raw["_har"])
    result = validate_har(har_file)

    assert result.valid is True, f"expected valid but got issues: {result.issues}"
    assert result.auth_flow_detected is raw["_expected_auth"]
    for hint in raw["_expected_hints"]:
        assert hint in result.transport_hints, f"expected hint '{hint}' in {result.transport_hints}"


# ---------------------------------------------------------------------------
# Invalid HARs — must fail with expected error message
# ---------------------------------------------------------------------------

INVALID_FIXTURES = collect_fixtures(INVALID_DIR)


@pytest.mark.parametrize(
    "fixture_path",
    INVALID_FIXTURES,
    ids=[f.stem for f in INVALID_FIXTURES],
)
def test_invalid_har(fixture_path: Path, tmp_path):
    """Invalid HAR fails validation with expected issue message."""
    raw = load_fixture(fixture_path)
    har_file = write_har(tmp_path, raw["_har"])
    result = validate_har(har_file)

    expected = raw["_expected_error"]
    all_issues = result.issues
    assert any(expected in issue for issue in all_issues), f"expected '{expected}' in issues but got: {all_issues}"


# ---------------------------------------------------------------------------
# File-level errors (can't be fixture-driven)
# ---------------------------------------------------------------------------


def test_missing_file():
    """Missing HAR file is a hard stop."""
    result = validate_har("/nonexistent/path.har")
    assert result.valid is False
    assert any("not found" in i for i in result.issues)


def test_invalid_json(tmp_path):
    """Non-JSON file is a hard stop."""
    har_file = tmp_path / "bad.har"
    har_file.write_text("not json{{{")
    result = validate_har(har_file)
    assert result.valid is False
    assert any("not valid JSON" in i for i in result.issues)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    """Tests for ValidationResult serialization."""

    def test_to_dict(self):
        """ValidationResult serializes to dict."""
        result = ValidationResult(
            valid=True,
            issues=["WARNING: something"],
            auth_flow_detected=True,
            transport_hints=["http", "auth:form"],
        )
        d = result.to_dict()
        assert d["valid"] is True
        assert d["auth_flow_detected"] is True
        assert "http" in d["transport_hints"]
