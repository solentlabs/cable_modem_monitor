"""Route builder — HAR entries to route table.

Pure data transformation. No HTTP, no auth, no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse


@dataclass
class RouteEntry:
    """A single route in the mock server.

    Attributes:
        status: HTTP status code to return.
        headers: Response headers as list of (name, value) tuples.
        body: Response body text.
    """

    status: int
    headers: list[tuple[str, str]] = field(default_factory=list)
    body: str = ""


def build_routes(
    har_entries: list[dict[str, Any]],
) -> dict[tuple[str, str], RouteEntry]:
    """Build route table from HAR entries.

    Each entry becomes a route keyed by ``(method, normalized_path)``.
    For duplicate keys, the last successful (status 200) response wins.
    Non-200 responses are stored only if no 200 exists for that route.

    Args:
        har_entries: List of HAR ``log.entries`` dicts.

    Returns:
        Route table mapping ``(method, path)`` to response.
    """
    routes: dict[tuple[str, str], RouteEntry] = {}

    for entry in har_entries:
        request = entry.get("request", {})
        response = entry.get("response", {})

        method = request.get("method", "GET").upper()
        url = request.get("url", "")
        path = normalize_path(urlparse(url).path)
        if not path:
            continue

        status = response.get("status", 0)
        headers = _extract_headers(response)
        body = _extract_body(response)

        key = (method, path)
        existing = routes.get(key)

        # Prefer 200 responses; for non-200, only store if no entry yet
        if existing is None or status == 200:
            routes[key] = RouteEntry(status=status, headers=headers, body=body)

    return routes


def normalize_path(path: str) -> str:
    """Normalize a URL path for consistent route matching.

    Ensures a leading slash. Trailing slashes are preserved.
    """
    if not path:
        return ""
    if not path.startswith("/"):
        path = "/" + path
    return path


def _extract_headers(response: dict[str, Any]) -> list[tuple[str, str]]:
    """Extract response headers from a HAR response dict."""
    headers: list[tuple[str, str]] = []
    for h in response.get("headers", []):
        name = h.get("name", "")
        value = h.get("value", "")
        if name:
            headers.append((name, value))
    return headers


def _extract_body(response: dict[str, Any]) -> str:
    """Extract response body text from a HAR response dict."""
    content = response.get("content", {})
    return str(content.get("text", ""))
