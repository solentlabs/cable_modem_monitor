"""Catalog modem tests — config validation and HAR replay.

Auto-parametrized by conftest.py via Core's ``discover_modem_tests``.
Each modem directory with a HAR + golden file becomes a test case.

No modem-specific test code here. Adding a modem = adding files.
"""

from __future__ import annotations

from solentlabs.cable_modem_monitor_core.testing import (
    ModemTestCase,
    run_modem_test,
)


def test_modem_har_replay(modem_test_case: ModemTestCase) -> None:
    """Each modem's HAR replay produces expected output."""
    result = run_modem_test(modem_test_case)
    assert result.passed, (
        f"{result.test_name}: {result.error}" if result.error else f"{result.test_name}: golden file mismatch"
    )
