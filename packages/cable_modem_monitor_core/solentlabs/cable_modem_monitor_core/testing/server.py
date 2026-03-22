"""HTTP server — thin layer composing routes and auth.

Context manager for clean lifecycle. Starts on an ephemeral port,
stops cleanly on exit.

See ONBOARDING_SPEC.md HAR Mock Server section.
"""

from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from ..models.modem_config import ModemConfig

from .auth import create_auth_handler
from .routes import build_routes, normalize_path

_logger = logging.getLogger(__name__)


class _MockHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the mock server.

    Dispatches requests through the auth layer and route table.
    """

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET requests."""
        self._handle_request("GET")

    def do_POST(self) -> None:  # noqa: N802
        """Handle POST requests."""
        self._handle_request("POST")

    def _handle_request(self, method: str) -> None:
        """Dispatch a request through auth then routes."""
        server: HARMockServer = self.server  # type: ignore[assignment]
        parsed = urlparse(self.path)
        path = normalize_path(parsed.path)
        # Include query string for route lookup so endpoints like
        # /setup.cgi?todo=X resolve independently.
        route_path = f"{path}?{parsed.query}" if parsed.query else path
        headers = {k.lower(): v for k, v in self.headers.items()}

        body = b""
        if method == "POST":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

        auth = server.auth_handler

        # Login request — handle auth and serve response
        if auth.is_login_request(method, path):
            self._handle_login(server, method, path, route_path, body, headers)
            return

        # Non-login request — check auth
        if not auth.is_authenticated(headers):
            self._send_response(401, [], "Unauthorized")
            return

        # Auth handler route override (HNAP merged data response)
        override = auth.get_route_override(method, path, body, headers)
        if override is not None:
            self._send_response(override.status, override.headers, override.body)
            return

        # Serve from route table
        route = _find_route(server.routes, method, path, route_path)
        if route is None:
            self._send_response(404, [], "Not Found")
            return

        self._send_response(route.status, route.headers, route.body)

    def _handle_login(
        self,
        server: HARMockServer,
        method: str,
        path: str,
        route_path: str,
        body: bytes,
        headers: dict[str, str],
    ) -> None:
        """Handle a login request through auth then route table."""
        auth = server.auth_handler
        login_response = auth.handle_login(method, path, body, headers)
        if login_response is not None:
            self._send_response(
                login_response.status,
                login_response.headers,
                login_response.body,
            )
            return
        # Fall through to route table (form auth)
        route = _find_route(server.routes, method, path, route_path)
        if route is None:
            self._send_response(404, [], "Not Found")
            return
        extra_headers = auth.set_authenticated()
        response_headers = list(route.headers)
        for name, value in extra_headers.items():
            response_headers.append((name, value))
        self._send_response(route.status, response_headers, route.body)

    def _send_response(
        self,
        status: int,
        headers: list[tuple[str, str]],
        body: str,
    ) -> None:
        """Send an HTTP response."""
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        if body:
            self.wfile.write(body.encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stderr logging."""
        _logger.debug(format, *args)


def _find_route(
    routes: dict[tuple[str, str], Any],
    method: str,
    path: str,
    route_path: str,
) -> Any:
    """Look up a route by method and path, with query-string fallback.

    Three-tier lookup:

    1. Exact match ``(method, route_path)`` — query string included.
    2. Path-only ``(method, path)`` — request has query, route doesn't.
    3. Scan for route whose path portion matches — route has query
       (e.g. HAR captured ``?status=1``), request doesn't.

    Tiers 1-2 handle query-string-specific routes (e.g.
    ``/setup.cgi?todo=X``) and dynamic URL token suffixes.
    Tier 3 handles HARs that captured incidental query params
    (e.g. ``?status=1``) that aren't part of the resource path.
    """
    # Tier 1: exact match
    route = routes.get((method, route_path))
    if route is not None:
        return route

    # Tier 2: request has query, route stored without
    if route_path != path:
        route = routes.get((method, path))
        if route is not None:
            return route

    # Tier 3: route has query, request doesn't — scan by path prefix
    for (m, rp), r in routes.items():
        if m == method and rp.split("?", 1)[0] == path:
            return r

    return None


class HARMockServer(HTTPServer):
    """Auth-aware HAR replay HTTP server.

    Context manager that starts on an ephemeral port and stops cleanly.

    Usage::

        har_data = json.loads(Path("modem.har").read_text())
        entries = har_data["log"]["entries"]

        with HARMockServer(entries, modem_config=modem_config) as server:
            base_url = server.base_url
            # ... run pipeline against base_url ...

    Args:
        har_entries: HAR ``log.entries`` list.
        modem_config: Validated ``ModemConfig`` for auth handler creation.
            None for no auth.
    """

    def __init__(
        self,
        har_entries: list[dict[str, Any]],
        modem_config: ModemConfig | None = None,
    ) -> None:
        self.routes = build_routes(har_entries)
        self.auth_handler = create_auth_handler(modem_config, har_entries)
        self._thread: threading.Thread | None = None

        super().__init__(("127.0.0.1", 0), _MockHandler)

    @property
    def base_url(self) -> str:
        """Base URL of the running server (e.g., ``http://127.0.0.1:54321``)."""
        host = str(self.server_address[0])
        port = self.server_address[1]
        return f"http://{host}:{port}"

    def __enter__(self) -> HARMockServer:
        """Start the server in a background thread."""
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        """Stop the server and wait for the thread to finish."""
        self.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self.server_close()
