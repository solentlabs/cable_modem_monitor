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


class TestMB8611AuthFlow:
    """Test HNAP auth flow details from MB8611 HAR."""

    @requires_har("mb8611")
    @pytest.mark.har_replay
    def test_hnap_endpoint(self, har_flow_factory):
        """MB8611 HNAP endpoint is /HNAP1."""
        flow = har_flow_factory("mb8611")
        assert flow.hnap_endpoint is not None
        assert "HNAP" in flow.hnap_endpoint.upper()

    @requires_har("mb8611")
    @pytest.mark.har_replay
    def test_soap_actions_include_login(self, har_flow_factory):
        """MB8611 HNAP includes Login action."""
        flow = har_flow_factory("mb8611")
        assert len(flow.soap_actions) > 0
        soap_actions_upper = [a.upper() for a in flow.soap_actions]
        assert any("LOGIN" in a for a in soap_actions_upper)


class TestMB8611HnapResponseFormat:
    """Test HNAP response format - regression guard for issue #102.

    HNAP modems return JSON/XML responses from API calls, not HTML pages.
    The discovery pipeline must handle html=None for HNAP auth.

    Note: MB8611 firmware returns JSON with incorrect Content-type: text/html
    header, so we must check actual content, not MIME type.
    """

    @requires_har("mb8611")
    @pytest.mark.har_replay
    def test_hnap_responses_contain_json(self, har_parser_factory):
        """HNAP POST responses contain JSON data (despite MIME type lies).

        MB8611 firmware incorrectly reports Content-type: text/html for JSON.
        We check the actual content format, not the MIME type header.

        This is critical: HNAP auth returns JSON via API, not scrapeable HTML,
        so discovery pipeline must skip HTML-based validation for HNAP modems.

        Regression test for issue #102 - AssertionError on html=None.
        """
        parser = har_parser_factory("mb8611")
        exchanges = parser.get_exchanges()

        # Find HNAP POST exchanges (auth and data requests)
        hnap_posts = [e for e in exchanges if "HNAP" in e.url.upper() and e.method == "POST" and e.response.content]

        if not hnap_posts:
            pytest.skip("No HNAP POST with response in HAR")

        # All HNAP responses should have JSON content (starts with { or [)
        # Note: MIME type may lie (text/html) but content is JSON
        for exchange in hnap_posts:
            content = exchange.response.content.strip()
            is_json_content = content.startswith("{") or content.startswith("[")
            is_xml_content = content.startswith("<")

            assert is_json_content or is_xml_content, (
                f"HNAP response should be JSON/XML content: {exchange.url}\n" f"Content starts with: {content[:50]}"
            )

            # Verify it's NOT parseable HTML (no DOCTYPE, html tags, etc.)
            content_lower = content.lower()
            assert "<!doctype" not in content_lower, f"HNAP response should not be HTML: {exchange.url}"
            assert "<html" not in content_lower, f"HNAP response should not contain <html>: {exchange.url}"

    @requires_har("mb8611")
    @pytest.mark.har_replay
    def test_hnap_login_response_is_json(self, har_parser_factory):
        """HNAP Login response is JSON with LoginResponse structure.

        Validates that auth response is machine-readable JSON, not an
        HTML page that could be scraped for parser detection.
        """
        parser = har_parser_factory("mb8611")
        exchanges = parser.get_exchanges()

        # Find the Login HNAP request
        login_exchange = None
        for e in exchanges:
            soap_action = e.request.get_header("SOAPAction") or ""
            if "Login" in soap_action and e.response.content:
                login_exchange = e
                break

        if login_exchange is None:
            pytest.skip("No HNAP Login request found in HAR")

        # Login response should be JSON with LoginResponse key
        content = login_exchange.response.content.strip()
        assert content.startswith("{"), "Login response should be JSON"
        assert "LoginResponse" in content, "Login response should contain LoginResponse"
        assert "LoginResult" in content, "Login response should contain LoginResult"

        # Explicitly NOT HTML
        assert "<html" not in content.lower(), "Login response should not be HTML"
