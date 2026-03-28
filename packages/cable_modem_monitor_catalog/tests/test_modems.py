"""Catalog modem tests — schema validation and HAR replay.

Auto-parametrized by conftest.py:
- ``modem_yaml_path``: every modem*.yaml validates through Pydantic
- ``modem_test_case``: HAR + golden file pairs run full orchestrator cycle

No modem-specific test code here. Adding a modem = adding files.
"""

from __future__ import annotations

from pathlib import Path

from solentlabs.cable_modem_monitor_core.config_loader import load_modem_config
from solentlabs.cable_modem_monitor_core.test_harness import (
    ModemTestCase,
    run_modem_test_orchestrated,
)


def test_modem_yaml_schema(modem_yaml_path: Path) -> None:
    """Every modem.yaml in the catalog passes Pydantic schema validation."""
    load_modem_config(modem_yaml_path)


def test_modem_har_replay(modem_test_case: ModemTestCase) -> None:
    """Each modem's HAR replay produces expected output via orchestrator."""
    result = run_modem_test_orchestrated(modem_test_case)
    assert result.passed, (
        f"{result.test_name}: {result.error}" if result.error else f"{result.test_name}: golden file mismatch"
    )
