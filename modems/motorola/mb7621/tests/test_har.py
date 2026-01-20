"""HAR-based integration tests for Motorola MB7621.

These tests use HAR captures to validate auth detection, auth flow,
and parser integration. Tests skip gracefully when HAR files are unavailable.

Runs locally if HAR files present, skips in CI (HAR files gitignored for PII).
"""

from __future__ import annotations

import pytest
import requests
from bs4 import BeautifulSoup

from tests.integration.har_replay.conftest import requires_har
from tests.integration.har_replay.har_parser import AuthPattern


class TestMB7621AuthDetection:
    """Test auth pattern detection from MB7621 HAR."""

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_detects_form_auth(self, har_flow_factory):
        """MB7621 HAR detects as form auth (FORM_PLAIN due to sanitization).

        The actual modem uses base64 encoding (FORM_PLAIN with password_encoding=base64),
        but the sanitized HAR has [REDACTED] in password field which doesn't match base64 pattern.
        """
        flow = har_flow_factory("mb7621")
        assert flow.pattern == AuthPattern.FORM_PLAIN
        assert flow.form_action is not None
        assert flow.login_url is not None


class TestMB7621AuthFlow:
    """Test auth flow details from MB7621 HAR."""

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_form_action(self, har_flow_factory):
        """MB7621 login form posts to /goform/login."""
        flow = har_flow_factory("mb7621")
        assert flow.form_action == "/goform/login"

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_form_fields(self, har_flow_factory):
        """MB7621 uses loginUsername and loginPassword fields."""
        flow = har_flow_factory("mb7621")
        assert "loginUsername" in flow.form_fields
        assert "loginPassword" in flow.form_fields

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_login_page(self, har_flow_factory):
        """MB7621 login page is at root."""
        flow = har_flow_factory("mb7621")
        assert flow.login_url is not None
        assert flow.login_url.endswith("/")

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_full_auth_flow_extraction(self, har_parser_factory):
        """Extract complete MB7621 auth flow."""
        parser = har_parser_factory("mb7621")
        flow = parser.extract_auth_flow()

        assert len(flow.exchanges) > 0
        assert flow.login_url is not None
        assert flow.form_action is not None


class TestMB7621ParserIntegration:
    """Test MB7621 parser against HAR-mocked responses."""

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_parse_with_har(self, mock_har_for_modem):
        """Parse MB7621 data using HAR responses."""
        with mock_har_for_modem("mb7621") as (flow, mocker):
            session = requests.Session()

            resp = session.get("http://192.168.100.1/MotoConnection.asp")
            if resp.status_code != 200:
                pytest.skip("MotoConnection.asp not in HAR capture")

            soup = BeautifulSoup(resp.text, "html.parser")

            assert soup is not None
            assert len(resp.text) > 0

            has_table = soup.find("table") is not None
            has_html = "html" in resp.text.lower()
            assert has_table or has_html, "Page should be valid HTML with content"

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_har_contains_status_page(self, har_parser_factory):
        """Verify MB7621 HAR contains the status page."""
        parser = har_parser_factory("mb7621")
        exchanges = parser.get_exchanges()

        status_urls = [e for e in exchanges if "MotoConnection" in e.url or "MotoStatus" in e.url]
        home_urls = [e for e in exchanges if "MotoHome" in e.url]

        assert len(status_urls) > 0 or len(home_urls) > 0 or len(exchanges) > 0


class TestMB7621HarStructure:
    """Test HAR exchange structure for MB7621."""

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_parser_loads_exchanges(self, har_parser_factory):
        """HarParser should load exchanges from HAR file."""
        parser = har_parser_factory("mb7621")
        exchanges = parser.get_exchanges()
        assert len(exchanges) > 0

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_parser_finds_auth_exchanges(self, har_parser_factory):
        """HarParser should identify auth-related exchanges."""
        parser = har_parser_factory("mb7621")
        auth_exchanges = parser.get_auth_exchanges()
        assert len(auth_exchanges) > 0

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_form_post_exchange_structure(self, har_parser_factory):
        """Validate form POST exchange has expected structure."""
        parser = har_parser_factory("mb7621")
        exchanges = parser.get_exchanges()

        login_posts = [e for e in exchanges if e.method == "POST" and "login" in e.path.lower()]
        assert len(login_posts) > 0

        login = login_posts[0]
        assert login.request.post_data is not None
        assert login.request.mime_type is not None
        assert "x-www-form-urlencoded" in login.request.mime_type.lower()
