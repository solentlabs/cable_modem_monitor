"""HAR-based integration tests for Arris SB6190.

These tests use HAR captures to validate auth detection, auth flow,
and parser integration. Tests skip gracefully when HAR files are unavailable.

Runs locally if HAR files present, skips in CI (HAR files gitignored for PII).
"""

from __future__ import annotations

import pytest

from tests.integration.har_replay.conftest import requires_har
from tests.integration.har_replay.har_parser import AuthPattern


class TestSB6190AuthDetection:
    """Test auth pattern detection from SB6190 HAR."""

    @requires_har("sb6190")
    @pytest.mark.har_replay
    def test_detects_url_token(self, har_flow_factory):
        """SB6190 HAR triggers URL_TOKEN detection (false positive from URL pattern).

        The actual modem uses BASIC_HTTP auth, but the HAR contains URLs that
        match URL_TOKEN patterns (e.g., login_ prefix), causing misdetection.
        """
        flow = har_flow_factory("sb6190")
        # HAR triggers URL_TOKEN detection due to URL patterns
        assert flow.pattern == AuthPattern.URL_TOKEN_SESSION
