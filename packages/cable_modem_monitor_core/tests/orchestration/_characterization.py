"""Shared setup for the strategy-knowledge characterization tests.

Two pieces: a real ``ModemConfig`` builder for any auth block, and a
local HTTP server that records every request it receives.
Characterization tests observe what the collector and action
dispatcher put on the wire (URL query, headers, POST body) instead of
patching loader constructors, so the pinned behaviour survives any
internal restructuring of how those values are passed around.
"""

from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any
from urllib.parse import urlsplit

from solentlabs.cable_modem_monitor_core.models.modem_config import ModemConfig
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import get_auth_strategy_rows

_TRANSPORT_BY_STRATEGY = {row.strategy: row.transport for row in get_auth_strategy_rows()}


def build_modem_config(auth: dict[str, Any] | None, **extra: Any) -> ModemConfig:
    """Validate a minimal modem config whose transport follows the auth strategy."""
    transport = _TRANSPORT_BY_STRATEGY[auth["strategy"]] if auth else "http"
    data: dict[str, Any] = {
        "manufacturer": "Solent Labs",
        "model": "T100",
        "transport": transport,
        "default_host": "192.168.100.1",
        "status": "unsupported",
        "auth": auth,
        **extra,
    }
    return ModemConfig.model_validate(data)


@dataclass(frozen=True)
class RecordedRequest:
    """One request as the server saw it."""

    method: str
    path: str
    query: str
    headers: dict[str, str]
    body: str


class _RecordingHandler(BaseHTTPRequestHandler):
    """Record the request, then answer with the server's canned response."""

    def _handle(self) -> None:
        server = self.server
        assert isinstance(server, RecordingServer)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8") if length else ""
        parts = urlsplit(self.path)
        server.requests.append(
            RecordedRequest(
                method=self.command,
                path=parts.path,
                query=parts.query,
                headers=dict(self.headers.items()),
                body=body,
            )
        )
        content_type, payload = server.response
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(payload.encode("utf-8"))

    def do_GET(self) -> None:
        """Record a GET."""
        self._handle()

    def do_POST(self) -> None:
        """Record a POST."""
        self._handle()

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress logging."""


class RecordingServer(HTTPServer):
    """Answer every path with one canned 200 response and record the request."""

    def __init__(self, content_type: str, payload: str) -> None:
        self.response = (content_type, payload)
        self.requests: list[RecordedRequest] = []
        super().__init__(("127.0.0.1", 0), _RecordingHandler)

    @property
    def base_url(self) -> str:
        """Server base URL."""
        return f"http://127.0.0.1:{self.server_address[1]}"

    def __enter__(self) -> RecordingServer:
        """Start serving in a background thread."""
        # Short poll keeps shutdown fast across many parametrized rows.
        self._thread = Thread(target=self.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        """Stop serving."""
        self.shutdown()
        self._thread.join(timeout=5)
        self.server_close()
