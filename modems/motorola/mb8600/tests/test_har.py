"""HAR-based integration tests for Motorola MB8600.

Validates HNAP auth detection, HMAC-MD5 algorithm, and response format.
The MB8600 is an HNAP modem in the session reuse blast radius (v3.13.2).

Tests skip gracefully when HAR files are unavailable.
Runs locally if HAR files present, skips in CI (HAR files gitignored for PII).
"""

from __future__ import annotations

import re

import pytest

from tests.integration.har_replay.conftest import requires_har
from tests.integration.har_replay.har_parser import AuthPattern


class TestMB8600AuthDetection:
    """Test auth pattern detection from MB8600 HAR."""

    @requires_har("mb8600")
    @pytest.mark.har_replay
    def test_detects_hnap_session(self, har_flow_factory):
        """MB8600 uses HNAP_SESSION authentication."""
        flow = har_flow_factory("mb8600")
        assert flow.pattern == AuthPattern.HNAP_SESSION
        assert flow.hnap_endpoint is not None
        assert len(flow.soap_actions) > 0

    @requires_har("mb8600")
    @pytest.mark.har_replay
    def test_hnap_endpoint(self, har_flow_factory):
        """MB8600 HNAP endpoint is /HNAP1."""
        flow = har_flow_factory("mb8600")
        assert flow.hnap_endpoint is not None
        assert "HNAP" in flow.hnap_endpoint.upper()

    @requires_har("mb8600")
    @pytest.mark.har_replay
    def test_login_soap_action_present(self, har_flow_factory):
        """Login SOAPAction is in the auth flow."""
        flow = har_flow_factory("mb8600")
        assert any("Login" in a for a in flow.soap_actions)


class TestMB8600HmacAlgorithm:
    """Confirm MB8600 uses HMAC-MD5."""

    @requires_har("mb8600")
    @pytest.mark.har_replay
    def test_hnap_auth_hash_is_md5_length(self, har_parser_factory):
        """HNAP_AUTH hash is 32 hex chars (MD5)."""
        parser = har_parser_factory("mb8600")
        exchanges = parser.get_exchanges()

        hnap_posts = [e for e in exchanges if e.request.has_header("HNAP_AUTH")]
        assert len(hnap_posts) > 0, "No HNAP_AUTH headers found"

        hnap_auth = hnap_posts[0].request.get_header("HNAP_AUTH")
        hash_part = hnap_auth.split(" ", 1)[0]
        assert len(hash_part) == 32, f"Expected 32-char MD5 hash, got {len(hash_part)}"
        assert re.match(r"^[0-9A-Fa-f]{32}$", hash_part)

    @requires_har("mb8600")
    @pytest.mark.har_replay
    def test_hmac_md5_js_loaded(self, har_parser_factory):
        """MB8600 loads hmac_md5.js."""
        parser = har_parser_factory("mb8600")
        exchanges = parser.get_exchanges()

        js_urls = [e.url for e in exchanges if ".js" in e.url]
        assert any("hmac_md5" in url for url in js_urls)


class TestMB8600HarStructure:
    """Validate structural expectations of the MB8600 HAR."""

    @requires_har("mb8600")
    @pytest.mark.har_replay
    def test_pre_auth_to_post_auth_flow(self, har_parser_factory):
        """HAR contains pre-auth followed by post-auth exchanges."""
        parser = har_parser_factory("mb8600")
        exchanges = parser.get_exchanges()

        pre_auth = [e for e in exchanges if not e.request.cookies.get("uid")]
        post_auth = [e for e in exchanges if e.request.cookies.get("uid")]

        assert len(pre_auth) > 0, "No pre-auth exchanges"
        assert len(post_auth) > 0, "No post-auth exchanges"

    @requires_har("mb8600")
    @pytest.mark.har_replay
    def test_login_response_is_json(self, har_parser_factory):
        """Login response is JSON with LoginResponse structure."""
        parser = har_parser_factory("mb8600")
        exchanges = parser.get_exchanges()

        login_posts = [
            e
            for e in exchanges
            if e.method == "POST" and "Login" in (e.request.get_header("SOAPAction") or "") and e.response.content
        ]
        assert len(login_posts) > 0, "No Login SOAPAction found"

        content = login_posts[0].response.content.strip()
        assert content.startswith("{"), "Login response should be JSON"
        assert "LoginResponse" in content
        assert "LoginResult" in content

    @requires_har("mb8600")
    @pytest.mark.har_replay
    def test_uid_cookie_appears_after_login(self, har_parser_factory):
        """uid cookie appears in requests after login."""
        parser = har_parser_factory("mb8600")
        exchanges = parser.get_exchanges()

        login_index = None
        for e in exchanges:
            if e.method == "POST" and "Login" in (e.request.get_header("SOAPAction") or ""):
                login_index = e.index
                break

        assert login_index is not None

        post_login = [e for e in exchanges if e.index > login_index]
        uid_exchanges = [e for e in post_login if e.request.cookies.get("uid")]
        assert len(uid_exchanges) > 0, "No uid cookie after login"
