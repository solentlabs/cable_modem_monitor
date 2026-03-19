"""HTTP resource loader — fetch pages and build resource dict.

Uses an authenticated ``requests.Session`` to fetch data pages from a
modem. Each response is decoded based on the format declared in
parser.yaml (HTML → BeautifulSoup, JSON → dict).

See RESOURCE_LOADING_SPEC.md.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import requests
from bs4 import BeautifulSoup

from ..auth.base import AuthResult
from .fetch_list import ResourceTarget

_logger = logging.getLogger(__name__)

# Formats decoded as HTML (BeautifulSoup)
_HTML_FORMATS = frozenset({"table", "table_transposed", "javascript", "html_fields"})

# Formats decoded as structured data (dict)
_STRUCTURED_FORMATS = frozenset({"json", "xml"})


class HTTPResourceLoader:
    """Fetch resources from a modem's HTTP interface.

    Given an authenticated session and a list of resource targets
    (derived from parser.yaml), fetches each page and decodes the
    response based on format. Deduplicates by path. Reuses the auth
    response if it landed on a data page.

    Args:
        session: Authenticated ``requests.Session``.
        base_url: Modem base URL (e.g., ``http://192.168.100.1``).
        timeout: Per-request timeout in seconds.
        url_token: URL token for ``url_token`` auth (empty for other
            strategies).
        token_prefix: Token prefix from ``session.token_prefix``
            (e.g., ``ct_``).
    """

    def __init__(
        self,
        session: requests.Session,
        base_url: str,
        timeout: int = 10,
        url_token: str = "",
        token_prefix: str = "",
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._url_token = url_token
        self._token_prefix = token_prefix

    def fetch(
        self,
        targets: list[ResourceTarget],
        auth_result: AuthResult | None = None,
    ) -> dict[str, Any]:
        """Fetch all resource targets and return the resource dict.

        Args:
            targets: List of resources to fetch (from
                ``collect_fetch_targets``).
            auth_result: Auth result for response reuse. If the login
                response landed on a page in the target list, its body
                is reused instead of re-fetching.

        Returns:
            Resource dict keyed by URL path. Values are
            ``BeautifulSoup`` for HTML formats, ``dict`` for
            structured formats.

        Raises:
            ResourceLoadError: If a required page cannot be fetched.
        """
        resources: dict[str, Any] = {}

        # Check for auth response reuse
        reuse_path = ""
        reuse_response: requests.Response | None = None
        if auth_result and auth_result.response and auth_result.response_url:
            reuse_path = auth_result.response_url
            reuse_response = auth_result.response

        for target in targets:
            # Auth response reuse — skip fetch if login landed here
            if reuse_path and reuse_response and target.path == reuse_path:
                _logger.debug(
                    "Reusing auth response for %s",
                    target.path,
                )
                decoded = _decode_response(
                    reuse_response.text,
                    target.format,
                    target.encoding,
                )
                if decoded is not None:
                    resources[target.path] = decoded
                continue

            # Fetch the page
            url = self._build_url(target.path)
            try:
                response = self._session.get(url, timeout=self._timeout)
            except requests.RequestException as e:
                raise ResourceLoadError(
                    f"Failed to fetch {target.path}: {e}",
                ) from e

            if response.status_code == 401:
                raise ResourceLoadError(
                    f"Auth failed fetching {target.path}: 401 Unauthorized " f"(session may have expired)",
                )

            if response.status_code >= 400:
                raise ResourceLoadError(
                    f"HTTP {response.status_code} fetching {target.path}",
                )

            decoded = _decode_response(
                response.text,
                target.format,
                target.encoding,
            )
            if decoded is not None:
                resources[target.path] = decoded
            else:
                _logger.warning(
                    "Empty or undecoded response for %s (format=%s)",
                    target.path,
                    target.format,
                )

        return resources

    def _build_url(self, path: str) -> str:
        """Build the full URL for a resource path.

        Appends URL token if configured (for ``url_token`` auth).
        """
        url = f"{self._base_url}{path}"
        if self._url_token and self._token_prefix:
            url = f"{url}?{self._token_prefix}{self._url_token}"
        return url


class ResourceLoadError(Exception):
    """A resource could not be fetched from the modem."""


def _decode_response(
    text: str,
    fmt: str,
    encoding: str,
) -> Any:
    """Decode a response body based on format and encoding.

    Args:
        text: Raw response body text.
        fmt: Format from parser.yaml (``table``, ``json``, etc.).
        encoding: Optional encoding (``base64`` or empty).

    Returns:
        Decoded value (``BeautifulSoup`` or ``dict``), or ``None``
        if the response is empty.
    """
    if not text:
        return None

    # Handle base64 encoding on response body
    if encoding == "base64":
        try:
            text = base64.b64decode(text).decode("utf-8", errors="replace")
        except Exception:
            _logger.debug("Failed to base64-decode response")
            return None

    if fmt in _HTML_FORMATS:
        return BeautifulSoup(text, "html.parser")

    if fmt in _STRUCTURED_FORMATS:
        if fmt == "json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                _logger.warning("Response is not valid JSON")
                return None
            if not isinstance(data, dict):
                return {"_raw": data}
            return data

        if fmt == "xml":
            _logger.warning("XML format not yet supported by loader")
            return None

    _logger.warning("Unknown format '%s', returning as BeautifulSoup", fmt)
    return BeautifulSoup(text, "html.parser")
