"""HAR-based integration tests for Motorola MB8611.

These tests use HAR captures to validate auth detection, auth flow,
and parser integration. Tests skip gracefully when HAR files are unavailable.

Runs locally if HAR files present, skips in CI (HAR files gitignored for PII).
"""

from __future__ import annotations

import pytest

from tests.integration.har_replay.conftest import requires_har
from tests.integration.har_replay.har_parser import AuthPattern


class TestMB8611AuthDetection:
    """Test auth pattern detection from MB8611 HAR."""

    @requires_har("mb8611")
    @pytest.mark.har_replay
    def test_detects_hnap_session(self, har_flow_factory):
        """MB8611 uses HNAP_SESSION authentication (like S33)."""
        flow = har_flow_factory("mb8611")

        assert flow.pattern == AuthPattern.HNAP_SESSION
        assert flow.hnap_endpoint is not None
        assert len(flow.soap_actions) > 0
