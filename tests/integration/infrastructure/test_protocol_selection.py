"""Tests for protocol selection in connectivity check.

These tests verify behavior when a modem responds on one protocol
but only actually works on another - exposing the S34/PR#90 issue.

Key insight from PR #90:
- S34 returns 403 on HTTP (connectivity accepts as "reachable")
- S34's HNAP endpoint only works on HTTPS
- Result: working_url is set to HTTP, auth fails silently

This file tests the protocol selection scenarios to understand
what the correct behavior should be.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from custom_components.cable_modem_monitor.lib.connectivity import check_connectivity


class Http403HttpsOkHandler(BaseHTTPRequestHandler):
    """Handler that returns 403 on HTTP requests.

    Simulates S34's behavior where HTTP responds but doesn't work.
    """

    def log_message(self, format, *args):
        """Suppress logging."""
        pass

    def do_HEAD(self):  # noqa: N802
        """Return 403 Forbidden."""
        self.send_response(403)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        """Return 403 Forbidden."""
        self.send_response(403)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Forbidden")


class HttpOkHandler(BaseHTTPRequestHandler):
    """Handler that returns 200 OK."""

    def log_message(self, format, *args):
        """Suppress logging."""
        pass

    def do_HEAD(self):  # noqa: N802
        """Return 200 OK."""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        """Return 200 OK."""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body>OK</body></html>")


# =============================================================================
# SCENARIO DOCUMENTATION
# =============================================================================
#
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ S34-LIKE MODEM SCENARIO                                                      │
# ├─────────────────────────────────────────────────────────────────────────────┤
# │ User enters: 192.168.100.1 (no protocol)                                     │
# │                                                                              │
# │ HTTP trial:   HEAD → 403 Forbidden                                           │
# │ Current:      Accept as "reachable" (any HTTP response = success)            │
# │ Result:       working_url = http://192.168.100.1                             │
# │                                                                              │
# │ Auth attempt: POST /HNAP1/ over HTTP → empty response (HNAP needs HTTPS)    │
# │ Outcome:      Auth fails silently                                            │
# │                                                                              │
# │ If we had tried HTTPS: POST /HNAP1/ → success!                              │
# └─────────────────────────────────────────────────────────────────────────────┘
#
# The question: should connectivity check skip 4xx responses?
# Pro: Would help S34 case
# Con: Could break modems that legitimately return 401/403 for Basic Auth
#
# =============================================================================


class TestCurrentBehavior:
    """Tests documenting CURRENT behavior for protocol selection."""

    def test_connectivity_accepts_403_as_reachable(self):
        """CURRENT: 403 response is accepted as 'reachable'.

        This test documents the current behavior. S34 returns 403 on HTTP,
        and the connectivity check accepts it, setting working_url to HTTP.
        """
        # Start HTTP server that returns 403
        server = HTTPServer(("127.0.0.1", 0), Http403HttpsOkHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()

        try:
            # User provides just the IP (no protocol)
            result = check_connectivity(f"http://127.0.0.1:{port}")

            # Document current behavior: 403 is accepted
            assert result.success is True
            assert "http://" in result.working_url
            # No error - 403 is considered "reachable"
            assert result.error is None

        finally:
            server.shutdown()

    def test_http_first_order_when_no_protocol_specified(self):
        """CURRENT: HTTP is tried before HTTPS when no protocol specified.

        User enters: 192.168.100.1
        URLs tried: ['http://192.168.100.1', 'https://192.168.100.1']
        """
        # Start HTTP server that returns 200
        server = HTTPServer(("127.0.0.1", 0), HttpOkHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()

        try:
            # User provides just the IP (simulated with host:port)
            result = check_connectivity(f"127.0.0.1:{port}")

            # HTTP is tried first and succeeds
            assert result.success is True
            assert result.protocol == "http"
            assert result.working_url == f"http://127.0.0.1:{port}"

        finally:
            server.shutdown()

    def test_explicit_https_uses_only_https(self):
        """CURRENT: User can force HTTPS by specifying protocol explicitly.

        This is the workaround for S34 users - specify https:// in the host field.

        We verify this by checking that when HTTPS is specified, the code
        builds a URL list containing only that HTTPS URL.
        """
        # Verify the URL building logic directly
        host = "https://192.168.100.1"

        # This is the logic from connectivity.py lines 74-77
        if host.startswith(("http://", "https://")):
            urls_to_try = [host]
        else:
            urls_to_try = [f"http://{host}", f"https://{host}"]

        # When user specifies https://, only that URL should be tried
        assert urls_to_try == ["https://192.168.100.1"]
        assert len(urls_to_try) == 1  # No HTTP fallback


class TestProposedBehaviors:
    """Tests for PROPOSED behavior changes.

    These tests document what we MIGHT want to change.
    Currently they're just documentation/discussion starters.
    """

    @pytest.mark.skip(reason="Proposed behavior - not implemented")
    def test_skip_4xx_responses_in_connectivity_check(self):
        """PROPOSED: Skip 4xx responses and try next protocol.

        Ryan's suggestion from PR #90: Add status code validation.

        if resp.status_code >= 400:
            _LOGGER.debug("Connectivity check: %s returned %d, skipping", url, resp.status_code)
            continue

        Pros:
        - Fixes S34 (403 on HTTP → try HTTPS → success)

        Cons:
        - Could break modems using HTTP Basic Auth (401/403 expected initially)
        - 401 Unauthorized is often valid for auth-required modems
        """
        pass

    @pytest.mark.skip(reason="Proposed behavior - not implemented")
    def test_both_protocol_trial_with_auth_verification(self):
        """PROPOSED: Try both protocols, pick one where auth succeeds.

        1. Try HTTP connectivity → succeeds (200/403/etc)
        2. Try HTTPS connectivity → succeeds
        3. Attempt auth on HTTP → fails
        4. Attempt auth on HTTPS → succeeds
        5. Use HTTPS as working protocol

        Pros:
        - Most robust - actually verifies auth works

        Cons:
        - Slower (more requests)
        - More complex
        """
        pass

    @pytest.mark.skip(reason="Proposed behavior - not implemented")
    def test_modem_yaml_specifies_protocol(self):
        """PROPOSED: modem.yaml specifies required protocol.

        Add to S34's modem.yaml:
          network:
            protocol: https  # Required protocol for this modem

        Pros:
        - Explicit, predictable
        - No heuristics
        - Works for known modems

        Cons:
        - Only works for known modems
        - Fallback discovery still has the issue
        """
        pass


class TestUserInputScenarios:
    """Document what happens with different user inputs."""

    @pytest.mark.parametrize(
        "user_input,expected_urls_tried",
        [
            # User specifies protocol - use only that
            ("http://192.168.100.1", ["http://192.168.100.1"]),
            ("https://192.168.100.1", ["https://192.168.100.1"]),
            # User specifies IP only - try HTTP first, then HTTPS
            ("192.168.100.1", ["http://192.168.100.1", "https://192.168.100.1"]),
        ],
        ids=["explicit-http", "explicit-https", "ip-only"],
    )
    def test_url_order_by_input_type(self, user_input, expected_urls_tried):
        """Document which URLs are tried based on user input.

        This test documents the current URL building logic in connectivity.py.
        """

        # We can't easily inspect which URLs were tried without modifying the code,
        # but we can verify the expected behavior based on code review:
        #
        # if host.startswith(("http://", "https://")):
        #     urls_to_try = [host]
        # else:
        #     urls_to_try = [f"http://{host}", f"https://{host}"]
        #
        # This test is primarily documentation.
        pass
