"""HAR-based integration tests for Arris G54.

These tests use HAR captures to validate auth detection, auth flow,
and parser integration. Tests skip gracefully when HAR files are unavailable.

Runs locally if HAR files present, skips in CI (HAR files gitignored for PII).
"""

from __future__ import annotations

import pytest

from tests.integration.har_replay.conftest import requires_har
from tests.integration.har_replay.har_parser import AuthPattern


class TestG54AuthDetection:
    """Test auth pattern detection from G54 HAR."""

    @requires_har("g54")
    @pytest.mark.har_replay
    def test_detects_form_plain(self, har_flow_factory):
        """G54 uses FORM_PLAIN authentication."""
        flow = har_flow_factory("g54")
        assert flow.pattern == AuthPattern.FORM_PLAIN


class TestG54AuthFlow:
    """Test form auth flow details from G54 HAR."""

    @requires_har("g54")
    @pytest.mark.har_replay
    def test_form_fields(self, har_parser_factory):
        """G54 form auth details can be extracted."""
        parser = har_parser_factory("g54")
        flow = parser.extract_auth_flow()

        assert flow.pattern == AuthPattern.FORM_PLAIN
        assert flow.login_url is not None


class TestG54ParserIntegration:
    """Test G54 parser against HAR-mocked responses."""

    @requires_har("g54")
    @pytest.mark.har_replay
    def test_har_contains_login_page(self, har_parser_factory):
        """Verify G54 HAR contains login or status page."""
        parser = har_parser_factory("g54")
        exchanges = parser.get_exchanges()

        # G54 uses luci web interface
        luci_exchanges = [e for e in exchanges if "luci" in e.url.lower()]

        if luci_exchanges:
            successful = [e for e in luci_exchanges if e.status == 200]
            assert len(successful) > 0
        else:
            # HAR might just have root page
            assert len(exchanges) > 0
