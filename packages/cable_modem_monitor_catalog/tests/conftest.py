"""Catalog test configuration — auto-discover modem test cases.

Uses Core's ``discover_modem_tests`` to walk the catalog's modem
directory tree and parametrize tests from HAR + golden file pairs.
Enables socket access for HAR mock server replay.

Adding a modem = adding files to its directory. No test code changes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.testing import discover_modem_tests

# Catalog modems root: solentlabs/cable_modem_monitor_catalog/modems/
CATALOG_MODEMS_PATH = Path(__file__).parent.parent / "solentlabs" / "cable_modem_monitor_catalog" / "modems"


@pytest.fixture(autouse=True)
def _allow_sockets(socket_enabled: None) -> None:  # noqa: ARG001
    """Enable sockets for HAR mock server replay.

    The ``socket_enabled`` fixture is provided by pytest-socket
    and re-enables socket operations for the test.
    """


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize tests from modem directory discovery."""
    if "modem_test_case" in metafunc.fixturenames:
        cases = discover_modem_tests(CATALOG_MODEMS_PATH)
        metafunc.parametrize("modem_test_case", cases, ids=lambda c: c.name)
