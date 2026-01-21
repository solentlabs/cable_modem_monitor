"""Tests for modem.yaml configuration validation.

These tests ensure all modem.yaml files are valid and complete,
serving as a CI safety net for the pre-commit validation hook.

=============================================================================
TEST DATA TABLES
=============================================================================

This file uses table-driven tests for readability. Test data is defined in
tables at the top, making it easy to see all test cases at a glance and add
new ones by simply adding a row.

Tables defined below:
    AUTH_FIELD_REQUIREMENTS - Required fields for each auth type (via types{})
    SCHEMA_VALIDATION_CASES - ModemConfig validation by status/parser config
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# Project root for finding modem configs
PROJECT_ROOT = Path(__file__).parent.parent.parent


# =============================================================================
# AUTH FIELD REQUIREMENTS TABLE
# =============================================================================
# Each auth type requires specific fields in modem.yaml.
# This table defines what fields must be present for each type in auth.types{}.
#
# ┌─────────────┬─────────────────┬──────────────────────┐
# │ auth_type   │ required_field  │ description          │
# ├─────────────┼─────────────────┼──────────────────────┤
# │ form        │ action          │ form action URL      │
# │ form        │ username_field  │ username field name  │
# │ form        │ password_field  │ password field name  │
# │ hnap        │ endpoint        │ HNAP endpoint        │
# │ url_token   │ login_page      │ login page URL       │
# │ url_token   │ session_cookie  │ session cookie name  │
# └─────────────┴─────────────────┴──────────────────────┘
#
# fmt: off
AUTH_FIELD_REQUIREMENTS: list[tuple[str, str, str]] = [
    # (auth_type, required_field, description)
    ("form",        "action",          "form action URL"),
    ("form",        "username_field",  "username field name"),
    ("form",        "password_field",  "password field name"),
    ("hnap",        "endpoint",        "HNAP endpoint"),
    ("url_token",   "login_page",      "login page URL"),
    ("url_token",   "session_cookie",  "session cookie name"),
]
# fmt: on


# =============================================================================
# SCHEMA VALIDATION CASES TABLE
# =============================================================================
# ModemConfig enforces that verified/awaiting_verification modems have parser
# config, while in_progress/unsupported modems don't require it.
#
# ┌───────────────────────┬───────────────────────┬─────────────────────────────┬───────┬─────────────────────────────┐
# │ test_id               │ status                │ parser_config               │ pass? │ error_contains              │
# ├───────────────────────┼───────────────────────┼─────────────────────────────┼───────┼─────────────────────────────┤
# │ verified_no_parser    │ verified              │ None                        │ ✗     │ ["parser"]                  │
# │ verified_empty_class  │ verified              │ {class:"", module:"x"}      │ ✗     │ ["parser.class"]            │
# │ verified_empty_module │ verified              │ {class:"X", module:""}      │ ✗     │ ["parser.module"]           │
# │ verified_complete     │ verified              │ {class:"X", module:"x"}     │ ✓     │ []                          │
# │ awaiting_no_parser    │ awaiting_verification │ None                        │ ✗     │ ["parser", "awaiting_..."]  │
# │ in_progress_no_parser │ in_progress           │ None                        │ ✓     │ []                          │
# │ unsupported_no_parser │ unsupported           │ None                        │ ✓     │ []                          │
# └───────────────────────┴───────────────────────┴─────────────────────────────┴───────┴─────────────────────────────┘
#
# Note: Import ParserStatus at runtime to avoid circular imports during collection
#
# fmt: off
SCHEMA_VALIDATION_CASES: list[tuple[str, str, dict | None, bool, list[str]]] = [
    # (test_id,              status,                 parser_config,                  pass?, error_contains)
    ("verified_no_parser",   "verified",             None,                           False, ["parser"]),
    ("verified_empty_class", "verified",             {"class": "", "module": "x"},   False, ["parser.class"]),
    ("verified_empty_module","verified",             {"class": "X", "module": ""},   False, ["parser.module"]),
    ("verified_complete",    "verified",             {"class": "X", "module": "x"},  True,  []),
    ("awaiting_no_parser",   "awaiting_verification",None,                           False, ["parser", "awaiting"]),
    ("in_progress_no_parser","in_progress",          None,                           True,  []),
    ("unsupported_no_parser","unsupported",          None,                           True,  []),
]
# fmt: on


def get_all_modem_configs() -> list[Path]:
    """Find all modem.yaml files."""
    modems_dir = PROJECT_ROOT / "modems"
    if not modems_dir.exists():
        return []
    return list(modems_dir.glob("*/*/modem.yaml"))


def get_complete_modem_configs() -> list[Path]:
    """Find modem.yaml files that have parser.class defined (complete configs)."""
    configs = []
    for path in get_all_modem_configs():
        with open(path) as f:
            config = yaml.safe_load(f) or {}
        if config.get("parser", {}).get("class"):
            configs.append(path)
    return configs


def load_config(path: Path) -> dict:
    """Load a modem.yaml file."""
    with open(path) as f:
        return yaml.safe_load(f) or {}


class TestModemYamlStructure:
    """Test basic structure of all modem.yaml files."""

    @pytest.mark.parametrize("config_path", get_all_modem_configs(), ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
    def test_valid_yaml(self, config_path: Path):
        """All modem.yaml files should be valid YAML."""
        config = load_config(config_path)
        assert config is not None

    @pytest.mark.parametrize("config_path", get_all_modem_configs(), ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
    def test_has_manufacturer(self, config_path: Path):
        """All modem.yaml files should have manufacturer."""
        config = load_config(config_path)
        assert config.get("manufacturer"), f"{config_path}: missing manufacturer"

    @pytest.mark.parametrize("config_path", get_all_modem_configs(), ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
    def test_has_model(self, config_path: Path):
        """All modem.yaml files should have model."""
        config = load_config(config_path)
        assert config.get("model"), f"{config_path}: missing model"


class TestCompleteModemConfigs:
    """Test complete modem.yaml files (those with parser.class defined)."""

    @pytest.mark.parametrize(
        "config_path", get_complete_modem_configs(), ids=lambda p: str(p.relative_to(PROJECT_ROOT))
    )
    def test_has_auth_types(self, config_path: Path):
        """Complete configs should have auth.types{} defined."""
        config = load_config(config_path)
        auth_types = config.get("auth", {}).get("types")
        assert auth_types is not None, f"{config_path}: missing auth.types"
        assert len(auth_types) > 0, f"{config_path}: auth.types is empty"

    @pytest.mark.parametrize(
        "config_path", get_complete_modem_configs(), ids=lambda p: str(p.relative_to(PROJECT_ROOT))
    )
    def test_has_detection(self, config_path: Path):
        """Complete configs should have detection patterns."""
        config = load_config(config_path)
        detection = config.get("detection", {})

        has_detection = detection.get("pre_auth") or detection.get("post_auth") or detection.get("json_markers")
        assert has_detection, f"{config_path}: missing detection patterns"

    @pytest.mark.parametrize(
        "config_path", get_complete_modem_configs(), ids=lambda p: str(p.relative_to(PROJECT_ROOT))
    )
    def test_has_parser_module(self, config_path: Path):
        """Complete configs should have parser module path."""
        config = load_config(config_path)
        assert config.get("parser", {}).get("module"), f"{config_path}: missing parser.module"


def _get_configs_by_auth_type(auth_type: str) -> list[Path]:
    """Get modem configs that have a specific auth type in auth.types{}."""
    configs = []
    for path in get_complete_modem_configs():
        config = load_config(path)
        types = config.get("auth", {}).get("types", {})
        if auth_type in types:
            configs.append(path)
    return configs


def _generate_auth_field_test_cases() -> list[tuple[Path, str, str, str]]:
    """Generate test cases from AUTH_FIELD_REQUIREMENTS table.

    Returns list of (config_path, auth_type, required_field, description)
    for each modem config that has the specified auth type.
    """
    cases = []
    for auth_type, field, description in AUTH_FIELD_REQUIREMENTS:
        for modem_path in _get_configs_by_auth_type(auth_type):
            cases.append((modem_path, auth_type, field, description))
    return cases


class TestAuthFieldRequirements:
    """Test that auth type configs have all required fields.

    Uses AUTH_FIELD_REQUIREMENTS table defined at top of file.
    Each row specifies: (auth_type, required_field, description)
    """

    @pytest.mark.parametrize(
        "config_path,auth_type,required_field,description",
        _generate_auth_field_test_cases(),
        ids=lambda x: f"{x.parent.parent.name}/{x.parent.name}:{x}" if isinstance(x, Path) else str(x),
    )
    def test_auth_has_required_field(self, config_path: Path, auth_type: str, required_field: str, description: str):
        """Auth type config should have required field."""
        config = load_config(config_path)
        type_config = config.get("auth", {}).get("types", {}).get(auth_type)

        # Skip if type_config is None (e.g., auth.types.none: null)
        if type_config is None:
            pytest.skip(f"Auth type '{auth_type}' has no config (expected for 'none' type)")

        assert type_config.get(
            required_field
        ), f"{config_path}: missing {description} (auth.types.{auth_type}.{required_field})"


def _load_html_fixture(path: Path) -> str | None:
    """Load an HTML fixture file with encoding fallback."""
    if not path.exists():
        return None
    for encoding in ("utf-8", "iso-8859-1", "cp1252"):
        try:
            with open(path, encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return None


def _find_login_fixtures(modem_path: Path) -> list[Path]:
    """Find login page fixtures for a modem.

    Looks for common login fixture patterns:
    - login.html, Login.html
    - index.html (often the login page for form auth)
    - Files in extended/ with 'login' in name
    """
    fixtures_dir = modem_path.parent / "fixtures"
    if not fixtures_dir.exists():
        return []

    login_patterns = [
        "login.html",
        "Login.html",
        "index.html",
        "root.html",
    ]

    fixtures = []
    for pattern in login_patterns:
        path = fixtures_dir / pattern
        if path.exists():
            fixtures.append(path)

    # Also check extended/ directory
    extended_dir = fixtures_dir / "extended"
    if extended_dir.exists():
        for path in extended_dir.glob("*login*.html"):
            fixtures.append(path)

    return fixtures


def _find_data_fixtures(modem_path: Path) -> list[Path]:
    """Find data page fixtures for a modem.

    Returns all HTML fixtures except login pages.
    """
    fixtures_dir = modem_path.parent / "fixtures"
    if not fixtures_dir.exists():
        return []

    login_names = {"login.html", "Login.html", "login_page.html", "logon.html"}

    fixtures = []
    for path in fixtures_dir.glob("*.html"):
        if path.name.lower() not in {n.lower() for n in login_names}:
            fixtures.append(path)

    return fixtures


def get_modems_with_fixtures() -> list[tuple[Path, Path]]:
    """Get (config_path, fixtures_dir) tuples for modems with fixtures."""
    results = []
    for config_path in get_complete_modem_configs():
        fixtures_dir = config_path.parent / "fixtures"
        if fixtures_dir.exists() and list(fixtures_dir.glob("*.html")):
            results.append((config_path, fixtures_dir))
    return results


def get_modems_with_pre_auth() -> list[Path]:
    """Get config paths for modems that have detection.pre_auth defined."""
    configs = []
    for path in get_complete_modem_configs():
        config = load_config(path)
        if config.get("detection", {}).get("pre_auth"):
            configs.append(path)
    return configs


def get_modems_with_post_auth() -> list[Path]:
    """Get config paths for modems that have detection.post_auth defined."""
    configs = []
    for path in get_complete_modem_configs():
        config = load_config(path)
        if config.get("detection", {}).get("post_auth"):
            configs.append(path)
    return configs


def _is_error_page(html: str) -> bool:
    """Check if HTML is an error page (401, 404, etc.)."""
    if not html:
        return True
    lower = html.lower()
    return "401" in lower and "unauthorized" in lower or "404" in lower and "not found" in lower


def _is_json_fixture(html: str) -> bool:
    """Check if content appears to be JSON rather than HTML."""
    if not html:
        return False
    stripped = html.strip()
    return stripped.startswith("{") or stripped.startswith("[")


# Known fixture gaps - modems where fixtures don't contain expected hints
# These are tracked separately for fixture improvement
KNOWN_FIXTURE_GAPS = {
    # c3700: root.html is 401 error page, not real login page
    "c3700": "Fixture is 401 error page",
    # s33: HNAP modem uses JSON responses, HTML fixtures may not contain model
    "s33": "HNAP modem - model in JSON response, not HTML",
    # mb7621: index.html is login page, model appears on data pages
    "mb7621": "Login fixture lacks model string (appears on data pages)",
}


def _filter_usable_login_fixtures(fixtures: list[Path]) -> list[Path]:
    """Filter login fixtures to remove error/JSON pages."""
    usable = []
    for path in fixtures:
        html = _load_html_fixture(path)
        if html and not _is_error_page(html) and not _is_json_fixture(html):
            usable.append(path)
    return usable


def _filter_usable_data_fixtures(fixtures: list[Path]) -> list[Path]:
    """Filter data fixtures to remove error pages."""
    usable = []
    for path in fixtures:
        html = _load_html_fixture(path)
        if html and not _is_error_page(html):
            usable.append(path)
    return usable


def _find_marker_matches(fixtures: list[Path], markers: list[str]) -> list[tuple]:
    """Find which markers match which fixtures."""
    matches = []
    for path in fixtures:
        html = _load_html_fixture(path)
        if not html:
            continue
        html_lower = html.lower()
        for marker in markers:
            if marker.lower() in html_lower:
                matches.append((marker, path.name))
    return matches


def _skip_if_known_gap(modem_name: str, context: str) -> None:
    """Skip test if modem has known fixture gap."""
    if modem_name in KNOWN_FIXTURE_GAPS:
        pytest.skip(f"Known gap: {KNOWN_FIXTURE_GAPS[modem_name]}")


class TestYamlHintsVsFixtures:
    """Validate YAML detection hints (pre_auth, post_auth) match fixture HTML.

    These tests prove the YAML-driven detection works with real modem HTML.
    This is the fixture validation test harness from v3.12.0 architecture.

    Note: Some tests are skipped for known fixture gaps. See KNOWN_FIXTURE_GAPS.
    """

    @pytest.mark.parametrize(
        "config_path",
        get_modems_with_pre_auth(),
        ids=lambda p: str(p.relative_to(PROJECT_ROOT)),
    )
    def test_pre_auth_match_fixtures(self, config_path: Path):
        """Verify detection.pre_auth patterns match login page fixtures."""
        modem_name = config_path.parent.name
        config = load_config(config_path)
        pre_auth = config.get("detection", {}).get("pre_auth", [])

        if not pre_auth:
            pytest.skip("No pre_auth defined")

        login_fixtures = _find_login_fixtures(config_path)
        if not login_fixtures:
            pytest.skip("No login fixtures available")

        usable_fixtures = _filter_usable_login_fixtures(login_fixtures)
        if not usable_fixtures:
            _skip_if_known_gap(modem_name, "login_fixtures")
            pytest.skip("No usable login fixtures (all are error/JSON pages)")

        matches_found = _find_marker_matches(usable_fixtures, pre_auth)
        if not matches_found:
            _skip_if_known_gap(modem_name, "pre_auth")

        assert matches_found, (
            f"{modem_name}: No pre_auth patterns matched any fixtures.\n"
            f"  Patterns: {pre_auth}\n"
            f"  Fixtures: {[f.name for f in usable_fixtures]}"
        )

    @pytest.mark.parametrize(
        "config_path",
        get_modems_with_post_auth(),
        ids=lambda p: str(p.relative_to(PROJECT_ROOT)),
    )
    def test_post_auth_match_fixtures(self, config_path: Path):
        """Verify detection.post_auth patterns match data page fixtures."""
        modem_name = config_path.parent.name
        config = load_config(config_path)
        post_auth = config.get("detection", {}).get("post_auth", [])

        if not post_auth:
            pytest.skip("No post_auth defined")

        data_fixtures = _find_data_fixtures(config_path)
        if not data_fixtures:
            pytest.skip("No data fixtures available")

        usable_fixtures = _filter_usable_data_fixtures(data_fixtures)
        if not usable_fixtures:
            _skip_if_known_gap(modem_name, "data_fixtures")
            pytest.skip("No usable data fixtures (all are error pages)")

        matches_found = _find_marker_matches(usable_fixtures, post_auth)
        if not matches_found:
            _skip_if_known_gap(modem_name, "post_auth")

        assert matches_found, (
            f"{modem_name}: No post_auth patterns matched any fixtures.\n"
            f"  Patterns: {post_auth}\n"
            f"  Fixtures: {[f.name for f in usable_fixtures]}"
        )


class TestYamlHintsCoverage:
    """Test coverage of YAML hints across modems.

    These tests document which modems have complete YAML hints and which
    need additional work. They don't fail but provide visibility.
    """

    def test_pre_auth_coverage_report(self):
        """Report which modems have detection.pre_auth defined."""
        configs = get_complete_modem_configs()
        with_pre_auth = 0
        without_pre_auth = []

        for path in configs:
            config = load_config(path)
            if config.get("detection", {}).get("pre_auth"):
                with_pre_auth += 1
            else:
                modem_name = f"{config.get('manufacturer', '?')}/{config.get('model', '?')}"
                without_pre_auth.append(modem_name)

        coverage_pct = (with_pre_auth / len(configs) * 100) if configs else 0
        print(f"\npre_auth coverage: {with_pre_auth}/{len(configs)} ({coverage_pct:.0f}%)")
        if without_pre_auth:
            print(f"Missing pre_auth: {', '.join(without_pre_auth[:5])}")
            if len(without_pre_auth) > 5:
                print(f"  ... and {len(without_pre_auth) - 5} more")

    def test_post_auth_coverage_report(self):
        """Report which modems have detection.post_auth defined."""
        configs = get_complete_modem_configs()
        with_post_auth = 0
        without_post_auth = []

        for path in configs:
            config = load_config(path)
            if config.get("detection", {}).get("post_auth"):
                with_post_auth += 1
            else:
                modem_name = f"{config.get('manufacturer', '?')}/{config.get('model', '?')}"
                without_post_auth.append(modem_name)

        coverage_pct = (with_post_auth / len(configs) * 100) if configs else 0
        print(f"\npost_auth coverage: {with_post_auth}/{len(configs)} ({coverage_pct:.0f}%)")
        if without_post_auth:
            print(f"Missing post_auth: {', '.join(without_post_auth[:5])}")
            if len(without_post_auth) > 5:
                print(f"  ... and {len(without_post_auth) - 5} more")

    def test_fixtures_coverage_report(self):
        """Report which modems have fixtures for hint validation."""
        configs = get_complete_modem_configs()
        with_fixtures = 0
        without_fixtures = []

        for path in configs:
            config = load_config(path)
            fixtures_dir = path.parent / "fixtures"
            if fixtures_dir.exists() and list(fixtures_dir.glob("*.html")):
                with_fixtures += 1
            else:
                modem_name = f"{config.get('manufacturer', '?')}/{config.get('model', '?')}"
                without_fixtures.append(modem_name)

        coverage_pct = (with_fixtures / len(configs) * 100) if configs else 0
        print(f"\nFixtures coverage: {with_fixtures}/{len(configs)} ({coverage_pct:.0f}%)")
        if without_fixtures:
            print(f"Missing fixtures: {', '.join(without_fixtures[:5])}")
            if len(without_fixtures) > 5:
                print(f"  ... and {len(without_fixtures) - 5} more")


class TestModemConfigSchemaValidation:
    """Test ModemConfig pydantic model validation.

    Uses SCHEMA_VALIDATION_CASES table defined at top of file.
    Each row specifies: (test_id, status, parser_config, should_pass, error_contains)

    This tests the schema's enforcement that verified/awaiting_verification
    modems require parser config, while in_progress/unsupported don't.
    """

    @pytest.mark.parametrize(
        "test_id,status,parser_config,should_pass,error_contains",
        SCHEMA_VALIDATION_CASES,
        ids=lambda x: x if isinstance(x, str) else None,
    )
    def test_parser_requirements_by_status(
        self,
        test_id: str,
        status: str,
        parser_config: dict | None,
        should_pass: bool,
        error_contains: list[str],
    ):
        """Validate parser requirements based on modem status."""
        from pydantic import ValidationError

        from custom_components.cable_modem_monitor.modem_config.schema import (
            AuthConfig,
            ModemConfig,
            ParserConfig,
            ParserStatus,
            StatusMetadata,
        )

        # Convert string status to enum
        status_enum = ParserStatus(status)

        # Build parser config if provided
        parser = ParserConfig(**parser_config) if parser_config else None

        if should_pass:
            # Should NOT raise
            config = ModemConfig(
                manufacturer="Test",
                model="TestModem",
                auth=AuthConfig(),
                status_info=StatusMetadata(status=status_enum),
                parser=parser,
            )
            assert config.manufacturer == "Test"
            if parser:
                assert config.parser is not None
        else:
            # Should raise ValidationError
            with pytest.raises(ValidationError) as exc_info:
                ModemConfig(
                    manufacturer="Test",
                    model="TestModem",
                    auth=AuthConfig(),
                    status_info=StatusMetadata(status=status_enum),
                    parser=parser,
                )

            # Verify error message contains expected strings
            error_msg = str(exc_info.value).lower()
            for expected in error_contains:
                assert expected in error_msg, f"Expected '{expected}' in error: {error_msg}"
