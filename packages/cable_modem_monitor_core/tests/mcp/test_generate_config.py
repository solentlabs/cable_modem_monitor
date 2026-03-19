"""Tests for generate_config — config generation from analysis output.

Each fixture has ``_analysis`` (analysis result dict) and ``_metadata``
(caller-provided metadata). Valid fixtures produce configs that pass
Pydantic validation and cross-file checks. Invalid fixtures produce
expected errors.

Spot-check assertions use ``_expected_*`` fields in the fixture to
verify key properties of the generated output.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from solentlabs.cable_modem_monitor_core.mcp.generate_config import generate_config

from tests.conftest import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "generate_config"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"


# ---------------------------------------------------------------------------
# Valid configs — generation succeeds with validation passing
# ---------------------------------------------------------------------------

VALID_FIXTURES = collect_fixtures(VALID_DIR)


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=[f.stem for f in VALID_FIXTURES],
)
def test_valid_generates_successfully(fixture_path: Path) -> None:
    """Valid fixture generates configs that pass validation."""
    fixture = load_fixture(fixture_path)
    result = generate_config(fixture["_analysis"], fixture["_metadata"])

    assert result.validation.valid, f"Expected valid output, got errors: {result.validation.errors}"
    assert result.modem_yaml
    assert result.parser_py is None


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=[f.stem for f in VALID_FIXTURES],
)
def test_valid_modem_yaml_structure(fixture_path: Path) -> None:
    """Generated modem.yaml has correct auth strategy and identity."""
    fixture = load_fixture(fixture_path)
    result = generate_config(fixture["_analysis"], fixture["_metadata"])
    modem = yaml.safe_load(result.modem_yaml)

    # Identity from metadata
    assert modem["manufacturer"] == fixture["_metadata"]["manufacturer"]
    assert modem["model"] == fixture["_metadata"]["model"]
    assert modem["transport"] == fixture["_analysis"]["transport"]

    # Auth strategy
    expected_strategy = fixture.get("_expected_auth_strategy")
    if expected_strategy:
        assert modem["auth"]["strategy"] == expected_strategy


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=[f.stem for f in VALID_FIXTURES],
)
def test_valid_parser_yaml_presence(fixture_path: Path) -> None:
    """Parser.yaml is present when sections exist, absent otherwise."""
    fixture = load_fixture(fixture_path)
    result = generate_config(fixture["_analysis"], fixture["_metadata"])
    expected_has_parser = fixture.get("_expected_has_parser", False)

    if expected_has_parser:
        assert result.parser_yaml is not None
        parser = yaml.safe_load(result.parser_yaml)
        assert parser is not None

        # Check format if specified
        expected_format = fixture.get("_expected_format")
        if expected_format and "downstream" in parser:
            assert parser["downstream"]["format"] == expected_format
    else:
        assert result.parser_yaml is None


# ---------------------------------------------------------------------------
# Spot-check: session and cookie behavior
# ---------------------------------------------------------------------------


class TestSessionBehavior:
    """Verify session config generation from analysis output."""

    def _find_fixture(self, name: str) -> Path:
        """Find a valid fixture by stem name."""
        return VALID_DIR / f"{name}.json"

    def test_no_cookie_when_empty(self) -> None:
        """IP-based session produces no cookie_name in modem.yaml."""
        fixture = load_fixture(self._find_fixture("table_no_cookie"))
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        modem = yaml.safe_load(result.modem_yaml)
        assert "session" not in modem or not modem.get("session", {}).get("cookie_name")

    def test_session_with_cookie(self) -> None:
        """Session with cookie_name appears in modem.yaml."""
        fixture = load_fixture(self._find_fixture("table_form_auth"))
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        modem = yaml.safe_load(result.modem_yaml)
        assert modem["session"]["cookie_name"] == "session"
        assert modem["session"]["max_concurrent"] == 1

    def test_url_token_session(self) -> None:
        """URL token session has cookie_name and token_prefix."""
        fixture = load_fixture(self._find_fixture("url_token_with_session"))
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        modem = yaml.safe_load(result.modem_yaml)
        assert modem["session"]["cookie_name"] == "sessionId"
        assert modem["session"]["token_prefix"] == "ct_"


# ---------------------------------------------------------------------------
# Spot-check: actions
# ---------------------------------------------------------------------------


class TestActionsBehavior:
    """Verify action config generation from analysis output."""

    def test_logout_action(self) -> None:
        """Logout action appears in modem.yaml."""
        fixture = load_fixture(VALID_DIR / "table_form_auth.json")
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        modem = yaml.safe_load(result.modem_yaml)
        assert modem["actions"]["logout"]["type"] == "http"
        assert modem["actions"]["logout"]["method"] == "GET"
        assert modem["actions"]["logout"]["endpoint"] == "/logout.asp"

    def test_restart_action_with_params(self) -> None:
        """Restart action with params appears in modem.yaml."""
        fixture = load_fixture(VALID_DIR / "table_no_cookie.json")
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        modem = yaml.safe_load(result.modem_yaml)
        assert modem["actions"]["restart"]["type"] == "http"
        assert modem["actions"]["restart"]["params"]["action"] == "1"

    def test_no_actions_when_none(self) -> None:
        """No actions block when no actions detected."""
        fixture = load_fixture(VALID_DIR / "table_no_auth.json")
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        modem = yaml.safe_load(result.modem_yaml)
        assert "actions" not in modem


# ---------------------------------------------------------------------------
# Spot-check: parser.yaml system_info
# ---------------------------------------------------------------------------


class TestSystemInfo:
    """Verify system_info passthrough in parser.yaml."""

    def test_system_info_sources(self) -> None:
        """System_info sources appear in parser.yaml."""
        fixture = load_fixture(VALID_DIR / "with_system_info.json")
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        assert result.parser_yaml is not None
        parser = yaml.safe_load(result.parser_yaml)
        assert "system_info" in parser
        assert len(parser["system_info"]["sources"]) == 2
        fields_page1 = parser["system_info"]["sources"][0]["fields"]
        assert fields_page1[0]["field"] == "system_uptime"


# ---------------------------------------------------------------------------
# Invalid configs — generation reports errors
# ---------------------------------------------------------------------------

INVALID_FIXTURES = collect_fixtures(INVALID_DIR)


@pytest.mark.parametrize(
    "fixture_path",
    INVALID_FIXTURES,
    ids=[f.stem for f in INVALID_FIXTURES],
)
def test_invalid_reports_errors(fixture_path: Path) -> None:
    """Invalid fixture produces expected error in validation result."""
    fixture = load_fixture(fixture_path)
    result = generate_config(fixture["_analysis"], fixture["_metadata"])
    expected_error = fixture["_expected_error"]

    assert not result.validation.valid, "Expected validation to fail"
    combined = " | ".join(result.validation.errors)
    assert re.search(
        expected_error, combined
    ), f"Expected error matching '{expected_error}', got: {result.validation.errors}"
