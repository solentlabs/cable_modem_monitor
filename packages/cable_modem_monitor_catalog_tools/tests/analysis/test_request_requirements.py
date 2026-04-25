"""Tests for post-analysis request requirements detection.

Table-driven tests for pure utility functions.
Fixture-driven tests for the end-to-end detection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.request_requirements import (
    _extract_query_params,
    _is_known_cache_buster,
    detect_request_requirements,
)
from solentlabs.cable_modem_monitor_catalog_tools.analysis.session import SessionDetail

from tests._helpers import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "request_requirements"
FIXTURES = collect_fixtures(FIXTURES_DIR)


# =====================================================================
# detect_request_requirements — fixture-driven
# =====================================================================


def _session_from_fixture(data: dict[str, Any]) -> SessionDetail:
    """Build a SessionDetail with token_prefix from fixture if present."""
    return SessionDetail(token_prefix=data.get("_token_prefix", ""))


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=[f.stem for f in FIXTURES])
def test_query_params_detection(fixture_path: Path) -> None:
    """Correct query_params detected for each fixture."""
    data = load_fixture(fixture_path)
    session = _session_from_fixture(data)
    warnings: list[str] = []
    detect_request_requirements(data["_entries"], data["_transport"], session, warnings)
    assert session.query_params == data["_expected_query_params"]


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in FIXTURES if "_expected_warning" in load_fixture(f)],
    ids=[f.stem for f in FIXTURES if "_expected_warning" in load_fixture(f)],
)
def test_expected_warnings(fixture_path: Path) -> None:
    """Fixtures with _expected_warning produce the expected warning."""
    data = load_fixture(fixture_path)
    session = _session_from_fixture(data)
    warnings: list[str] = []
    detect_request_requirements(data["_entries"], data["_transport"], session, warnings)
    expected = data["_expected_warning"]
    assert any(expected in w for w in warnings), f"Expected warning containing {expected!r}, got {warnings}"


# =====================================================================
# No-warning cases — fixture-driven
# =====================================================================


class TestNoWarnings:
    """Cases that should NOT produce request requirements warnings."""

    def test_no_query_params_no_warning(self) -> None:
        """Standard modem with no query params produces no warning."""
        data = load_fixture(FIXTURES_DIR / "no_query_params.json")
        session = _session_from_fixture(data)
        warnings: list[str] = []
        detect_request_requirements(data["_entries"], data["_transport"], session, warnings)
        assert not any("query parameters" in w for w in warnings)

    def test_hnap_no_warning(self) -> None:
        """HNAP transport produces no warnings."""
        data = load_fixture(FIXTURES_DIR / "hnap_short_circuit.json")
        session = _session_from_fixture(data)
        warnings: list[str] = []
        detect_request_requirements(data["_entries"], data["_transport"], session, warnings)
        assert not warnings

    def test_token_prefix_no_warning(self) -> None:
        """url_token auth params are filtered — no warning."""
        data = load_fixture(FIXTURES_DIR / "token_prefix_filtered.json")
        session = _session_from_fixture(data)
        warnings: list[str] = []
        detect_request_requirements(data["_entries"], data["_transport"], session, warnings)
        assert not any("query parameters" in w for w in warnings)


# =====================================================================
# _is_known_cache_buster — table-driven
# =====================================================================

# fmt: off
_CACHE_BUSTER_CASES = [
    # (param_name, expected, description)
    ("_",    True,  "jQuery cache:false key"),
    ("_n",   False, "Arris session nonce"),
    ("t",    False, "generic param"),
    ("cb",   False, "custom cache-buster name"),
    ("v",    False, "version param"),
]
# fmt: on


@pytest.mark.parametrize(
    "param_name,expected,desc",
    _CACHE_BUSTER_CASES,
    ids=[c[2] for c in _CACHE_BUSTER_CASES],
)
def test_is_known_cache_buster(param_name: str, expected: bool, desc: str) -> None:
    """Known cache-buster detection works for common param names."""
    assert _is_known_cache_buster(param_name) == expected


# =====================================================================
# _extract_query_params — table-driven
# =====================================================================

# fmt: off
_EXTRACT_CASES = [
    # (url, expected, description)
    (
        "http://192.168.0.1/php/data.php?_n=13127",
        {"_n": "13127"},
        "single param",
    ),
    (
        "http://192.168.0.1/php/data.php?_n=13127&_=1767478481675",
        {"_n": "13127", "_": "1767478481675"},
        "multiple params",
    ),
    (
        "http://192.168.0.1/status.html",
        {},
        "no query string",
    ),
    (
        "http://192.168.0.1/api/data?key=",
        {"key": ""},
        "empty value preserved",
    ),
    (
        "/relative/path?foo=bar",
        {"foo": "bar"},
        "relative URL",
    ),
]
# fmt: on


@pytest.mark.parametrize(
    "url,expected,desc",
    _EXTRACT_CASES,
    ids=[c[2] for c in _EXTRACT_CASES],
)
def test_extract_query_params(url: str, expected: dict[str, str], desc: str) -> None:
    """Query param extraction from URLs."""
    assert _extract_query_params(url) == expected
