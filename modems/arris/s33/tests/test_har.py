"""HAR-based integration tests for Arris S33.

These tests use HAR captures to validate auth detection, auth flow,
and parser integration. Tests skip gracefully when HAR files are unavailable.

Runs locally if HAR files present, skips in CI (HAR files gitignored for PII).
"""

from __future__ import annotations

import pytest

from tests.integration.har_replay.conftest import requires_har
from tests.integration.har_replay.har_parser import AuthPattern


class TestS33AuthDetection:
    """Test auth pattern detection from S33 HAR."""

    @requires_har("s33")
    @pytest.mark.har_replay
    def test_detects_hnap_session(self, har_flow_factory):
        """S33 uses HNAP_SESSION authentication."""
        flow = har_flow_factory("s33")
        assert flow.pattern == AuthPattern.HNAP_SESSION
        assert len(flow.soap_actions) > 0
        assert flow.hnap_endpoint is not None


class TestS33AuthFlow:
    """Test HNAP auth flow details from S33 HAR."""

    @requires_har("s33")
    @pytest.mark.har_replay
    def test_hnap_endpoint(self, har_flow_factory):
        """S33 HNAP endpoint is /HNAP1."""
        flow = har_flow_factory("s33")
        assert flow.hnap_endpoint is not None
        assert "HNAP" in flow.hnap_endpoint.upper()

    @requires_har("s33")
    @pytest.mark.har_replay
    def test_soap_actions_use_hnap(self, har_flow_factory):
        """S33 HNAP uses HNAP1 SOAPActions."""
        flow = har_flow_factory("s33")
        assert len(flow.soap_actions) > 0
        soap_actions_upper = [a.upper() for a in flow.soap_actions]
        assert any("HNAP" in a for a in soap_actions_upper)

    @requires_har("s33")
    @pytest.mark.har_replay
    def test_full_auth_flow_extraction(self, har_parser_factory):
        """Extract complete S33 auth flow."""
        parser = har_parser_factory("s33")
        flow = parser.extract_auth_flow()

        assert len(flow.exchanges) > 0
        assert flow.pattern == AuthPattern.HNAP_SESSION
        assert flow.hnap_endpoint is not None
        assert len(flow.soap_actions) > 0


class TestS33ParserIntegration:
    """Test S33 HNAP parser against HAR-mocked responses."""

    @requires_har("s33")
    @pytest.mark.har_replay
    def test_har_contains_hnap_response(self, har_parser_factory):
        """Verify S33 HAR contains HNAP responses."""
        parser = har_parser_factory("s33")
        exchanges = parser.get_exchanges()

        hnap_exchanges = [e for e in exchanges if "HNAP" in e.url.upper()]
        assert len(hnap_exchanges) > 0

        successful = [e for e in hnap_exchanges if e.status == 200]
        assert len(successful) > 0

    @requires_har("s33")
    @pytest.mark.har_replay
    def test_hnap_response_is_json_or_xml(self, har_parser_factory):
        """S33 HNAP responses should be JSON or XML."""
        parser = har_parser_factory("s33")
        exchanges = parser.get_exchanges()

        hnap_posts = [e for e in exchanges if "HNAP" in e.url.upper() and e.method == "POST" and e.response.content]

        if not hnap_posts:
            pytest.skip("No HNAP POST with response in HAR")

        hnap = hnap_posts[0]
        content = hnap.response.content.strip()

        is_json = content.startswith("{") or content.startswith("[")
        is_xml = content.startswith("<")
        assert is_json or is_xml, f"Unexpected content format: {content[:100]}"


class TestS33HarStructure:
    """Test HAR exchange structure for S33."""

    @requires_har("s33")
    @pytest.mark.har_replay
    def test_hnap_exchanges_have_soap_action(self, har_parser_factory):
        """HNAP exchanges should have SOAPAction headers."""
        parser = har_parser_factory("s33")
        auth_exchanges = parser.get_auth_exchanges()

        soap_exchanges = [e for e in auth_exchanges if e.request.has_header("SOAPAction")]
        assert len(soap_exchanges) > 0

    @requires_har("s33")
    @pytest.mark.har_replay
    def test_hnap_request_has_soap_header(self, har_parser_factory):
        """S33 HNAP requests include SOAPAction header."""
        parser = har_parser_factory("s33")
        auth_exchanges = parser.get_auth_exchanges()

        hnap_exchanges = [e for e in auth_exchanges if e.request.has_header("SOAPAction")]
        assert len(hnap_exchanges) > 0

        hnap = hnap_exchanges[0]
        assert hnap.method == "POST"
        assert hnap.request.mime_type is not None

    @requires_har("s33")
    @pytest.mark.har_replay
    def test_hnap_post_exchange_structure(self, har_parser_factory):
        """Validate HNAP POST exchange has expected structure."""
        parser = har_parser_factory("s33")
        auth_exchanges = parser.get_auth_exchanges()

        hnap_posts = [e for e in auth_exchanges if e.request.has_header("SOAPAction")]
        assert len(hnap_posts) > 0

        hnap = hnap_posts[0]
        assert hnap.method == "POST"
        assert hnap.request.post_data is not None

        content = hnap.request.post_data
        is_xml = content.strip().startswith("<")
        is_json = content.strip().startswith("{")
        assert is_xml or is_json
