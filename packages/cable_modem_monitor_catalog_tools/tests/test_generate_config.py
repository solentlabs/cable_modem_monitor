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
from solentlabs.cable_modem_monitor_catalog_tools.generate_config import (
    GenerateConfigResult,
    generate_config,
)
from tests._helpers import collect_fixtures, load_fixture

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
# Alias and brand validation — firmware-internal codes rejected from aliases/brands
# ---------------------------------------------------------------------------


class TestAliasAndBrandValidation:
    """Firmware-internal codes are rejected from model_aliases and brands.

    Guards the documented G54 failure (#72): intake once wrote the
    firmware product code into model_aliases. Underscores are the
    firmware-code tell; legitimate user-facing names never carry them.
    """

    def _fixture(self) -> dict:
        return load_fixture(VALID_DIR / "table_form_auth.json")

    def _with_identity(self, **identity: list[str]) -> GenerateConfigResult:
        fixture = self._fixture()
        metadata = {**fixture["_metadata"], **identity}
        return generate_config(fixture["_analysis"], metadata)

    def test_firmware_code_alias_rejected(self) -> None:
        result = self._with_identity(model_aliases=["G54_COMMSCOPE"])
        assert not result.validation.valid
        assert any("model_aliases" in e and "firmware" in e for e in result.validation.errors)

    def test_firmware_code_brand_rejected(self) -> None:
        result = self._with_identity(brands=["G54_COMMSCOPE"])
        assert not result.validation.valid
        assert any("brands" in e and "firmware" in e for e in result.validation.errors)

    def test_user_facing_names_pass(self) -> None:
        result = self._with_identity(
            model_aliases=["CGM4140COM", "Motorola SB6141", "Hub 5"],
            brands=["SURFboard", "Virgin Media"],
        )
        assert result.validation.valid, result.validation.errors


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
        assert not modem.get("auth", {}).get("cookie_name")

    def test_session_with_cookie(self) -> None:
        """Session with cookie_name appears on auth in modem.yaml."""
        fixture = load_fixture(self._find_fixture("table_form_auth"))
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        modem = yaml.safe_load(result.modem_yaml)
        assert modem["auth"]["cookie_name"] == "session"
        assert "max_concurrent" not in modem.get("session", {})

    def test_url_token_session(self) -> None:
        """URL token session has cookie_name and token_prefix on auth."""
        fixture = load_fixture(self._find_fixture("url_token_with_session"))
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        modem = yaml.safe_load(result.modem_yaml)
        assert modem["auth"]["cookie_name"] == "sessionId"
        assert modem["auth"]["token_prefix"] == "ct_"

    def test_form_cbn_no_cookie_name(self) -> None:
        """form_cbn auth must not receive cookie_name (uses session_cookie_name)."""
        fixture = load_fixture(self._find_fixture("form_cbn_no_cookie_copy"))
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        modem = yaml.safe_load(result.modem_yaml)
        assert modem["auth"]["strategy"] == "form_cbn"
        assert "cookie_name" not in modem["auth"]

    def test_form_auth_no_token_prefix(self) -> None:
        """form auth must not receive token_prefix (url_token only)."""
        fixture = load_fixture(self._find_fixture("table_form_auth"))
        analysis = dict(fixture["_analysis"])
        analysis["session"] = dict(analysis["session"])
        analysis["session"]["token_prefix"] = "ct_"
        result = generate_config(analysis, fixture["_metadata"])
        modem = yaml.safe_load(result.modem_yaml)
        assert modem["auth"]["strategy"] == "form"
        assert "token_prefix" not in modem["auth"]

    def test_session_with_query_params(self) -> None:
        """Session query_params appear in modem.yaml."""
        fixture = load_fixture(self._find_fixture("session_with_query_params"))
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        modem = yaml.safe_load(result.modem_yaml)
        assert modem["session"]["query_params"] == {"_n": "13127"}

    def test_form_sjcl_injects_crypto_defaults(self) -> None:
        """form_sjcl auth injects SJCL crypto defaults (iterations, key_length, tag_length)."""
        fixture = load_fixture(self._find_fixture("form_sjcl_defaults"))
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        modem = yaml.safe_load(result.modem_yaml)
        auth = modem["auth"]
        assert auth["strategy"] == "form_sjcl"
        for key, expected in fixture["_expected_auth_fields"].items():
            assert auth.get(key) == expected, f"{key}: expected {expected}, got {auth.get(key)}"


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
# Spot-check: auth default stripping
# ---------------------------------------------------------------------------


class TestAuthDefaultStripping:
    """Verify empty/default auth fields are stripped from modem.yaml."""

    def test_form_auth_defaults_stripped(self) -> None:
        """Default/empty auth fields are stripped from generated YAML."""
        fixture = load_fixture(VALID_DIR / "form_auth_with_defaults.json")
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        modem = yaml.safe_load(result.modem_yaml)
        auth = modem["auth"]
        assert "method" not in auth
        assert "hidden_fields" not in auth
        assert "login_page" not in auth
        assert "form_selector" not in auth
        assert "success" not in auth
        assert "encoding" not in auth

    def test_non_default_values_kept(self) -> None:
        """Non-default auth fields (encoding, login_page) are preserved."""
        fixture = load_fixture(VALID_DIR / "table_form_auth.json")
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        modem = yaml.safe_load(result.modem_yaml)
        assert modem["auth"]["encoding"] == "base64"
        assert modem["auth"]["login_page"] == "/login.html"


# ---------------------------------------------------------------------------
# Spot-check: aggregate auto-generation
# ---------------------------------------------------------------------------


class TestAggregateGeneration:
    """Verify aggregate section auto-generation from field mappings."""

    def test_aggregate_from_corrected_uncorrected(self) -> None:
        """Aggregate generated when downstream has corrected + uncorrected."""
        fixture = load_fixture(VALID_DIR / "table_form_auth.json")
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        assert result.parser_yaml is not None
        parser = yaml.safe_load(result.parser_yaml)
        assert "aggregate" in parser
        assert parser["aggregate"]["total_corrected"] == {"sum": "corrected", "channels": "downstream"}
        assert parser["aggregate"]["total_uncorrected"] == {"sum": "uncorrected", "channels": "downstream"}

    def test_aggregate_docsis_31_scopes_to_ofdm(self) -> None:
        """DOCSIS 3.1 scopes aggregates to downstream.qam, not downstream."""
        fixture = load_fixture(VALID_DIR / "table_form_auth.json")
        metadata = dict(fixture["_metadata"])
        metadata["hardware"] = {"docsis_version": "3.1", "chipset": "Broadcom BCM3390"}
        result = generate_config(fixture["_analysis"], metadata)
        assert result.parser_yaml is not None
        parser = yaml.safe_load(result.parser_yaml)
        assert "aggregate" in parser
        assert parser["aggregate"]["total_corrected"] == {"sum": "corrected", "channels": "downstream.qam"}
        assert parser["aggregate"]["total_uncorrected"] == {"sum": "uncorrected", "channels": "downstream.qam"}

    def test_no_aggregate_without_corrected(self) -> None:
        """No aggregate when downstream lacks corrected/uncorrected fields."""
        fixture = load_fixture(VALID_DIR / "form_auth_with_defaults.json")
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        assert result.parser_yaml is not None
        parser = yaml.safe_load(result.parser_yaml)
        assert "aggregate" not in parser

    def test_metadata_aggregate_wins(self) -> None:
        """Explicit metadata aggregate overrides auto-generation."""
        fixture = load_fixture(VALID_DIR / "table_form_auth.json")
        metadata = dict(fixture["_metadata"])
        metadata["aggregate"] = {"custom": {"sum": "power", "channels": "upstream"}}
        result = generate_config(fixture["_analysis"], metadata)
        assert result.parser_yaml is not None
        parser = yaml.safe_load(result.parser_yaml)
        assert "custom" in parser["aggregate"]
        assert "total_corrected" not in parser["aggregate"]


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
