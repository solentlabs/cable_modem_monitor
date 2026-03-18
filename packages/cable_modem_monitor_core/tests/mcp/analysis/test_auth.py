"""Tests for Phase 2: Auth strategy detection.

Strategy detection, field extraction, and edge case tests are
fixture-driven. Utility function tests (login URL, path, form params,
encoding) are table-driven since they test pure functions with scalar
inputs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.mcp.analysis import AuthDetail
from solentlabs.cable_modem_monitor_core.mcp.analysis.auth import detect_auth
from solentlabs.cable_modem_monitor_core.mcp.analysis.auth.hnap import (
    _detect_hmac_algorithm,
)
from solentlabs.cable_modem_monitor_core.mcp.analysis.auth.http import (
    _extract_form_pbkdf2,
    _extract_url_token_parts,
    _HttpAuthSignals,
    _is_login_url,
    _parse_auth_scheme,
    classify_form_fields,
    detect_encoding,
)
from solentlabs.cable_modem_monitor_core.mcp.validation.har_utils import (
    parse_form_params,
    path_from_url,
)

from tests.conftest import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "auth"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"

VALID_FIXTURES = collect_fixtures(VALID_DIR)
INVALID_FIXTURES = collect_fixtures(INVALID_DIR)


# =====================================================================
# Strategy detection - fixture-driven
# =====================================================================


@pytest.mark.parametrize("fixture_path", VALID_FIXTURES, ids=[f.stem for f in VALID_FIXTURES])
def test_valid_auth_strategy(fixture_path: Path) -> None:
    """Correct strategy and confidence for each valid fixture."""
    data = load_fixture(fixture_path)
    warnings: list[str] = []
    hard_stops: list[str] = []
    result = detect_auth(data["_entries"], data["_transport"], warnings, hard_stops)
    assert result.strategy == data["_expected_strategy"]
    assert result.confidence == data["_expected_confidence"]
    assert not hard_stops


@pytest.mark.parametrize("fixture_path", INVALID_FIXTURES, ids=[f.stem for f in INVALID_FIXTURES])
def test_invalid_auth_hard_stop(fixture_path: Path) -> None:
    """Invalid fixtures produce expected strategy and hard stop."""
    data = load_fixture(fixture_path)
    warnings: list[str] = []
    hard_stops: list[str] = []
    result = detect_auth(data["_entries"], data["_transport"], warnings, hard_stops)
    assert result.strategy == data["_expected_strategy"]
    assert result.confidence == data["_expected_confidence"]
    assert any(data["_expected_hard_stop"] in hs for hs in hard_stops)


# =====================================================================
# Field extraction - fixture-driven
# =====================================================================


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if "_expected_fields" in load_fixture(f)],
    ids=[f.stem for f in VALID_FIXTURES if "_expected_fields" in load_fixture(f)],
)
def test_auth_field_extraction(fixture_path: Path) -> None:
    """Strategy-specific fields extracted correctly."""
    data = load_fixture(fixture_path)
    result = detect_auth(data["_entries"], data["_transport"], [], [])
    for key, value in data["_expected_fields"].items():
        assert key in result.fields, f"Missing auth field: {key}"
        assert result.fields[key] == value, f"Auth field {key}: expected {value!r}, got {result.fields[key]!r}"


# =====================================================================
# Warnings - fixture-driven
# =====================================================================


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if "_expected_warning" in load_fixture(f)],
    ids=[f.stem for f in VALID_FIXTURES if "_expected_warning" in load_fixture(f)],
)
def test_auth_expected_warnings(fixture_path: Path) -> None:
    """Fixtures with _expected_warning produce the expected warning."""
    data = load_fixture(fixture_path)
    warnings: list[str] = []
    detect_auth(data["_entries"], data["_transport"], warnings, [])
    expected = data["_expected_warning"]
    assert any(expected in w for w in warnings), f"Expected warning containing {expected!r}, got {warnings}"


# =====================================================================
# Edge cases - pure function behavioral tests (no HAR data)
# =====================================================================


class TestAuthUtilityEdgeCases:
    """Edge cases for auth utility functions (scalar inputs, no HAR dicts)."""

    def test_url_token_no_match_returns_none(self) -> None:
        """URL without login_ prefix returns no url_token match."""
        assert _extract_url_token_parts("/status.html?session=abc") is None


# =====================================================================
# Serialization - inline behavioral
# =====================================================================


class TestAuthDetailSerialization:
    """AuthDetail.to_dict() produces expected output."""

    def test_to_dict(self) -> None:
        """Serialization includes strategy, fields, and confidence."""
        detail = AuthDetail(strategy="form", fields={"action": "/login"}, confidence="high")
        d = detail.to_dict()
        assert d["strategy"] == "form"
        assert d["fields"]["action"] == "/login"
        assert d["confidence"] == "high"


# =====================================================================
# Auth scheme parsing - table-driven
# =====================================================================

# fmt: off
AUTH_SCHEME_CASES = [
    # (www_authenticate,                                       expected, desc)
    ('Basic realm="modem"',                                    "basic",  "basic with realm"),
    ('Digest realm="modem", nonce="abc", qop="auth"',          "digest", "digest with params"),
    ("Basic",                                                  "basic",  "bare basic"),
    ("Digest",                                                 "digest", "bare digest"),
    ("bearer token=xyz",                                       "bearer", "bearer token"),
    ("",                                                       "",       "empty header"),
    ("   Basic   ",                                            "basic",  "whitespace padded"),
    ("BASIC realm=modem",                                      "basic",  "uppercase basic"),
    ("DIGEST realm=modem",                                     "digest", "uppercase digest"),
]
# fmt: on


@pytest.mark.parametrize(
    "www_authenticate,expected,desc",
    AUTH_SCHEME_CASES,
    ids=[c[2] for c in AUTH_SCHEME_CASES],
)
def test_parse_auth_scheme(www_authenticate: str, expected: str, desc: str) -> None:
    """WWW-Authenticate header scheme parsed per RFC 7235."""
    assert _parse_auth_scheme(www_authenticate) == expected


# =====================================================================
# Utility function tests - table-driven
# =====================================================================

# ┌──────────────────────────────┬──────────┬──────────────────────────┐
# │ url                          │ expected │ description              │
# ├──────────────────────────────┼──────────┼──────────────────────────┤
# │ /goform/login                │ True     │ goform login endpoint    │
# │ /cgi-bin/auth                │ True     │ cgi-bin endpoint         │
# │ /api/v1/session/login        │ True     │ API session endpoint     │
# │ /LOGIN                       │ True     │ case insensitive         │
# │ /status.html                 │ False    │ data page                │
# │ /info.html                   │ False    │ info page                │
# │ /                            │ False    │ root path                │
# └──────────────────────────────┴──────────┴──────────────────────────┘

# fmt: off
LOGIN_URL_CASES = [
    ("/goform/login",           True,  "goform login"),
    ("/cgi-bin/auth",           True,  "cgi-bin endpoint"),
    ("/api/v1/session/login",   True,  "API session endpoint"),
    ("/LOGIN",                  True,  "case insensitive"),
    ("/status.html",            False, "data page"),
    ("/info.html",              False, "info page"),
    ("/",                       False, "root path"),
]
# fmt: on


@pytest.mark.parametrize(
    "url,expected,desc",
    LOGIN_URL_CASES,
    ids=[c[2] for c in LOGIN_URL_CASES],
)
def test_is_login_url(url: str, expected: bool, desc: str) -> None:
    """Login URL detection matches expected patterns."""
    assert _is_login_url(url) == expected


# ┌──────────────────────────────────────┬──────────────┬────────────┐
# │ url                                  │ expected     │ description│
# ├──────────────────────────────────────┼──────────────┼────────────┤
# │ http://host/path                     │ /path        │ full URL   │
# │ /relative/path                       │ /relative... │ relative   │
# │ http://host/path?query=1             │ /path        │ with query │
# │ /path?query=1                        │ /path        │ rel+query  │
# │ http://host/                         │ /            │ root       │
# │ http://host                          │ /            │ no path    │
# └──────────────────────────────────────┴──────────────┴────────────┘

# fmt: off
PATH_CASES = [
    ("http://host/path",           "/path",           "full URL"),
    ("/relative/path",             "/relative/path",  "relative"),
    ("http://host/path?query=1",   "/path",           "with query"),
    ("/path?query=1",              "/path",           "rel with query"),
    ("http://host/",               "/",               "root"),
    ("http://host",                "/",               "no path"),
]
# fmt: on


@pytest.mark.parametrize(
    "url,expected,desc",
    PATH_CASES,
    ids=[c[2] for c in PATH_CASES],
)
def test_path_from_url(url: str, expected: str, desc: str) -> None:
    """Path extraction from URL works for all forms."""
    assert path_from_url(url) == expected


class TestParseFormParams:
    """Form parameter parsing from HAR postData."""

    def test_from_params_array(self) -> None:
        """Parses structured params array."""
        post_data = {
            "params": [
                {"name": "user", "value": "admin"},
                {"name": "pass", "value": "secret"},
            ]
        }
        assert parse_form_params(post_data) == {
            "user": "admin",
            "pass": "secret",
        }

    def test_from_text(self) -> None:
        """Parses URL-encoded text fallback."""
        post_data = {"text": "user=admin&pass=secret"}
        assert parse_form_params(post_data) == {
            "user": "admin",
            "pass": "secret",
        }

    def test_empty(self) -> None:
        """Empty postData returns empty dict."""
        assert parse_form_params({}) == {}


class TestClassifyFormFields:
    """Form field classification into username, password, hidden."""

    def test_explicit_fields(self) -> None:
        """Identifies username and password fields by name."""
        params = {
            "loginUsername": "admin",
            "loginPassword": "pass",
            "webToken": "",
        }
        user, pwd, hidden = classify_form_fields(params)
        assert user == "loginUsername"
        assert pwd == "loginPassword"
        assert hidden == {"webToken": ""}

    def test_defaults(self) -> None:
        """Defaults to 'username' and 'password' when no match."""
        params = {"field1": "val1", "field2": "val2"}
        user, pwd, hidden = classify_form_fields(params)
        assert user == "username"
        assert pwd == "password"
        assert hidden == {"field1": "val1", "field2": "val2"}


class TestDetectEncoding:
    """Password encoding detection (base64 vs plain)."""

    def test_base64_value(self) -> None:
        """Valid base64-encoded password detected."""
        assert detect_encoding({"password": "YWRtaW4="}, "password") == "base64"

    def test_plain_value(self) -> None:
        """Plain text password detected."""
        assert detect_encoding({"password": "admin"}, "password") == "plain"

    def test_empty_value(self) -> None:
        """Empty password defaults to plain."""
        assert detect_encoding({"password": ""}, "password") == "plain"

    def test_missing_field(self) -> None:
        """Missing field defaults to plain."""
        assert detect_encoding({}, "password") == "plain"


# =====================================================================
# _HttpAuthSignals.describe() - table-driven
# =====================================================================


class TestHttpAuthSignalsDescribe:
    """Tests for describe() method with various signal combinations."""

    def test_digest_challenge_signal(self) -> None:
        """Digest challenge shows in description."""
        signals = _HttpAuthSignals(digest_challenge=True, has_any_auth_signal=True)
        assert "WWW-Authenticate: Digest" in signals.describe()

    def test_401_signal(self) -> None:
        """401 response shows in description."""
        signals = _HttpAuthSignals(has_401=True, has_any_auth_signal=True)
        assert "401 response" in signals.describe()

    def test_authorization_header_signal(self) -> None:
        """Authorization header shows in description."""
        signals = _HttpAuthSignals(has_authorization_header=True, has_any_auth_signal=True)
        assert "Authorization header" in signals.describe()

    def test_form_post_signal(self) -> None:
        """Form POST shows endpoint path in description."""
        signals = _HttpAuthSignals(
            form_post_entry={
                "request": {"url": "http://192.168.100.1/goform/login", "method": "POST"},
                "response": {"status": 200},
            },
            has_any_auth_signal=True,
        )
        desc = signals.describe()
        assert "POST to /goform/login" in desc

    def test_set_cookie_signal(self) -> None:
        """Set-Cookie after login shows in description."""
        signals = _HttpAuthSignals(has_set_cookie_after_login=True, has_any_auth_signal=True)
        assert "Set-Cookie after login" in signals.describe()

    def test_no_signals_returns_ambiguous(self) -> None:
        """No specific signals returns ambiguous message."""
        signals = _HttpAuthSignals(has_any_auth_signal=True)
        assert signals.describe() == "ambiguous auth artifacts"


# =====================================================================
# HNAP auth edge cases
# =====================================================================


class TestHnapAuthEdgeCases:
    """Edge cases for HNAP auth detection."""

    def test_whitespace_only_hnap_auth_header(self) -> None:
        """Whitespace-only HNAP_AUTH header is treated as absent."""
        entries = [
            {
                "request": {
                    "url": "http://192.168.100.1/HNAP1/",
                    "method": "POST",
                    "headers": [{"name": "HNAP_AUTH", "value": "   "}],
                },
                "response": {"status": 200},
            }
        ]
        result = _detect_hmac_algorithm(entries)
        assert result is None


# =====================================================================
# form_pbkdf2 empty guard
# =====================================================================


class TestFormPbkdf2EmptyGuard:
    """Edge case: empty pbkdf2_entries returns minimal detail."""

    def test_empty_pbkdf2_entries(self) -> None:
        """Empty pbkdf2 entries returns medium confidence without fields."""
        signals = _HttpAuthSignals(pbkdf2_entries=[], has_any_auth_signal=True)
        result = _extract_form_pbkdf2(signals)
        assert result.strategy == "form_pbkdf2"
        assert result.confidence == "medium"
        assert not result.fields
