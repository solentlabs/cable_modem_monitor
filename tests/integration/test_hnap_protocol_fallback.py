"""Tests for HNAP modem protocol fallback behavior.

Issue: S34 and other HNAP modems respond to HTTP but only work over HTTPS.
The connectivity check accepts HTTP responses, but HNAP auth fails.

These tests verify:
1. CURRENT BEHAVIOR: setup_modem fails when HTTP is tried first for HNAP modems
2. DESIRED BEHAVIOR: setup_modem tries HTTPS if HTTP auth fails

Related: PR #90 (S34 support), Issue #81 (SB8200)
"""

from __future__ import annotations

import ssl
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from custom_components.cable_modem_monitor.core.setup import setup_modem

# =============================================================================
# DUAL-PROTOCOL MOCK SERVER
# =============================================================================
# Simulates S34 behavior:
# - HTTP: Responds with 403 (connectivity check accepts) or empty HNAP response
# - HTTPS: HNAP works correctly
# =============================================================================


class HttpOnly403Handler(BaseHTTPRequestHandler):
    """HTTP handler that returns 403 for everything.

    Simulates S34's HTTP behavior - server responds but auth won't work.
    """

    def log_message(self, format, *args):
        pass

    def do_HEAD(self):  # noqa: N802
        self.send_response(403)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        self.send_response(403)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Forbidden")

    def do_POST(self):  # noqa: N802
        """HNAP POST returns empty response on HTTP."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        # Empty response - HNAP auth will fail to parse this
        self.wfile.write(b"")


class HttpsHnapHandler(BaseHTTPRequestHandler):
    """HTTPS handler that implements working HNAP auth.

    Simplified HNAP - returns success for any login attempt.
    """

    def log_message(self, format, *args):
        pass

    def do_HEAD(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        # Serve HNAP login page
        content = b"""<!DOCTYPE html>
<html><head><title>Login</title>
<script src="js/SOAP/SOAPAction.js"></script>
</head><body>
<form id="loginForm">
<input type="text" id="username">
<input type="password" id="password">
</form>
</body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):  # noqa: N802
        """HNAP POST returns proper JSON response on HTTPS."""
        import json

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""

        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            data = {}

        login_data = data.get("Login", {})
        action = login_data.get("Action", "")

        if action == "request" or not login_data.get("LoginPassword"):
            # Challenge response
            response = {
                "LoginResponse": {
                    "LoginResult": "OK",
                    "Challenge": "ABCD1234",
                    "PublicKey": "1234ABCD",
                    "Cookie": "testsession",
                }
            }
        else:
            # Login success
            response = {"LoginResponse": {"LoginResult": "OK"}}

        content = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Set-Cookie", "uid=testsession; Path=/")
        self.end_headers()
        self.wfile.write(content)


class DualProtocolModem:
    """Mock modem with different behavior on HTTP vs HTTPS.

    HTTP port: Returns 403/empty (simulates S34 HTTP behavior)
    HTTPS port: HNAP works correctly
    """

    def __init__(self, test_certs: tuple[str, str]):
        self.http_port = self._find_free_port()
        self.https_port = self._find_free_port()
        self.cert_path, self.key_path = test_certs

        self._http_server: HTTPServer | None = None
        self._https_server: HTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._https_thread: threading.Thread | None = None

    def _find_free_port(self) -> int:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def start(self):
        # Start HTTP server (returns 403)
        self._http_server = HTTPServer(("127.0.0.1", self.http_port), HttpOnly403Handler)
        self._http_thread = threading.Thread(target=self._http_server.serve_forever)
        self._http_thread.daemon = True
        self._http_thread.start()

        # Start HTTPS server (HNAP works)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.cert_path, self.key_path)

        self._https_server = HTTPServer(("127.0.0.1", self.https_port), HttpsHnapHandler)
        self._https_server.socket = context.wrap_socket(self._https_server.socket, server_side=True)
        self._https_thread = threading.Thread(target=self._https_server.serve_forever)
        self._https_thread.daemon = True
        self._https_thread.start()

    def stop(self):
        if self._http_server:
            self._http_server.shutdown()
        if self._https_server:
            self._https_server.shutdown()
        if self._http_thread:
            self._http_thread.join(timeout=5)
        if self._https_thread:
            self._https_thread.join(timeout=5)


@pytest.fixture
def dual_protocol_hnap_modem(test_certs) -> DualProtocolModem:
    """Provide modem that only works on HTTPS but responds on HTTP."""
    modem = DualProtocolModem(test_certs)
    modem.start()
    yield modem
    modem.stop()


# =============================================================================
# TESTS
# =============================================================================


MODEMS_DIR = Path(__file__).parent.parent.parent / "modems"


def _get_s34_parser():
    """Get S34 parser class."""
    from custom_components.cable_modem_monitor.core.parser_registry import get_parser_by_name

    return get_parser_by_name("Arris/CommScope S34")


def _build_s34_auth_config():
    """Build static auth config for S34."""
    from custom_components.cable_modem_monitor.core.auth.workflow import AUTH_TYPE_TO_STRATEGY
    from custom_components.cable_modem_monitor.modem_config import get_auth_adapter_for_parser

    parser = _get_s34_parser()
    adapter = get_auth_adapter_for_parser(parser.__name__)
    type_config = adapter.get_auth_config_for_type("hnap")

    return {
        "auth_strategy": AUTH_TYPE_TO_STRATEGY.get("hnap"),
        "auth_hnap_config": type_config,
        "timeout": adapter.config.timeout,
    }


class TestCurrentBehavior:
    """Tests documenting CURRENT (broken) behavior for HNAP protocol selection."""

    def test_explicit_https_works(self, dual_protocol_hnap_modem, test_certs):
        """CURRENT: Explicit HTTPS URL works for HNAP modems.

        When user specifies https://, we use HTTPS and auth succeeds.
        This is the workaround S34 users can use.
        """
        parser = _get_s34_parser()
        if not parser:
            pytest.skip("S34 parser not found")

        auth_config = _build_s34_auth_config()

        # Explicit HTTPS - should work
        result = setup_modem(
            host=f"https://127.0.0.1:{dual_protocol_hnap_modem.https_port}",
            parser_class=parser,
            static_auth_config=auth_config,
            username="admin",
            password="pw",
        )

        assert result.success, f"HTTPS should work but got: {result.error}"
        assert "https://" in result.working_url

    def test_explicit_http_fails_for_hnap(self, dual_protocol_hnap_modem):
        """CURRENT: Explicit HTTP URL fails for HNAP modems.

        When user specifies http://, HNAP auth fails because
        the modem returns empty response on HTTP.
        """
        parser = _get_s34_parser()
        if not parser:
            pytest.skip("S34 parser not found")

        auth_config = _build_s34_auth_config()

        # Explicit HTTP - should fail (HNAP doesn't work over HTTP)
        result = setup_modem(
            host=f"http://127.0.0.1:{dual_protocol_hnap_modem.http_port}",
            parser_class=parser,
            static_auth_config=auth_config,
            username="admin",
            password="pw",
        )

        # This SHOULD fail - HNAP returns empty on HTTP
        assert not result.success, "HTTP should fail for HNAP but it succeeded?"
        assert result.failed_step == "auth"


class TestProtocolFallback:
    """Tests for protocol fallback behavior.

    These tests verify that setup_modem tries multiple protocols
    when no explicit protocol is specified.
    """

    def test_hnap_paradigm_tries_https_first(self, test_certs):
        """HNAP paradigm should try HTTPS first.

        When we have only an HTTPS server and call setup_modem with just
        the port (no protocol), it should:
        1. Try HTTPS first (based on HNAP paradigm)
        2. Succeed on HTTPS
        """
        from tests.integration.mock_modem_server import MockModemServer

        modem_path = MODEMS_DIR / "arris" / "s34"
        if not modem_path.exists():
            pytest.skip("S34 modem directory not found")

        parser = _get_s34_parser()
        if not parser:
            pytest.skip("S34 parser not found")

        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        with MockModemServer.from_modem_path(modem_path, auth_type="hnap", ssl_context=context) as server:
            auth_config = _build_s34_auth_config()

            # No protocol specified - just host:port
            # HNAP paradigm should try HTTPS first
            result = setup_modem(
                host=f"127.0.0.1:{server.port}",  # No protocol!
                parser_class=parser,
                static_auth_config=auth_config,
                username="admin",
                password="pw",
            )

            # Should succeed on HTTPS (tried first for HNAP)
            assert result.success, f"Setup failed: {result.error}"
            assert result.working_url is not None
            assert "https://" in result.working_url, f"Expected HTTPS URL but got: {result.working_url}"

    def test_html_paradigm_tries_http_first(self):
        """HTML paradigm should try HTTP first.

        When we have only an HTTP server and call setup_modem with just
        the port (no protocol), it should:
        1. Try HTTP first (based on HTML paradigm)
        2. Succeed on HTTP
        """
        from tests.integration.mock_modem_server import MockModemServer

        modem_path = MODEMS_DIR / "motorola" / "mb7621"
        if not modem_path.exists():
            pytest.skip("MB7621 modem directory not found")

        from custom_components.cable_modem_monitor.core.auth.workflow import (
            AUTH_TYPE_TO_STRATEGY,
        )
        from custom_components.cable_modem_monitor.core.parser_registry import (
            get_parser_by_name,
        )
        from custom_components.cable_modem_monitor.modem_config import (
            get_auth_adapter_for_parser,
        )

        parser = get_parser_by_name("Motorola MB7621")
        if not parser:
            pytest.skip("MB7621 parser not found")

        adapter = get_auth_adapter_for_parser(parser.__name__)
        type_config = adapter.get_auth_config_for_type("form")
        auth_config = {
            "auth_strategy": AUTH_TYPE_TO_STRATEGY.get("form"),
            "auth_form_config": type_config,
            "timeout": adapter.config.timeout,
        }

        # HTTP-only server (no SSL context)
        with MockModemServer.from_modem_path(modem_path, auth_type="form", ssl_context=None) as server:
            # No protocol specified - just host:port
            # HTML paradigm should try HTTP first
            result = setup_modem(
                host=f"127.0.0.1:{server.port}",  # No protocol!
                parser_class=parser,
                static_auth_config=auth_config,
                username="admin",
                password="pw",  # Default mock server password
            )

            # Should succeed on HTTP (tried first for HTML)
            assert result.success, f"Setup failed: {result.error}"
            assert result.working_url is not None
            assert "http://" in result.working_url, f"Expected HTTP URL but got: {result.working_url}"

    def test_fallback_when_first_protocol_fails(self, test_certs):
        """Should fall back to second protocol when first fails.

        Even if HTTP is tried first, if it fails (connection refused),
        HTTPS should be tried next.
        """
        from tests.integration.mock_modem_server import MockModemServer

        # Use an HTML-paradigm modem but serve only HTTPS
        modem_path = MODEMS_DIR / "arris" / "sb6190"
        if not modem_path.exists():
            pytest.skip("SB6190 modem directory not found")

        from custom_components.cable_modem_monitor.core.auth.workflow import (
            AUTH_TYPE_TO_STRATEGY,
        )
        from custom_components.cable_modem_monitor.core.parser_registry import (
            get_parser_by_name,
        )
        from custom_components.cable_modem_monitor.modem_config import (
            get_auth_adapter_for_parser,
        )

        parser = get_parser_by_name("ARRIS SB6190")
        if not parser:
            pytest.skip("SB6190 parser not found")

        # no_auth doesn't need additional config
        adapter = get_auth_adapter_for_parser(parser.__name__)
        auth_config = {
            "auth_strategy": AUTH_TYPE_TO_STRATEGY.get("none"),
            "timeout": adapter.config.timeout,
        }

        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        # HTTPS-only server (HTML paradigm would try HTTP first, but it will fail)
        with MockModemServer.from_modem_path(modem_path, auth_type="none", ssl_context=context) as server:
            # No protocol specified - just host:port
            # HTML paradigm tries HTTP first, but only HTTPS server exists
            result = setup_modem(
                host=f"127.0.0.1:{server.port}",  # No protocol!
                parser_class=parser,
                static_auth_config=auth_config,
                username="",
                password="",
            )

            # Should succeed on HTTPS (after HTTP failed)
            assert result.success, f"Setup failed: {result.error}"
            assert result.working_url is not None
            assert "https://" in result.working_url, f"Expected HTTPS URL after fallback but got: {result.working_url}"


class TestRealWorldScenario:
    """Tests using actual modem fixtures (closer to real deployment)."""

    def test_s34_explicit_https_with_mock_server(self, test_certs):
        """S34 with explicit HTTPS using MockModemServer."""
        from tests.integration.mock_modem_server import MockModemServer

        modem_path = MODEMS_DIR / "arris" / "s34"
        if not modem_path.exists():
            pytest.skip("S34 modem directory not found")

        parser = _get_s34_parser()
        if not parser:
            pytest.skip("S34 parser not found")

        cert_path, key_path = test_certs
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)

        with MockModemServer.from_modem_path(modem_path, auth_type="hnap", ssl_context=context) as server:
            auth_config = _build_s34_auth_config()

            # Explicit HTTPS - should work
            result = setup_modem(
                host=f"https://127.0.0.1:{server.port}",
                parser_class=parser,
                static_auth_config=auth_config,
                username="admin",
                password="pw",
            )

            assert result.success, f"S34 HTTPS setup failed: {result.error}"
