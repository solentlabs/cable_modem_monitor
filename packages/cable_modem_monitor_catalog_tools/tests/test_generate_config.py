"""Tests for generate_config — config generation from analysis output.

Each fixture has ``_analysis`` (analysis result dict) and ``_metadata``
(caller-provided metadata). Valid fixtures produce configs that pass
Pydantic validation and cross-file checks. Invalid fixtures produce
expected errors.

Spot-check assertions use ``_expected_*`` fields in the fixture to
verify key properties of the generated output.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

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


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if "_expected_auth_fields" in load_fixture(f)],
    ids=[f.stem for f in VALID_FIXTURES if "_expected_auth_fields" in load_fixture(f)],
)
def test_valid_auth_fields(fixture_path: Path) -> None:
    """Auth fields, including resolved ambiguities, land in modem.yaml; explicit nones stay absent."""
    fixture = load_fixture(fixture_path)
    auth = yaml.safe_load(generate_config(fixture["_analysis"], fixture["_metadata"]).modem_yaml)["auth"]
    for key, value in fixture["_expected_auth_fields"].items():
        assert auth.get(key) == value, f"auth.{key}: expected {value!r}, got {auth.get(key)!r}"
    for key in fixture.get("_expected_absent_auth_fields", []):
        assert key not in auth, f"auth.{key} should be absent"


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

    def test_restart_action_with_json_body(self) -> None:
        """An observed JSON body becomes json_body, and the config validates."""
        fixture = load_fixture(VALID_DIR / "table_no_cookie.json")
        fixture["_analysis"]["actions"]["restart"] = {
            "type": "http",
            "method": "POST",
            "endpoint": "/rest/v1/system/reboot",
            "json_body": {"reboot": {"enable": True}},
        }
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        assert result.validation.valid, result.validation.errors
        restart = yaml.safe_load(result.modem_yaml)["actions"]["restart"]
        assert restart["json_body"] == {"reboot": {"enable": True}}
        assert "params" not in restart

    def test_json_rpc_restart_from_resolution(self) -> None:
        """A resolved actions.restart.method becomes a json_rpc action; the rest comes from the transport."""
        fixture = load_fixture(VALID_DIR / "json_rpc_resolved_restart.json")
        modem = yaml.safe_load(generate_config(fixture["_analysis"], fixture["_metadata"]).modem_yaml)
        assert modem["actions"] == {"restart": {"type": "json_rpc", "method": "SYS.reboot"}}

    def test_json_rpc_unresolved_restart_omitted(self) -> None:
        """A non-blocking restart left unresolved leaves no actions block, and generation stays valid."""
        fixture = load_fixture(VALID_DIR / "json_rpc_resolved_restart.json")
        fixture["_analysis"]["ambiguities"][-1]["resolution"] = None
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        assert result.validation.valid, result.validation.errors
        assert "actions" not in yaml.safe_load(result.modem_yaml)

    def test_no_actions_when_none(self) -> None:
        """No actions block when no actions detected."""
        fixture = load_fixture(VALID_DIR / "table_no_auth.json")
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        modem = yaml.safe_load(result.modem_yaml)
        assert "actions" not in modem


# ---------------------------------------------------------------------------
# Spot-check: channel key resolutions (parser.<section>.<key>)
# ---------------------------------------------------------------------------

_KEY_PATH = "parser.downstream.power"
_KEY_REASON = {"value": None, "reason": "the capture shows no such meaning"}

# ┌──────────────────────────┬──────────────────────────┬─────────┬──────────────────────────┐
# │ resolution               │ power key maps to        │ valid   │ description              │
# ├──────────────────────────┼──────────────────────────┼─────────┼──────────────────────────┤
# │ snr                      │ snr (float)              │ yes     │ fleet meaning applied    │
# │ lock_status              │ lock_status (lock_status)│ yes     │ type follows the field   │
# │ power_state              │ power_state (float)      │ yes     │ new meaning keeps type   │
# │ none, with reason        │ (key dropped)            │ yes     │ explicit none            │
# │ unresolved               │ (key dropped)            │ yes     │ non-blocking, omitted    │
# │ none, no reason          │ (key dropped)            │ no      │ a blank is rejected      │
# └──────────────────────────┴──────────────────────────┴─────────┴──────────────────────────┘
#
# fmt: off
KEY_RESOLUTION_CASES: list[tuple[dict[str, Any] | None, tuple[str, str] | None, bool, str]] = [
    # (resolution,               maps_to,                          valid, id)
    ({"value": "snr"},           ("snr", "float"),                 True,  "fleet-meaning"),
    ({"value": "lock_status"},   ("lock_status", "lock_status"),   True,  "type-follows-field"),
    ({"value": "power_state"},   ("power_state", "float"),         True,  "new-meaning"),
    (_KEY_REASON,                None,                             True,  "explicit-none"),
    (None,                       None,                             True,  "unresolved"),
    ({"value": None},            None,                             False, "blank"),
]
# fmt: on


def _with_key_ambiguity(path: str, resolution: dict[str, Any] | None) -> dict[str, Any]:
    """The json_format fixture carrying one channel key ambiguity."""
    fixture = load_fixture(VALID_DIR / "json_format.json")
    fixture["_analysis"]["ambiguities"] = [
        {
            "field": path,
            "blocking": False,
            "candidates": [{"value": "power", "evidence": [], "corroborated_by": []}],
            "resolution": resolution,
        }
    ]
    return fixture


class TestChannelKeyResolution:
    """A resolved channel key rewrites its field before parser.yaml is built; none or unresolved drops it."""

    @pytest.mark.parametrize(
        "resolution,maps_to,valid",
        [c[:3] for c in KEY_RESOLUTION_CASES],
        ids=[c[3] for c in KEY_RESOLUTION_CASES],
    )
    def test_key_resolution(
        self, resolution: dict[str, Any] | None, maps_to: tuple[str, str] | None, valid: bool
    ) -> None:
        """The resolution picks the key's field and type, or drops the key."""
        fixture = _with_key_ambiguity(_KEY_PATH, resolution)
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        assert result.validation.valid is valid, result.validation.errors
        assert result.parser_yaml is not None
        fields = yaml.safe_load(result.parser_yaml)["downstream"]["fields"]
        power = [(f["field"], f["type"]) for f in fields if f["key"] == "power"]
        assert power == ([maps_to] if maps_to else [])

    def test_modem_yaml_untouched(self) -> None:
        """A parser path never lands in modem.yaml."""
        fixture = _with_key_ambiguity(_KEY_PATH, {"value": "snr"})
        assert "parser" not in yaml.safe_load(generate_config(fixture["_analysis"], fixture["_metadata"]).modem_yaml)

    def test_analysis_not_mutated(self) -> None:
        """Resolving rewrites a copy; the caller's analysis sections are unchanged."""
        fixture = _with_key_ambiguity(_KEY_PATH, {"value": "snr"})
        before = copy.deepcopy(fixture["_analysis"]["sections"])
        generate_config(fixture["_analysis"], fixture["_metadata"])
        assert fixture["_analysis"]["sections"] == before

    def test_unknown_key_is_an_error(self) -> None:
        """A path naming a key the section does not map is reported, not ignored."""
        fixture = _with_key_ambiguity("parser.downstream.nokey", {"value": "snr"})
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        assert "parser.downstream.nokey: the analysis maps no such channel key" in result.validation.errors


# ---------------------------------------------------------------------------
# Spot-check: json arrays form (several channel arrays in one section)
# ---------------------------------------------------------------------------


def _with_arrays(ambiguity: dict[str, Any] | None = None) -> dict[str, Any]:
    """The json_format fixture whose downstream holds a QAM and an OFDM array."""
    fixture = load_fixture(VALID_DIR / "json_format.json")
    fixture["_analysis"]["sections"]["downstream"] = {
        "format": "json",
        "resource": "/api/downstream",
        "arrays": [
            {
                "array_path": "data.qam",
                "mappings": [
                    {"key": "channelId", "field": "channel_id", "type": "integer"},
                    {"key": "status", "field": "status", "type": "string"},
                    {"key": "corrected", "field": "corrected", "type": "integer"},
                ],
                "channel_type": {"fixed": "qam"},
                "channel_count": 32,
            },
            {
                "array_path": "data.ofdm",
                "mappings": [
                    {"key": "ofdmId", "field": "channel_id", "type": "integer"},
                    {"key": "status", "field": "status", "type": "string"},
                ],
                "channel_type": {"fixed": "ofdm"},
                "channel_count": 2,
            },
        ],
    }
    if ambiguity:
        fixture["_analysis"]["ambiguities"] = [ambiguity]
    return fixture


class TestJsonArraysForm:
    """Several analysis arrays become parser.yaml's arrays form, each with its own fields and type."""

    def test_arrays_written(self) -> None:
        fixture = _with_arrays()
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        assert result.validation.valid, result.validation.errors
        assert result.parser_yaml is not None
        downstream = yaml.safe_load(result.parser_yaml)["downstream"]
        assert "array_path" not in downstream
        assert [
            (a["array_path"], a["channel_type"], [f["key"] for f in a["fields"]]) for a in downstream["arrays"]
        ] == [
            ("data.qam", {"fixed": "qam"}, ["channelId", "status", "corrected"]),
            ("data.ofdm", {"fixed": "ofdm"}, ["ofdmId", "status"]),
        ]

    def test_aggregate_reads_every_array(self) -> None:
        """A counter mapped only inside an array still earns its aggregate."""
        fixture = _with_arrays()
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        assert result.parser_yaml is not None
        assert "total_corrected" in yaml.safe_load(result.parser_yaml)["aggregate"]

    def test_key_resolution_reaches_every_array(self) -> None:
        """A parser.<section>.<key> resolution rewrites the key in each array that maps it."""
        ambiguity = {
            "field": "parser.downstream.status",
            "blocking": False,
            "candidates": [{"value": "lock_status", "evidence": [], "corroborated_by": []}],
            "resolution": {"value": "lock_status"},
        }
        fixture = _with_arrays(ambiguity)
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        assert result.validation.valid, result.validation.errors
        assert result.parser_yaml is not None
        arrays = yaml.safe_load(result.parser_yaml)["downstream"]["arrays"]
        assert [[f["field"] for f in a["fields"] if f["key"] == "status"] for a in arrays] == [
            ["lock_status"],
            ["lock_status"],
        ]


class TestJavascriptJsonArraysForm:
    """An object variable's arrays become javascript_json arrays, each with its own mappings and type."""

    def test_arrays_written(self) -> None:
        fixture = load_fixture(VALID_DIR / "json_format.json")
        fixture["_analysis"]["sections"]["downstream"] = {
            "format": "javascript_json",
            "resource": "/wan.php",
            "variable": "channelData",
            "arrays": [
                {
                    "array_path": "ds_channels",
                    "mappings": [
                        {"key": "ChannelID", "field": "channel_id", "type": "integer"},
                        {"key": "Frequency", "field": "frequency", "type": "frequency"},
                    ],
                    "channel_type": {"fixed": "qam"},
                    "channel_count": 31,
                },
                {
                    "array_path": "ofdm_channels",
                    "mappings": [
                        {"key": "ChannelID", "field": "channel_id", "type": "integer"},
                        {"key": "Type", "field": "channel_type", "type": "string"},
                    ],
                    "channel_type": {"key": "Type", "map": {"OFDM": "ofdm"}},
                    "channel_count": 1,
                },
            ],
        }
        result = generate_config(fixture["_analysis"], fixture["_metadata"])
        assert result.validation.valid, result.validation.errors
        assert result.parser_yaml is not None
        downstream = yaml.safe_load(result.parser_yaml)["downstream"]
        assert (downstream["format"], downstream["variable"], "mappings" in downstream) == (
            "javascript_json",
            "channelData",
            False,
        )
        assert [(a["array_path"], a.get("channel_type"), a["mappings"]) for a in downstream["arrays"]] == [
            (
                "ds_channels",
                {"fixed": "qam"},
                [
                    {"key": "ChannelID", "field": "channel_id", "type": "integer"},
                    {"key": "Frequency", "field": "frequency", "type": "frequency"},
                ],
            ),
            (
                "ofdm_channels",
                None,
                [
                    {"key": "ChannelID", "field": "channel_id", "type": "integer"},
                    {"key": "Type", "field": "channel_type", "type": "string", "map": {"OFDM": "ofdm"}},
                ],
            ),
        ]


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
