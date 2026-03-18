"""Tests for Phase 4: HTTP action detection.

Fixture-driven tests for HTTP logout and restart endpoint detection.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.mcp.analysis.actions import detect_actions

from tests.conftest import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "actions" / "http"
HTTP_FIXTURES = collect_fixtures(FIXTURES_DIR)


# =====================================================================
# HTTP action detection - fixture-driven
# =====================================================================


@pytest.mark.parametrize("fixture_path", HTTP_FIXTURES, ids=[f.stem for f in HTTP_FIXTURES])
def test_http_action_presence(fixture_path: Path) -> None:
    """Correct action presence/absence for each HTTP fixture."""
    data = load_fixture(fixture_path)
    result = detect_actions(data["_entries"], "http")
    assert (result.logout is not None) == (data["_expected_logout"] is not None)
    assert (result.restart is not None) == (data["_expected_restart"] is not None)


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in HTTP_FIXTURES if load_fixture(f)["_expected_logout"] is not None],
    ids=[f.stem for f in HTTP_FIXTURES if load_fixture(f)["_expected_logout"] is not None],
)
def test_http_logout_details(fixture_path: Path) -> None:
    """HTTP logout details match fixture expectations."""
    data = load_fixture(fixture_path)
    result = detect_actions(data["_entries"], "http")
    expected = data["_expected_logout"]
    assert result.logout is not None
    assert result.logout.type == expected["type"]
    assert result.logout.method == expected["method"]
    assert result.logout.endpoint == expected["endpoint"]
    if "params" in expected:
        assert result.logout.params == expected["params"]


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in HTTP_FIXTURES if load_fixture(f)["_expected_restart"] is not None],
    ids=[f.stem for f in HTTP_FIXTURES if load_fixture(f)["_expected_restart"] is not None],
)
def test_http_restart_details(fixture_path: Path) -> None:
    """HTTP restart details match fixture expectations."""
    data = load_fixture(fixture_path)
    result = detect_actions(data["_entries"], "http")
    expected = data["_expected_restart"]
    assert result.restart is not None
    assert result.restart.type == expected["type"]
    assert result.restart.method == expected["method"]
    assert result.restart.endpoint == expected["endpoint"]
    if "params" in expected:
        assert result.restart.params == expected["params"]
