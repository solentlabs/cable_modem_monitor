"""Test harness for modem onboarding.

HAR mock server, golden file comparison, and test discovery.
See ONBOARDING_SPEC.md Test Harness section.
"""

from __future__ import annotations

from .golden_file import ComparisonResult, compare_golden_file
from .har_mock_server import HARMockServer

__all__ = [
    "ComparisonResult",
    "HARMockServer",
    "compare_golden_file",
]
