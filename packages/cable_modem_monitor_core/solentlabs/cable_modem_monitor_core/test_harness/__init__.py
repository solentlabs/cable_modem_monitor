"""Test harness — HAR replay server, golden file comparison, and pipeline runner.

Two use cases share the same ``HARMockServer`` component:

1. **Automated catalog regression testing** — ``run_modem_test()`` /
   ``run_modem_test_orchestrated()`` start an ephemeral server per test,
   run the pipeline, and compare output against golden files.

2. **Manual integration testing** — ``python -m solentlabs.cable_modem_monitor_core.test_harness``
   starts a persistent server for testing against a real HA instance.

See ONBOARDING_SPEC.md Test Harness section.

Public API for Catalog's pytest integration::

    from solentlabs.cable_modem_monitor_core.test_harness import (
        discover_modem_tests,
        run_modem_test,
        run_modem_test_orchestrated,
    )
"""

from __future__ import annotations

from .discovery import ModemTestCase, discover_modem_tests
from .golden_file import ComparisonResult, compare_golden_file
from .loader import ServerConfig, load_server_from_modem_dir
from .runner import TestResult, run_modem_test, run_modem_test_orchestrated
from .server import HARMockServer

__all__ = [
    "ComparisonResult",
    "HARMockServer",
    "ModemTestCase",
    "ServerConfig",
    "TestResult",
    "compare_golden_file",
    "discover_modem_tests",
    "load_server_from_modem_dir",
    "run_modem_test",
    "run_modem_test_orchestrated",
]
