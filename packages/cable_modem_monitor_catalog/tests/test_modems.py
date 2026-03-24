"""Catalog modem tests — config validation and HAR replay.

Auto-parametrized by conftest.py via Core's ``discover_modem_tests``.
Each modem directory with a HAR + golden file becomes a test case.

Uses the orchestrated path — ``run_modem_test_orchestrated`` — which
exercises the full poll cycle through ``Orchestrator.get_modem_data()``:
session lifecycle, logout, signal classification, status derivation,
and golden file comparison.

No modem-specific test code here. Adding a modem = adding files.
"""

from __future__ import annotations

from solentlabs.cable_modem_monitor_core.test_harness import (
    ModemTestCase,
    run_modem_test_orchestrated,
)


def test_modem_har_replay(modem_test_case: ModemTestCase) -> None:
    """Each modem's HAR replay produces expected output via orchestrator."""
    result = run_modem_test_orchestrated(modem_test_case)
    assert result.passed, (
        f"{result.test_name}: {result.error}" if result.error else f"{result.test_name}: golden file mismatch"
    )
