"""MockModemServer - Fixture-driven HTTP server for E2E testing.

Reads modem.yaml configuration and serves fixture files,
implementing authentication flows based on the declared strategy.
"""

from __future__ import annotations

import logging
import socket
import ssl
import threading
from collections.abc import Generator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from custom_components.cable_modem_monitor.modem_config import load_modem_config
from custom_components.cable_modem_monitor.modem_config.loader import (
    get_modem_fixtures_path,
)
from custom_components.cable_modem_monitor.modem_config.schema import ModemConfig

from .mock_handlers import (
    FormAjaxAuthHandler,
    FormAuthHandler,
    FormDynamicAuthHandler,
    FormNonceAuthHandler,
    HnapAuthHandler,
    RestApiHandler,
    UrlTokenAuthHandler,
)
from .mock_handlers.base import BaseAuthHandler

_LOGGER = logging.getLogger(__name__)


def _find_free_port() -> int:
    """Find an available port for the test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class MockModemServer:
    """HTTP server that mocks a modem based on modem.yaml configuration.

    Serves fixture files and implements authentication flows
    based on the declared auth strategy.

    Supports variants:
    - auth_enabled=True (default): Use auth strategy from modem.yaml
    - auth_enabled=False: Bypass auth, serve fixtures directly (no-auth variant)
    - ssl_context: For HTTPS testing with self-signed certs
    """

    def __init__(
        self,
        modem_path: Path | str,
        port: int | None = None,
        host: str = "127.0.0.1",
        auth_enabled: bool = True,
        ssl_context: ssl.SSLContext | None = None,
        auth_type: str | None = None,
        auth_redirect: str | None = None,
        response_delay: float = 0.0,
        max_concurrent: int = 0,
    ):
        """Initialize MockModemServer.

        Args:
            modem_path: Path to modem directory containing modem.yaml.
            port: Port to listen on. If None, finds a free port.
            host: Host to bind to. Default 127.0.0.1, use 0.0.0.0 for external access.
            auth_enabled: If False, bypass auth and serve fixtures directly.
            ssl_context: SSL context for HTTPS. If None, uses HTTP.
            auth_type: Override auth type (e.g., "form", "none"). If None, uses first from modem.yaml.
            auth_redirect: Override redirect URL after auth. Used to simulate modems
                          that redirect to a different page than the data page.
            response_delay: Delay in seconds before sending responses (simulates slow modems).
            max_concurrent: Max concurrent sessions (0 = unlimited). Simulates modems like
                          Netgear C7000v2 that only allow one authenticated session at a time.
        """
        self.modem_path = Path(modem_path)
        self.port = port or _find_free_port()
        self.host = host
        self.auth_enabled = auth_enabled
        self.ssl_context = ssl_context
        self.auth_type_override = auth_type
        self.auth_redirect = auth_redirect
        self.response_delay = response_delay
        self.max_concurrent = max_concurrent

        # Load configuration
        self.config = load_modem_config(self.modem_path)
        self.fixtures_path = get_modem_fixtures_path(self.modem_path)

        # Create auth handler based on strategy (or NoAuth if disabled)
        self.handler = self._create_auth_handler()

        # Server state
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def _create_auth_handler(self) -> BaseAuthHandler:
        """Create the appropriate auth handler based on auth type.

        Auth type can include options separated by colon, e.g.:
        - "url_token" - standard URL token handler
        - "url_token:strict" - strict mode (requires URL token, rejects cookies)

        Returns:
            Auth handler instance.
        """
        # If auth disabled, always use NoAuthHandler
        if not self.auth_enabled:
            return NoAuthHandler(self.config, self.fixtures_path, response_delay=self.response_delay)

        # Get the auth type to use
        auth_types = self.config.auth.types
        if not auth_types:
            return NoAuthHandler(self.config, self.fixtures_path)

        # Parse auth type and options (e.g., "url_token:strict" -> "url_token", ["strict"])
        if self.auth_type_override:
            parts = self.auth_type_override.split(":")
            auth_type = parts[0]
            options = parts[1:] if len(parts) > 1 else []

            if auth_type not in auth_types:
                available = list(auth_types.keys())
                raise ValueError(f"Auth type '{auth_type}' not in modem.yaml. Available: {available}")
        else:
            auth_type = next(iter(auth_types.keys()))
            options = []

        # Map auth type string to handler
        handler_map = {
            "form": FormAuthHandler,
            "form_ajax": FormAjaxAuthHandler,
            "form_dynamic": FormDynamicAuthHandler,
            "form_nonce": FormNonceAuthHandler,
            "none": NoAuthHandler,
            "basic": BasicAuthHandler,
            "hnap": HnapAuthHandler,
            "url_token": UrlTokenAuthHandler,
            "rest_api": RestApiHandler,
        }

        handler_cls = handler_map.get(auth_type)
        if not handler_cls:
            raise NotImplementedError(f"Auth type not yet implemented: {auth_type}")

        # Handle handler-specific options
        if auth_type == "url_token":
            strict = "strict" in options
            two_step = "two_step" in options
            if strict or two_step:
                return handler_cls(  # type: ignore[no-any-return]
                    self.config,
                    self.fixtures_path,
                    strict=strict,
                    two_step=two_step,
                    response_delay=self.response_delay,
                )

        # Pass auth_redirect to form handlers
        if auth_type in ("form", "form_ajax", "form_dynamic", "form_nonce") and self.auth_redirect:
            return handler_cls(  # type: ignore[no-any-return]
                self.config,
                self.fixtures_path,
                auth_redirect=self.auth_redirect,
                response_delay=self.response_delay,
            )

        # Pass max_concurrent to BasicAuthHandler (simulates single-session modems)
        if auth_type == "basic" and self.max_concurrent > 0:
            return handler_cls(  # type: ignore[no-any-return]
                self.config,
                self.fixtures_path,
                response_delay=self.response_delay,
                max_concurrent=self.max_concurrent,
            )

        return handler_cls(  # type: ignore[no-any-return]
            self.config,
            self.fixtures_path,
            response_delay=self.response_delay,
        )

    @property
    def url(self) -> str:
        """Get the server URL."""
        scheme = "https" if self.ssl_context else "http"
        display_host = self.host if self.host != "0.0.0.0" else "127.0.0.1"
        return f"{scheme}://{display_host}:{self.port}"

    def start(self) -> None:
        """Start the server in a background thread."""
        # Create handler class with reference to our auth handler
        auth_handler = self.handler

        class RequestHandler(BaseHTTPRequestHandler):
            """HTTP request handler that delegates to auth handler."""

            def log_message(self, format: str, *args) -> None:
                """Suppress default logging."""
                pass

            def do_GET(self) -> None:  # noqa: N802
                """Handle GET requests."""
                headers = {k: v for k, v in self.headers.items()}
                status, resp_headers, body = auth_handler.handle_request(self, "GET", self.path, headers)
                self._send_response(status, resp_headers, body)

            def do_HEAD(self) -> None:  # noqa: N802
                """Handle HEAD requests (same as GET but no body)."""
                headers = {k: v for k, v in self.headers.items()}
                status, resp_headers, body = auth_handler.handle_request(self, "GET", self.path, headers)
                self._send_response(status, resp_headers, b"")  # No body for HEAD

            def do_POST(self) -> None:  # noqa: N802
                """Handle POST requests."""
                headers = {k: v for k, v in self.headers.items()}
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length) if content_length else None

                status, resp_headers, resp_body = auth_handler.handle_request(self, "POST", self.path, headers, body)
                self._send_response(status, resp_headers, resp_body)

            def _send_response(
                self,
                status: int,
                headers: dict[str, str],
                body: bytes,
            ) -> None:
                """Send HTTP response."""
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.end_headers()
                if body:
                    self.wfile.write(body)

        self._server = HTTPServer((self.host, self.port), RequestHandler)

        # Wrap socket with SSL if context provided
        if self.ssl_context:
            self._server.socket = self.ssl_context.wrap_socket(
                self._server.socket,
                server_side=True,
            )

        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.daemon = True
        self._thread.start()

        _LOGGER.info(
            "MockModemServer started for %s %s at %s",
            self.config.manufacturer,
            self.config.model,
            self.url,
        )

    def stop(self) -> None:
        """Stop the server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=5)

        _LOGGER.info("MockModemServer stopped")

    @classmethod
    @contextmanager
    def from_modem_path(
        cls,
        modem_path: Path | str,
        port: int | None = None,
        auth_enabled: bool = True,
        ssl_context: ssl.SSLContext | None = None,
        auth_type: str | None = None,
        auth_redirect: str | None = None,
        response_delay: float = 0.0,
        max_concurrent: int = 0,
    ) -> Generator[MockModemServer, None, None]:
        """Context manager to start and stop server.

        Args:
            modem_path: Path to modem directory.
            port: Optional port number.
            auth_enabled: If False, bypass auth and serve fixtures directly.
            ssl_context: SSL context for HTTPS. If None, uses HTTP.
            auth_type: Override auth type (e.g., "form", "none"). If None, uses first from modem.yaml.
            auth_redirect: Override redirect URL after auth.
            response_delay: Delay in seconds before sending responses (simulates slow modems).
            max_concurrent: Max concurrent sessions (0 = unlimited).

        Yields:
            Started MockModemServer instance.
        """
        server = cls(
            modem_path,
            port,
            auth_enabled=auth_enabled,
            ssl_context=ssl_context,
            auth_type=auth_type,
            auth_redirect=auth_redirect,
            response_delay=response_delay,
            max_concurrent=max_concurrent,
        )
        server.start()
        try:
            yield server
        finally:
            server.stop()


# =============================================================================
# SIMPLE HANDLERS FOR OTHER STRATEGIES
# =============================================================================


class NoAuthHandler(BaseAuthHandler):
    """Handler for modems without authentication."""

    def __init__(
        self,
        config: ModemConfig,
        fixtures_path: Path,
        response_delay: float = 0.0,
    ):
        """Initialize handler."""
        super().__init__(config, fixtures_path, response_delay=response_delay)

    def handle_request(
        self,
        handler: BaseHTTPRequestHandler,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle request - just serve the fixture."""
        from urllib.parse import urlparse

        clean_path = urlparse(path).path
        return self.serve_fixture(clean_path)


class BasicAuthHandler(BaseAuthHandler):
    """Handler for HTTP Basic authentication.

    Supports simulating single-session modems (like Netgear C7000v2) via max_concurrent.
    When max_concurrent=1, only one authenticated session is allowed at a time.
    New sessions are blocked until the active session calls the logout endpoint.
    """

    def __init__(
        self,
        config: ModemConfig,
        fixtures_path: Path,
        response_delay: float = 0.0,
        max_concurrent: int = 0,
    ):
        """Initialize handler.

        Args:
            config: Modem configuration.
            fixtures_path: Path to fixture files.
            response_delay: Delay before responses (simulates slow modems).
            max_concurrent: Max concurrent sessions. 0 = unlimited.
        """
        super().__init__(config, fixtures_path, response_delay=response_delay)
        self.max_concurrent = max_concurrent
        # Track active sessions by client address (ip:port)
        self.active_clients: dict[str, float] = {}  # client_id -> last_request_time
        # Session timeout in seconds (clear stale sessions)
        self.session_timeout = 30.0

    def _get_client_id(self, handler: BaseHTTPRequestHandler, headers: dict[str, str]) -> str:
        """Get unique client identifier from request handler.

        For testing: Uses X-Mock-Client-ID header if present, allowing tests
        to simulate multiple distinct clients from the same IP.

        For real behavior: Uses client IP address. This approximates Netgear's
        session tracking where requests from the same IP share a session.
        """
        # Allow tests to override client identity via header
        test_client_id = headers.get("X-Mock-Client-ID")
        if test_client_id:
            return f"test:{test_client_id}"

        # Default: use IP address (all localhost requests share a session)
        client_addr = handler.client_address
        return client_addr[0]

    def _cleanup_stale_sessions(self) -> None:
        """Remove sessions that have timed out."""
        import time

        now = time.time()
        stale = [
            client_id for client_id, last_time in self.active_clients.items() if now - last_time > self.session_timeout
        ]
        for client_id in stale:
            _LOGGER.debug("Cleaning up stale session: %s", client_id)
            del self.active_clients[client_id]

    def _check_session_limit(self, client_id: str) -> bool:
        """Check if this client can proceed given session limits.

        Returns:
            True if client can proceed, False if blocked by session limit.
        """
        if self.max_concurrent <= 0:
            return True  # No limit

        self._cleanup_stale_sessions()

        # If this client already has a session, allow it
        if client_id in self.active_clients:
            return True

        # Check if we're at capacity
        if len(self.active_clients) >= self.max_concurrent:
            _LOGGER.warning(
                "Session limit reached (%d). Blocking client %s. Active: %s",
                self.max_concurrent,
                client_id,
                list(self.active_clients.keys()),
            )
            return False

        return True

    def _register_session(self, client_id: str) -> None:
        """Register an active session for this client."""
        import time

        self.active_clients[client_id] = time.time()
        _LOGGER.debug("Registered session for %s. Active sessions: %d", client_id, len(self.active_clients))

    def _clear_session(self, client_id: str) -> None:
        """Clear session for this client (logout)."""
        if client_id in self.active_clients:
            del self.active_clients[client_id]
            _LOGGER.debug("Cleared session for %s. Active sessions: %d", client_id, len(self.active_clients))

    def handle_request(
        self,
        handler: BaseHTTPRequestHandler,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle request with Basic Auth check and session limits."""
        import base64
        from urllib.parse import urlparse

        clean_path = urlparse(path).path
        client_id = self._get_client_id(handler, headers)

        # Handle logout endpoint - always allowed, clears all sessions
        # (Netgear logout clears the session regardless of which client calls it)
        logout_endpoint = None
        if self.config.auth and self.config.auth.session:
            logout_endpoint = self.config.auth.session.logout_endpoint
        if logout_endpoint and clean_path == logout_endpoint:
            # Clear ALL sessions on logout (simulates Netgear behavior)
            self.active_clients.clear()
            _LOGGER.debug("Logout called - cleared all sessions")
            # Use goform handler for /goform/logout (no fixture needed)
            if clean_path.startswith("/goform/"):
                return self._handle_goform(method, clean_path)
            return self.serve_fixture(clean_path)

        # Public paths don't need auth
        if self.is_public_path(clean_path):
            return self.serve_fixture(clean_path)

        # Check Authorization header
        auth_header = headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            try:
                token = auth_header.split(" ", 1)[1]
                decoded = base64.b64decode(token).decode("utf-8")
                username, password = decoded.split(":", 1)

                # Use test credentials
                from .mock_handlers.form import TEST_PASSWORD, TEST_USERNAME

                if username == TEST_USERNAME and password == TEST_PASSWORD:
                    # Check session limit BEFORE granting access
                    if not self._check_session_limit(client_id):
                        self.apply_delay()
                        return (
                            503,
                            {"Content-Type": "text/plain", "Retry-After": "5"},
                            b"Service Unavailable - maximum sessions reached",
                        )

                    # Register this client's session
                    self._register_session(client_id)

                    # Handle form actions (restart, etc.)
                    if clean_path.startswith("/goform/"):
                        return self._handle_goform(method, clean_path)
                    return self.serve_fixture(clean_path)
            except Exception:
                pass

        # Return 401 Unauthorized
        self.apply_delay()
        return (
            401,
            {
                "WWW-Authenticate": f'Basic realm="{self.config.model}"',
                "Content-Type": "text/plain",
            },
            b"Unauthorized",
        )

    def _handle_goform(self, method: str, path: str) -> tuple[int, dict[str, str], bytes]:
        """Handle /goform/* endpoints (restart, settings, etc.)."""
        self.apply_delay()
        # Simulate successful form submission
        # Real modems either return 200 or drop connection on restart
        return (
            200,
            {"Content-Type": "text/html"},
            b"<html><body>Command accepted</body></html>",
        )
