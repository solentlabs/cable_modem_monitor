"""Tests for Phase 4: HNAP action detection.

Fixture-driven tests for HNAP SOAP action scanning.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.mcp.analysis.actions import detect_actions

from tests.conftest import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "actions" / "hnap"
HNAP_FIXTURES = collect_fixtures(FIXTURES_DIR)


# =====================================================================
# HNAP action detection - fixture-driven
# =====================================================================


@pytest.mark.parametrize("fixture_path", HNAP_FIXTURES, ids=[f.stem for f in HNAP_FIXTURES])
def test_hnap_action_presence(fixture_path: Path) -> None:
    """Correct action presence/absence for each HNAP fixture."""
    data = load_fixture(fixture_path)
    result = detect_actions(data["_entries"], "hnap")
    assert (result.logout is not None) == (data["_expected_logout"] is not None)
    assert (result.restart is not None) == (data["_expected_restart"] is not None)


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in HNAP_FIXTURES if load_fixture(f)["_expected_logout"] is not None],
    ids=[f.stem for f in HNAP_FIXTURES if load_fixture(f)["_expected_logout"] is not None],
)
def test_hnap_logout_details(fixture_path: Path) -> None:
    """HNAP logout details match fixture expectations."""
    data = load_fixture(fixture_path)
    result = detect_actions(data["_entries"], "hnap")
    expected = data["_expected_logout"]
    assert result.logout is not None
    assert result.logout.type == expected["type"]
    assert result.logout.method == expected["method"]
    assert result.logout.endpoint == expected["endpoint"]
    if "action_name" in expected:
        assert result.logout.action_name == expected["action_name"]
    if "credential_params" in expected:
        assert result.logout.credential_params == expected["credential_params"]


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in HNAP_FIXTURES if load_fixture(f)["_expected_restart"] is not None],
    ids=[f.stem for f in HNAP_FIXTURES if load_fixture(f)["_expected_restart"] is not None],
)
def test_hnap_restart_details(fixture_path: Path) -> None:
    """HNAP restart details match fixture expectations."""
    data = load_fixture(fixture_path)
    result = detect_actions(data["_entries"], "hnap")
    expected = data["_expected_restart"]
    assert result.restart is not None
    assert result.restart.type == expected["type"]
    assert result.restart.method == expected["method"]
    assert result.restart.endpoint == expected["endpoint"]
    if "action_name" in expected:
        assert result.restart.action_name == expected["action_name"]
    if "params" in expected:
        assert result.restart.params == expected["params"]
    if "credential_params" in expected:
        assert result.restart.credential_params == expected["credential_params"]
