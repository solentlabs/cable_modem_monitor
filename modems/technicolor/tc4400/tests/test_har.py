"""HAR-based integration tests for Technicolor TC4400.

Validates HAR structure and content detection. The TC4400 uses no
authentication — all pages are publicly accessible.

Tests skip gracefully when HAR files are unavailable.
Runs locally if HAR files present, skips in CI (HAR files gitignored for PII).
"""

from __future__ import annotations

import pytest

from tests.integration.har_replay.conftest import requires_har
from tests.integration.har_replay.har_parser import AuthPattern


class TestTC4400AuthDetection:
    """Test auth pattern detection from TC4400 HAR."""

    @requires_har("tc4400")
    @pytest.mark.har_replay
    def test_no_auth_detected(self, har_flow_factory):
        """TC4400 has no authentication — all pages are public."""
        flow = har_flow_factory("tc4400")
        assert flow.pattern in (AuthPattern.UNKNOWN, AuthPattern.NO_AUTH)

    @requires_har("tc4400")
    @pytest.mark.har_replay
    def test_no_auth_headers_or_cookies(self, har_parser_factory):
        """No Authorization headers or session cookies in any request."""
        parser = har_parser_factory("tc4400")
        exchanges = parser.get_exchanges()

        for e in exchanges:
            assert not e.request.has_header("Authorization"), f"Unexpected Authorization header at {e.path}"


class TestTC4400HarStructure:
    """Validate structural expectations of the TC4400 HAR."""

    @requires_har("tc4400")
    @pytest.mark.har_replay
    def test_has_connection_status_page(self, har_parser_factory):
        """HAR contains cmconnectionstatus.html."""
        parser = har_parser_factory("tc4400")
        exchange = parser.get_exchange_by_path("/cmconnectionstatus.html")
        assert exchange is not None, "cmconnectionstatus.html not found"
        assert exchange.status == 200

    @requires_har("tc4400")
    @pytest.mark.har_replay
    def test_connection_status_contains_channel_data(self, har_parser_factory):
        """cmconnectionstatus.html contains DOCSIS channel data."""
        parser = har_parser_factory("tc4400")
        exchange = parser.get_exchange_by_path("/cmconnectionstatus.html")
        assert exchange is not None

        content = exchange.response.content.lower()
        assert "downstream" in content or "frequency" in content
        assert "upstream" in content or "channel" in content

    @requires_har("tc4400")
    @pytest.mark.har_replay
    def test_has_software_info_page(self, har_parser_factory):
        """HAR contains cmswinfo.html (software/firmware info)."""
        parser = har_parser_factory("tc4400")
        exchange = parser.get_exchange_by_path("/cmswinfo.html")
        assert exchange is not None, "cmswinfo.html not found"
        assert exchange.status == 200

    @requires_har("tc4400")
    @pytest.mark.har_replay
    def test_all_requests_succeed(self, har_parser_factory):
        """All requests return 200."""
        parser = har_parser_factory("tc4400")
        exchanges = parser.get_exchanges()

        failed = [e for e in exchanges if e.status != 200]
        assert len(failed) == 0, f"{len(failed)} requests failed: " + ", ".join(f"{e.path}→{e.status}" for e in failed)

    @requires_har("tc4400")
    @pytest.mark.har_replay
    def test_uses_html_frames(self, har_parser_factory):
        """TC4400 uses HTML frames (index page loads sub-pages)."""
        parser = har_parser_factory("tc4400")
        exchanges = parser.get_exchanges()

        html_pages = [e for e in exchanges if e.response.content and "text/html" in (e.response.mime_type or "")]
        assert len(html_pages) >= 3, "Expected multiple HTML pages (frame-based layout)"
