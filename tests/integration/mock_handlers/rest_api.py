"""REST API authentication handler for MockModemServer.

Handles JSON REST API endpoints without authentication.
Used by: Virgin Hub 5
"""

from __future__ import annotations

import logging
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from .base import BaseAuthHandler

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.modem_config.schema import ModemConfig

_LOGGER = logging.getLogger(__name__)


class RestApiHandler(BaseAuthHandler):
    """Handler for REST API endpoints.

    Serves JSON fixtures for REST API paths.
    Maps paths like /rest/v1/cablemodem/downstream to downstream.json fixtures.
    """

    def __init__(self, config: ModemConfig, fixtures_path: Path):
        """Initialize REST API handler.

        Args:
            config: Modem configuration.
            fixtures_path: Path to fixtures directory.
        """
        super().__init__(config, fixtures_path)

        # Extract REST API config
        self.rest_api_config = config.auth.rest_api

    def handle_request(
        self,
        handler: BaseHTTPRequestHandler,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle HTTP request for REST API.

        Args:
            handler: HTTP request handler.
            method: HTTP method.
            path: Request path with query string.
            headers: Request headers.
            body: Request body.

        Returns:
            Response tuple (status, headers, body).
        """
        parsed = urlparse(path)
        clean_path = parsed.path

        # Handle root path (gateway HTML page for detection)
        if clean_path == "/" or clean_path == "":
            content = self._get_html_fixture("index.html")
            if content is not None:
                return (
                    200,
                    {
                        "Content-Type": "text/html",
                        "Content-Length": str(len(content)),
                    },
                    content,
                )

        # Get JSON fixture content for API paths
        content = self._get_json_fixture(clean_path)

        if content is None:
            return 404, {"Content-Type": "application/json"}, b'{"error": "Not Found"}'

        return (
            200,
            {
                "Content-Type": "application/json",
                "Content-Length": str(len(content)),
            },
            content,
        )

    def _get_html_fixture(self, filename: str) -> bytes | None:
        """Get HTML fixture file.

        Args:
            filename: HTML fixture filename.

        Returns:
            Fixture content as bytes, or None if not found.
        """
        fixture_path = self.fixtures_path / filename
        if fixture_path.exists() and fixture_path.is_file():
            return fixture_path.read_bytes()
        return None

    def _get_json_fixture(self, path: str) -> bytes | None:
        """Get JSON fixture for an API path.

        Maps REST API paths to fixture files:
        - /rest/v1/cablemodem/downstream -> downstream.json
        - /rest/v1/cablemodem/state_ -> state.json

        Args:
            path: API path.

        Returns:
            Fixture content as bytes, or None if not found.
        """
        # Extract endpoint name from path
        # /rest/v1/cablemodem/downstream -> downstream
        # /rest/v1/cablemodem/state_ -> state_ (or state)
        endpoint = path.rstrip("/").split("/")[-1]

        # Try exact match first (e.g., state_.json)
        fixture_path = self.fixtures_path / f"{endpoint}.json"
        if fixture_path.exists():
            return fixture_path.read_bytes()

        # Try without trailing underscore (state_ -> state.json)
        if endpoint.endswith("_"):
            fixture_path = self.fixtures_path / f"{endpoint.rstrip('_')}.json"
            if fixture_path.exists():
                return fixture_path.read_bytes()

        # Try nested path structure
        nested_path = path.lstrip("/")
        if nested_path:  # Skip empty path (root "/")
            fixture_path = self.fixtures_path / nested_path
            if fixture_path.exists() and fixture_path.is_file():
                return fixture_path.read_bytes()

            # Try with .json extension
            fixture_path = self.fixtures_path / f"{nested_path}.json"
            if fixture_path.exists() and fixture_path.is_file():
                return fixture_path.read_bytes()

        _LOGGER.warning("REST API fixture not found for path: %s", path)
        return None
