"""Test harness for modem onboarding.

HAR mock server, golden file comparison, test discovery, and
pipeline runner. See ONBOARDING_SPEC.md Test Harness section.

Public API for Catalog's pytest integration::

    from solentlabs.cable_modem_monitor_core.testing import (
        discover_modem_tests,
        run_modem_test,
    )
"""

from __future__ import annotations

from .discovery import ModemTestCase, discover_modem_tests
from .golden_file import ComparisonResult, compare_golden_file
from .har_mock_server import HARMockServer
from .runner import TestResult, run_modem_test

__all__ = [
    "ComparisonResult",
    "HARMockServer",
    "ModemTestCase",
    "TestResult",
    "compare_golden_file",
    "discover_modem_tests",
    "run_modem_test",
]
