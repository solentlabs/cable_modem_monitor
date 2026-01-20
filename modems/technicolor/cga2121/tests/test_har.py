"""HAR-based integration tests for Technicolor CGA2121.

These tests use HAR captures to validate auth detection, auth flow,
and parser integration. Tests skip gracefully when HAR files are unavailable.

Runs locally if HAR files present, skips in CI (HAR files gitignored for PII).
"""

from __future__ import annotations

import pytest

from tests.integration.har_replay.conftest import requires_har
from tests.integration.har_replay.har_parser import AuthPattern


class TestCGA2121AuthDetection:
    """Test auth pattern detection from CGA2121 HAR."""

    @requires_har("cga2121")
    @pytest.mark.har_replay
    def test_detects_form_plain(self, har_flow_factory):
        """CGA2121 uses FORM_PLAIN authentication."""
        flow = har_flow_factory("cga2121")
        assert flow.pattern == AuthPattern.FORM_PLAIN
