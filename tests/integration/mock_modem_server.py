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
        """
        self.modem_path = Path(modem_path)
        self.port = port or _find_free_port()
        self.host = host
        self.auth_enabled = auth_enabled
        self.ssl_context = ssl_context
        self.auth_type_override = auth_type
        self.auth_redirect = auth_redirect
        self.response_delay = response_delay

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
        if auth_type in ("form", "form_ajax", "form_dynamic") and self.auth_redirect:
            return handler_cls(  # type: ignore[no-any-return]
                self.config,
                self.fixtures_path,
                auth_redirect=self.auth_redirect,
                response_delay=self.response_delay,
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
    """Handler for HTTP Basic authentication."""

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
        """Handle request with Basic Auth check."""
        import base64
        from urllib.parse import urlparse

        clean_path = urlparse(path).path

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
