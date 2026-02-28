"""HAR-based integration tests for Arris S33v2.

Validates that the S33v2 HAR capture contains the expected HNAP auth flow,
HMAC-MD5 algorithm, and channel data format. Confirms S33v2 compatibility
with the existing S33 parser.

The S33v2 HAR is a separate file (s33v2.har) alongside the original S33
modem.har. Since the HAR replay factory defaults to modem.har, these tests
use HarParser directly with the s33v2.har path.

Related: Issue #117 (@mmiller7).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.integration.har_replay.har_parser import AuthPattern, HarParser

S33V2_HAR = Path(__file__).parent.parent / "har" / "s33v2.har"

requires_s33v2_har = pytest.mark.skipif(
    not S33V2_HAR.exists(),
    reason="S33v2 HAR file not available",
)


def _get_parser() -> HarParser:
    """Load the S33v2 HAR parser."""
    return HarParser(S33V2_HAR)


@pytest.mark.har_replay
class TestS33v2AuthDetection:
    """Test auth pattern detection from S33v2 HAR."""

    @requires_s33v2_har
    def test_detects_hnap_session(self):
        """S33v2 uses HNAP_SESSION authentication (same as S33)."""
        parser = _get_parser()
        flow = parser.extract_auth_flow()
        assert flow.pattern == AuthPattern.HNAP_SESSION

    @requires_s33v2_har
    def test_hnap_endpoint_detected(self):
        """HNAP endpoint is /HNAP1/."""
        parser = _get_parser()
        flow = parser.extract_auth_flow()
        assert flow.hnap_endpoint is not None
        assert "HNAP" in flow.hnap_endpoint.upper()

    @requires_s33v2_har
    def test_login_soap_action_present(self):
        """Login SOAPAction is in the auth flow."""
        parser = _get_parser()
        flow = parser.extract_auth_flow()
        assert any("Login" in a for a in flow.soap_actions)

    @requires_s33v2_har
    def test_soap_actions_use_purenetworks_namespace(self):
        """SOAPActions use the purenetworks.com/HNAP1 namespace."""
        parser = _get_parser()
        flow = parser.extract_auth_flow()
        assert any("purenetworks.com/HNAP1" in a for a in flow.soap_actions)


@pytest.mark.har_replay
class TestS33v2HmacAlgorithm:
    """Confirm S33v2 uses HMAC-MD5 (same as S33, unlike S33v3 which uses SHA256)."""

    @requires_s33v2_har
    def test_hnap_auth_hash_is_md5_length(self):
        """HNAP_AUTH hash is 32 hex chars (MD5), not 64 (SHA256)."""
        parser = _get_parser()
        exchanges = parser.get_exchanges()

        hnap_posts = [e for e in exchanges if e.request.has_header("HNAP_AUTH")]
        assert len(hnap_posts) > 0, "No HNAP_AUTH headers found"

        for e in hnap_posts:
            hnap_auth = e.request.get_header("HNAP_AUTH")
            # Format: "<32-hex-hash> <timestamp>"
            parts = hnap_auth.split(" ", 1)
            hash_part = parts[0]
            assert len(hash_part) == 32, f"Expected 32-char MD5 hash, got {len(hash_part)}: {hash_part}"
            assert re.match(r"^[0-9A-Fa-f]{32}$", hash_part), f"Not a valid hex hash: {hash_part}"

    @requires_s33v2_har
    def test_hmac_md5_js_loaded(self):
        """S33v2 loads hmac_md5.js (not hmac_sha256.js)."""
        parser = _get_parser()
        exchanges = parser.get_exchanges()

        js_urls = [e.url for e in exchanges if e.url.endswith(".js") or ".js?" in e.url]
        md5_loaded = any("hmac_md5" in url for url in js_urls)
        sha256_loaded = any("hmac_sha256" in url for url in js_urls)

        assert md5_loaded, "hmac_md5.js not found in loaded scripts"
        assert not sha256_loaded, "hmac_sha256.js should NOT be loaded for S33v2"

    @requires_s33v2_har
    def test_hnap_js_uses_hex_hmac_md5(self):
        """hnap.js references hex_hmac_md5 function."""
        parser = _get_parser()
        exchanges = parser.get_exchanges()

        hnap_js = [e for e in exchanges if "hnap.js" in e.url and e.response.content]
        assert len(hnap_js) > 0, "hnap.js not found in HAR"

        content = hnap_js[0].response.content
        assert "hex_hmac_md5" in content, "hnap.js should reference hex_hmac_md5"


@pytest.mark.har_replay
class TestS33v2HarStructure:
    """Validate structural expectations of the S33v2 HAR capture."""

    @requires_s33v2_har
    def test_pre_auth_to_post_auth_flow(self):
        """HAR contains pre-auth (no uid cookie) followed by post-auth (uid cookie)."""
        parser = _get_parser()
        exchanges = parser.get_exchanges()

        pre_auth = [e for e in exchanges if not e.request.cookies.get("uid")]
        post_auth = [e for e in exchanges if e.request.cookies.get("uid")]

        assert len(pre_auth) > 0, "No pre-auth exchanges found"
        assert len(post_auth) > 0, "No post-auth exchanges found"

        # Pre-auth should come before post-auth
        last_pre = max(e.index for e in pre_auth)
        first_post = min(e.index for e in post_auth)
        assert last_pre < first_post or any(
            e.index < first_post for e in pre_auth
        ), "Pre-auth exchanges should precede post-auth"

    @requires_s33v2_har
    def test_login_response_contains_challenge(self):
        """Login response includes Challenge, Cookie, PublicKey, and LoginResult."""
        parser = _get_parser()
        exchanges = parser.get_exchanges()

        login_posts = [
            e
            for e in exchanges
            if e.method == "POST"
            and e.request.has_header("SOAPAction")
            and "Login" in (e.request.get_header("SOAPAction") or "")
        ]
        assert len(login_posts) > 0, "No Login SOAPAction found"

        login_response = login_posts[0].response.content
        for field in ["Challenge", "Cookie", "PublicKey", "LoginResult"]:
            assert field in login_response, f"Login response missing {field}"

    @requires_s33v2_har
    def test_uid_cookie_appears_after_login(self):
        """uid cookie appears in requests after the Login SOAPAction."""
        parser = _get_parser()
        exchanges = parser.get_exchanges()

        login_index = None
        for e in exchanges:
            if (
                e.method == "POST"
                and e.request.has_header("SOAPAction")
                and "Login" in (e.request.get_header("SOAPAction") or "")
            ):
                login_index = e.index
                break

        assert login_index is not None, "Login exchange not found"

        post_login = [e for e in exchanges if e.index > login_index]
        assert len(post_login) > 0, "No exchanges after login"

        uid_exchanges = [e for e in post_login if e.request.cookies.get("uid")]
        assert len(uid_exchanges) > 0, "No uid cookie in post-login requests"


@pytest.mark.har_replay
class TestS33v2ParserIntegration:
    """Validate that S33v2 HAR data is parseable by the S33 parser."""

    @requires_s33v2_har
    def test_device_status_identifies_s33v2(self):
        """Device status response identifies model as S33v2."""
        parser = _get_parser()
        exchanges = parser.get_exchanges()

        # Entry 20 is GetArrisDeviceStatus (pre-login public query)
        device_posts = [
            e for e in exchanges if e.method == "POST" and "GetArrisDeviceStatus" in (e.response.content or "")
        ]
        assert len(device_posts) > 0, "No GetArrisDeviceStatus response found"

        content = device_posts[0].response.content
        assert "S33v2" in content, "Device status should identify model as S33v2"

    @requires_s33v2_har
    def test_firmware_prefix_matches_s33(self):
        """S33v2 firmware uses TB01.03.* prefix (same family as S33)."""
        parser = _get_parser()
        exchanges = parser.get_exchanges()

        device_posts = [e for e in exchanges if e.method == "POST" and "FirmwareVersion" in (e.response.content or "")]
        assert len(device_posts) > 0

        content = device_posts[0].response.content
        assert re.search(r"TB01\.03\.\d+", content), "Firmware should match TB01.03.* pattern"

    @requires_s33v2_har
    def test_downstream_channels_use_caret_delimiter(self):
        """Downstream channel data uses ^ field delimiter and |+| row delimiter."""
        parser = _get_parser()
        exchanges = parser.get_exchanges()

        channel_posts = [
            e for e in exchanges if e.method == "POST" and "CustomerConnDownstreamChannel" in (e.response.content or "")
        ]
        assert len(channel_posts) > 0, "No downstream channel data found"

        content = channel_posts[0].response.content
        assert "^" in content, "Missing ^ field delimiter"
        assert "|+|" in content, "Missing |+| row delimiter"

    @requires_s33v2_har
    def test_upstream_channels_present(self):
        """Upstream channel data is present in HAR."""
        parser = _get_parser()
        exchanges = parser.get_exchanges()

        upstream_posts = [
            e for e in exchanges if e.method == "POST" and "CustomerConnUpstreamChannel" in (e.response.content or "")
        ]
        assert len(upstream_posts) > 0, "No upstream channel data found"

    @requires_s33v2_har
    def test_data_posts_are_authenticated(self):
        """Post-login data requests include both HNAP_AUTH and uid cookie."""
        parser = _get_parser()
        exchanges = parser.get_exchanges()

        data_posts = [
            e
            for e in exchanges
            if e.method == "POST"
            and e.request.cookies.get("uid")
            and "GetMultipleHNAPs" in (e.request.get_header("SOAPAction") or "")
        ]
        assert len(data_posts) > 0, "No authenticated data POSTs found"

        for e in data_posts:
            assert e.request.has_header("HNAP_AUTH"), f"Data POST at index {e.index} missing HNAP_AUTH header"
            assert e.request.cookies.get("uid"), f"Data POST at index {e.index} missing uid cookie"
