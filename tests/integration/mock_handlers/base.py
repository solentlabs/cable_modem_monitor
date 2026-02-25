"""Base handler for MockModemServer.

Provides common functionality for all auth strategy handlers.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.modem_config.schema import ModemConfig

_LOGGER = logging.getLogger(__name__)


class BaseAuthHandler(ABC):
    """Base class for authentication strategy handlers.

    Subclasses implement specific auth strategies (form, basic, hnap, etc.).
    """

    def __init__(self, config: ModemConfig, fixtures_path: Path, response_delay: float = 0.0):
        """Initialize handler.

        Args:
            config: Modem configuration from modem.yaml.
            fixtures_path: Path to fixtures directory.
            response_delay: Delay in seconds before sending responses (simulates slow modems).
        """
        self.config = config
        self.fixtures_path = fixtures_path
        self.sessions: set[str] = set()
        self.response_delay = response_delay

    @abstractmethod
    def handle_request(
        self,
        handler: BaseHTTPRequestHandler,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle an HTTP request.

        Args:
            handler: The HTTP request handler.
            method: HTTP method (GET, POST).
            path: Request path (may include query string).
            headers: Request headers.
            body: Request body for POST requests.

        Returns:
            Tuple of (status_code, response_headers, response_body).
        """

    def is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required).

        Args:
            path: URL path.

        Returns:
            True if path is public.
        """
        if not self.config.pages:
            return True

        # Normalize path (remove query string)
        clean_path = urlparse(path).path

        return clean_path in self.config.pages.public

    def is_protected_path(self, path: str) -> bool:
        """Check if path requires authentication.

        Args:
            path: URL path.

        Returns:
            True if path requires auth.
        """
        return not self.is_public_path(path)

    def get_fixture_content(self, path: str) -> bytes | None:
        """Get fixture file content for a path.

        Args:
            path: URL path (e.g., "/MotoConnection.asp").

        Returns:
            File content as bytes, or None if not found.
        """
        # Normalize path
        clean_path = urlparse(path).path.lstrip("/")

        if not clean_path:
            # Try index.html first, then root.html
            for default in ("index.html", "root.html"):
                if (self.fixtures_path / default).exists():
                    clean_path = default
                    break
            else:
                clean_path = "index.html"  # Will 404

        fixture_path = self.fixtures_path / clean_path

        # If path is a directory, look for index.html inside
        if fixture_path.is_dir():
            index_path = fixture_path / "index.html"
            if index_path.exists():
                return index_path.read_bytes()
        elif fixture_path.exists():
            return fixture_path.read_bytes()

        # Try with .html extension
        html_path = self.fixtures_path / f"{clean_path}.html"
        if html_path.exists():
            return html_path.read_bytes()

        # Try stripping trailing slash and adding .html
        if clean_path.endswith("/"):
            stripped_path = self.fixtures_path / f"{clean_path.rstrip('/')}.html"
            if stripped_path.exists():
                return stripped_path.read_bytes()

        _LOGGER.warning("Fixture not found: %s", fixture_path)
        return None

    def get_content_type(self, path: str) -> str:
        """Get content type for a path.

        Args:
            path: URL path.

        Returns:
            MIME type string.
        """
        path_lower = path.lower()

        if path_lower.endswith(".css"):
            return "text/css"
        if path_lower.endswith(".js"):
            return "application/javascript"
        if path_lower.endswith(".json"):
            return "application/json"
        if path_lower.endswith(".xml"):
            return "application/xml"
        if path_lower.endswith((".jpg", ".jpeg")):
            return "image/jpeg"
        if path_lower.endswith(".png"):
            return "image/png"
        if path_lower.endswith(".gif"):
            return "image/gif"

        return "text/html; charset=utf-8"

    def create_session(self) -> str:
        """Create a new session.

        Returns:
            Session ID.
        """
        import uuid

        session_id = str(uuid.uuid4())
        self.sessions.add(session_id)
        return session_id

    def is_authenticated(self, headers: dict[str, str]) -> bool:
        """Check if request is authenticated.

        Args:
            headers: Request headers.

        Returns:
            True if authenticated.
        """
        cookie = headers.get("Cookie", "")
        return any(session_id in cookie for session_id in self.sessions)

    def apply_delay(self) -> None:
        """Apply response delay if configured.

        Simulates slow modem responses for timeout testing.
        """
        if self.response_delay > 0:
            _LOGGER.debug("Applying response delay: %.1fs", self.response_delay)
            time.sleep(self.response_delay)

    def serve_fixture(
        self,
        path: str,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Serve a fixture file.

        Args:
            path: URL path.
            extra_headers: Additional headers to include.

        Returns:
            Response tuple.
        """
        self.apply_delay()
        content = self.get_fixture_content(path)

        if content is None:
            return 404, {"Content-Type": "text/plain"}, b"Not Found"

        headers = {
            "Content-Type": self.get_content_type(path),
            "Content-Length": str(len(content)),
        }

        if extra_headers:
            headers.update(extra_headers)

        return 200, headers, content

    def parse_form_data(self, body: bytes) -> dict[str, str]:
        """Parse URL-encoded form data.

        Args:
            body: Request body.

        Returns:
            Dict of field name to value.
        """
        if not body:
            return {}

        try:
            decoded = body.decode("utf-8")
            parsed = parse_qs(decoded)
            # parse_qs returns lists, we want single values
            return {k: v[0] if v else "" for k, v in parsed.items()}
        except Exception:
            return {}
