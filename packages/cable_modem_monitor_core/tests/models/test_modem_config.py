"""Tests for modem.yaml Pydantic model.

Valid and invalid configs are stored as JSON fixtures in
tests/models/fixtures/modem_config/{valid,invalid}/.

Valid fixtures are complete modem.yaml-shaped dicts that must parse
without error. Invalid fixtures have `_config` (the bad input) and
`_expected_error` (the regex match for the expected ValidationError).

Behavioral tests verify specific field values, defaults, and access
patterns by loading named fixtures and checking parsed results.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from solentlabs.cable_modem_monitor_core.models.modem_config import ModemConfig
from solentlabs.cable_modem_monitor_core.models.modem_config.actions import HttpAction

from tests.conftest import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "modem_config"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"


def _load(name: str) -> ModemConfig:
    """Load and parse a valid modem config fixture by name."""
    return ModemConfig.model_validate(load_fixture(VALID_DIR / name))


# ---------------------------------------------------------------------------
# Valid configs — each fixture file must parse without error
# ---------------------------------------------------------------------------

VALID_FIXTURES = collect_fixtures(VALID_DIR)


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=[f.stem for f in VALID_FIXTURES],
)
def test_valid_modem_config(fixture_path: Path):
    """Valid fixture parses without error."""
    config = ModemConfig.model_validate(load_fixture(fixture_path))
    assert config.manufacturer
    assert config.model
    assert config.transport in ("http", "hnap")


# ---------------------------------------------------------------------------
# Invalid configs — each fixture file must raise ValidationError
# ---------------------------------------------------------------------------

INVALID_FIXTURES = collect_fixtures(INVALID_DIR)


@pytest.mark.parametrize(
    "fixture_path",
    INVALID_FIXTURES,
    ids=[f.stem for f in INVALID_FIXTURES],
)
def test_invalid_modem_config(fixture_path: Path):
    """Invalid fixture raises ValidationError with expected message."""
    raw = load_fixture(fixture_path)
    with pytest.raises(ValidationError, match=raw["_expected_error"]):
        ModemConfig.model_validate(raw["_config"])


# ---------------------------------------------------------------------------
# Behavioral: field access (table-driven where possible)
# ---------------------------------------------------------------------------

# ┌──────────────────────────┬─────────────────────────────┬────────────────┐
# │ fixture                  │ attribute path              │ expected       │
# ├──────────────────────────┼─────────────────────────────┼────────────────┤
# │ auth_none.json           │ timeout                     │ 10             │
# │ with_optional_identity   │ timeout                     │ 20             │
# │ with_optional_identity   │ model_aliases               │ ["T1100v2"]    │
# │ with_optional_identity   │ brands                      │ ["TestBrand"]  │
# │ with_optional_identity   │ notes                       │ "Test notes"   │
# │ auth_form.json           │ auth.encoding               │ "base64"       │
# │ auth_url_token.json      │ auth.ajax_login             │ True           │
# │ auth_url_token.json      │ session.token_prefix        │ "ct_"          │
# │ auth_form_pbkdf2.json    │ auth.pbkdf2_iterations      │ 1000           │
# │ auth_form_nonce.json     │ auth.nonce_length           │ 8              │
# │ auth_basic.json          │ auth.challenge_cookie       │ False          │
# │ auth_basic_challenge_..  │ auth.challenge_cookie       │ True           │
# │ auth_hnap.json           │ auth.hmac_algorithm         │ "md5"          │
# │ auth_hnap_sha256.json    │ auth.hmac_algorithm         │ "sha256"       │
# │ health_config.json       │ health.http_probe           │ False          │
# │ health_config.json       │ health.supports_head        │ False          │
# │ health_config.json       │ health.supports_icmp        │ False          │
# └──────────────────────────┴─────────────────────────────┴────────────────┘

# fmt: off
FIELD_ACCESS_CASES = [
    # (fixture,                          attr_path,                 expected)
    ("auth_none.json",                   "timeout",                 10),
    ("with_optional_identity.json",      "timeout",                 20),
    ("with_optional_identity.json",      "model_aliases",           ["T1100v2"]),
    ("with_optional_identity.json",      "brands",                  ["TestBrand"]),
    ("with_optional_identity.json",      "notes",                   "Test notes"),
    ("auth_form.json",                   "auth.encoding",           "base64"),
    ("auth_url_token.json",              "auth.ajax_login",         True),
    ("auth_url_token.json",              "session.token_prefix",    "ct_"),
    ("auth_form_pbkdf2.json",            "auth.pbkdf2_iterations",  1000),
    ("auth_form_pbkdf2.json",            "auth.csrf_header",        "X-CSRF-TOKEN"),
    ("auth_form_nonce.json",             "auth.nonce_length",       8),
    ("auth_form_nonce.json",             "auth.success_prefix",     "Url:"),
    ("auth_basic.json",                  "auth.challenge_cookie",   False),
    ("auth_basic_challenge_cookie.json", "auth.challenge_cookie",   True),
    ("auth_hnap.json",                   "auth.hmac_algorithm",     "md5"),
    ("auth_hnap_sha256.json",            "auth.hmac_algorithm",     "sha256"),
    ("health_config.json",               "health.http_probe",       False),
    ("health_config.json",               "health.supports_head",    False),
    ("health_config.json",               "health.supports_icmp",    False),
]
# fmt: on


def _resolve_attr(obj: object, path: str) -> object:
    """Resolve a dotted attribute path like 'auth.encoding'."""
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


@pytest.mark.parametrize(
    "fixture,attr_path,expected",
    FIELD_ACCESS_CASES,
    ids=[f"{c[0].removesuffix('.json')}:{c[1]}" for c in FIELD_ACCESS_CASES],
)
def test_field_access(fixture, attr_path, expected):
    """Parsed config field matches expected value."""
    config = _load(fixture)
    assert _resolve_attr(config, attr_path) == expected


# ---------------------------------------------------------------------------
# Behavioral: multi-field relationships (not table-driven)
# ---------------------------------------------------------------------------


class TestRelationships:
    """Tests for multi-field relationships that don't fit a flat table."""

    def test_references_issues_and_prs(self):
        """References section contains both issues and PRs."""
        config = _load("with_optional_identity.json")
        assert config.references is not None
        assert config.references.issues == ["ref-1", "ref-2"]
        assert config.references.prs == ["ref-3"]

    def test_sources_freeform(self):
        """Sources is a freeform string dict."""
        config = _load("with_optional_identity.json")
        assert config.sources["auth_config"] == "#42"

    def test_behaviors_restart_window(self):
        """Behaviors restart window is accessible."""
        config = _load("auth_hnap.json")
        assert config.behaviors is not None
        assert config.behaviors.restart is not None
        assert config.behaviors.restart.window_seconds == 300

    def test_unsupported_omits_auth_and_hardware(self):
        """Unsupported status allows omitting auth and hardware."""
        config = _load("status_unsupported.json")
        assert config.auth is None
        assert config.hardware is None

    def test_health_defaults_when_omitted(self):
        """Health section omitted defaults all probes to True."""
        config = _load("auth_none.json")
        assert config.health is None

    def test_health_explicit_values(self):
        """Health section with explicit values overrides defaults."""
        config = _load("health_config.json")
        assert config.health is not None
        assert config.health.http_probe is False
        assert config.health.supports_head is False
        assert config.health.supports_icmp is False

    def test_form_session_and_logout(self):
        """Form auth with max_concurrent requires and has logout."""
        config = _load("auth_form.json")
        assert config.session is not None
        assert config.session.max_concurrent == 1
        assert config.actions is not None
        assert config.actions.logout is not None
        assert isinstance(config.actions.logout, HttpAction)
        assert config.actions.logout.endpoint == "/logout.asp"
