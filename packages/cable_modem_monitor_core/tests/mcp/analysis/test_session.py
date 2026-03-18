"""Tests for Phase 3: Session detection.

Session detection tests are fixture-driven. Utility function tests
(cookie name matching, Set-Cookie parsing) are table-driven since
they test pure functions with scalar inputs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.mcp.analysis.session import (
    SessionDetail,
    _cookie_name_from_set_cookie,
    _is_session_cookie,
    detect_session,
)

from tests.conftest import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "session"
VALID_DIR = FIXTURES_DIR / "valid"

VALID_FIXTURES = collect_fixtures(VALID_DIR)


# =====================================================================
# Session detection - fixture-driven
# =====================================================================


@pytest.mark.parametrize("fixture_path", VALID_FIXTURES, ids=[f.stem for f in VALID_FIXTURES])
def test_session_cookie(fixture_path: Path) -> None:
    """Correct cookie_name detected for each fixture."""
    data = load_fixture(fixture_path)
    warnings: list[str] = []
    result = detect_session(data["_entries"], data["_transport"], data["_auth_strategy"], warnings)
    assert result.cookie_name == data["_expected_cookie"]


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if "_expected_headers" in load_fixture(f)],
    ids=[f.stem for f in VALID_FIXTURES if "_expected_headers" in load_fixture(f)],
)
def test_session_headers(fixture_path: Path) -> None:
    """Session headers detected correctly for fixtures that specify them."""
    data = load_fixture(fixture_path)
    warnings: list[str] = []
    result = detect_session(data["_entries"], data["_transport"], data["_auth_strategy"], warnings)
    for key, value in data["_expected_headers"].items():
        assert key in result.headers, f"Missing session header: {key}"
        assert result.headers[key] == value


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if "_expected_token_prefix" in load_fixture(f)],
    ids=[f.stem for f in VALID_FIXTURES if "_expected_token_prefix" in load_fixture(f)],
)
def test_session_token_prefix(fixture_path: Path) -> None:
    """Token prefix detected correctly for fixtures that specify it."""
    data = load_fixture(fixture_path)
    warnings: list[str] = []
    result = detect_session(data["_entries"], data["_transport"], data["_auth_strategy"], warnings)
    assert result.token_prefix == data["_expected_token_prefix"]


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if "_expected_warning" in load_fixture(f)],
    ids=[f.stem for f in VALID_FIXTURES if "_expected_warning" in load_fixture(f)],
)
def test_session_expected_warnings(fixture_path: Path) -> None:
    """Fixtures with _expected_warning produce the expected warning."""
    data = load_fixture(fixture_path)
    warnings: list[str] = []
    detect_session(data["_entries"], data["_transport"], data["_auth_strategy"], warnings)
    expected = data["_expected_warning"]
    assert any(expected in w for w in warnings), f"Expected warning containing {expected!r}, got {warnings}"


# =====================================================================
# Warning behavior - fixture-driven
# =====================================================================


class TestSessionWarnings:
    """Session detection warning behavior across transports."""

    def test_max_concurrent_warning_for_form(self) -> None:
        """max_concurrent warning emitted for non-none, non-HNAP auth."""
        data = load_fixture(VALID_DIR / "form_with_cookie.json")
        warnings: list[str] = []
        detect_session(data["_entries"], data["_transport"], data["_auth_strategy"], warnings)
        assert any("max_concurrent" in w for w in warnings)

    def test_no_max_concurrent_warning_for_hnap(self) -> None:
        """No max_concurrent warning for HNAP transport."""
        data = load_fixture(VALID_DIR / "hnap_implicit.json")
        warnings: list[str] = []
        detect_session(data["_entries"], data["_transport"], data["_auth_strategy"], warnings)
        assert not any("max_concurrent" in w for w in warnings)

    def test_no_max_concurrent_warning_for_none(self) -> None:
        """No max_concurrent warning for auth:none."""
        data = load_fixture(VALID_DIR / "none_no_cookies.json")
        warnings: list[str] = []
        detect_session(data["_entries"], data["_transport"], data["_auth_strategy"], warnings)
        assert not any("max_concurrent" in w for w in warnings)

    def test_cookie_on_none_auth_warns(self) -> None:
        """Cookie detected on auth:none modem produces warning."""
        data = load_fixture(VALID_DIR / "form_with_cookie.json")
        warnings: list[str] = []
        detect_session(data["_entries"], "http", "none", warnings)
        assert any("Cookie" in w and "auth:none" in w for w in warnings)


# =====================================================================
# Serialization - inline behavioral
# =====================================================================


class TestSessionDetailSerialization:
    """SessionDetail.to_dict() produces expected output."""

    def test_to_dict_stateless(self) -> None:
        """Stateless session serializes with empty cookie_name."""
        detail = SessionDetail()
        d = detail.to_dict()
        assert d["cookie_name"] == ""
        assert d["max_concurrent"] is None
        assert d["max_concurrent_confidence"] == "unknown"

    def test_to_dict_with_cookie(self) -> None:
        """Cookie-based session serializes correctly."""
        detail = SessionDetail(cookie_name="sessionId")
        assert detail.to_dict()["cookie_name"] == "sessionId"


# =====================================================================
# Utility function tests - table-driven
# =====================================================================

# ┌─────────────────┬──────────┬───────────────────────────┐
# │ name            │ expected │ description               │
# ├─────────────────┼──────────┼───────────────────────────┤
# │ sessionid       │ True     │ exact match               │
# │ PHPSESSID       │ True     │ case insensitive          │
# │ mySessionId     │ True     │ substring match           │
# │ uid             │ True     │ HNAP uid cookie           │
# │ token_data      │ True     │ token substring           │
# │ preferences     │ False    │ not session-related       │
# │ theme           │ False    │ not session-related       │
# └─────────────────┴──────────┴───────────────────────────┘

# fmt: off
COOKIE_NAME_CASES = [
    ("sessionid",    True,  "exact match"),
    ("PHPSESSID",    True,  "case insensitive"),
    ("mySessionId",  True,  "substring match"),
    ("uid",          True,  "HNAP uid"),
    ("token_data",   True,  "token substring"),
    ("preferences",  False, "not session-related"),
    ("theme",        False, "not session-related"),
]
# fmt: on


@pytest.mark.parametrize(
    "name,expected,desc",
    COOKIE_NAME_CASES,
    ids=[c[2] for c in COOKIE_NAME_CASES],
)
def test_is_session_cookie(name: str, expected: bool, desc: str) -> None:
    """Session cookie name detection works for common patterns."""
    assert _is_session_cookie(name) == expected


class TestCookieNameFromSetCookie:
    """Cookie name extraction from Set-Cookie header value."""

    def test_simple(self) -> None:
        """Extracts name from simple Set-Cookie."""
        assert _cookie_name_from_set_cookie("sessionId=abc123") == "sessionId"

    def test_with_attributes(self) -> None:
        """Extracts name ignoring cookie attributes."""
        assert _cookie_name_from_set_cookie("PHPSESSID=xyz; path=/; HttpOnly") == "PHPSESSID"

    def test_empty(self) -> None:
        """Returns empty string for malformed header."""
        assert _cookie_name_from_set_cookie("invalid") == ""
