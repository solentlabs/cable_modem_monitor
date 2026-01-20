"""HAR-based integration tests for Arris SB8200.

These tests use HAR captures to validate auth detection, auth flow,
and parser integration. Tests skip gracefully when HAR files are unavailable.

Runs locally if HAR files present, skips in CI (HAR files gitignored for PII).
"""

from __future__ import annotations

import pytest

from tests.integration.har_replay.conftest import requires_har
from tests.integration.har_replay.har_parser import AuthPattern


class TestSB8200AuthDetection:
    """Test auth pattern detection from SB8200 HAR."""

    @requires_har("sb8200")
    @pytest.mark.har_replay
    def test_detects_url_token(self, har_flow_factory):
        """SB8200 uses URL_TOKEN_SESSION authentication."""
        flow = har_flow_factory("sb8200")
        assert flow.pattern == AuthPattern.URL_TOKEN_SESSION


class TestSB8200AuthFlow:
    """Test URL token auth flow details from SB8200 HAR."""

    @requires_har("sb8200")
    @pytest.mark.har_replay
    def test_token_in_urls(self, har_parser_factory):
        """SB8200 includes tokens in URL paths."""
        parser = har_parser_factory("sb8200")
        exchanges = parser.get_exchanges()

        # Check for ct_ prefixed URLs (credential token) or login_ URLs
        ct_urls = [e for e in exchanges if "ct_" in e.url]
        login_urls = [e for e in exchanges if "login_" in e.url]
        assert len(ct_urls) > 0 or len(login_urls) > 0
