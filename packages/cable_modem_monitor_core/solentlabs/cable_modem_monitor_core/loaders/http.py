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
_HTML_FORMATS = frozenset({"table", "table_transposed", "javascript", "javascript_json", "html_fields"})

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
        token_prefix: Token prefix from ``auth.token_prefix``
            (e.g., ``ct_``).
        detect_login_pages: When True, check HTML responses for login
            page indicators (``<input type="password">``). Raises
            ``LoginPageDetectedError`` if detected. Enable for
            form-based auth strategies where the modem silently serves
            a login page at data URLs when the session expires.
    """

    def __init__(
        self,
        session: requests.Session,
        base_url: str,
        timeout: int = 10,
        url_token: str = "",
        token_prefix: str = "",
        detect_login_pages: bool = False,
        model: str = "",
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._url_token = url_token
        self._token_prefix = token_prefix
        self._detect_login_pages = detect_login_pages
        self._model = model

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
                    "Reusing auth response for %s [%s]",
                    target.path,
                    self._model,
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

            _logger.debug(
                "Fetched %s [%s]: %d (%d bytes)",
                target.path,
                self._model,
                response.status_code,
                len(response.content),
            )

            if response.status_code in (401, 403):
                raise ResourceLoadError(
                    f"HTTP {response.status_code} on {target.path}" " — session likely expired",
                    status_code=response.status_code,
                    path=target.path,
                )

            if response.status_code >= 400:
                raise ResourceLoadError(
                    f"HTTP {response.status_code} fetching {target.path}",
                    status_code=response.status_code,
                    path=target.path,
                )

            # Login page detection — data pages should never contain
            # a password input field. If one is present, the modem
            # silently served a login page instead of data (session
            # expired with HTTP 200).
            if (
                self._detect_login_pages
                and response.status_code == 200
                and target.format in _HTML_FORMATS
                and _is_login_page(response.text)
            ):
                _logger.warning(
                    "Data page %s appears to be a login page",
                    target.path,
                )
                raise LoginPageDetectedError(target.path)

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
    """A resource could not be fetched from the modem.

    Attributes:
        status_code: HTTP status code if the error was an HTTP response.
            None for connection/timeout errors.
        path: Resource path that failed (e.g., "/status.html").
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        path: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.path = path


class LoginPageDetectedError(ResourceLoadError):
    """Data page response contains login form indicators.

    The modem served a login page at a data URL -- the session has
    expired silently (HTTP 200, but body is a login form instead of
    data). Maps to CollectorSignal.LOAD_AUTH.
    """

    def __init__(self, path: str) -> None:
        super().__init__(
            f"Data page {path} appears to be a login page",
            status_code=200,
            path=path,
        )


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


def _is_login_page(text: str) -> bool:
    """Check if an HTML response contains login form indicators.

    Data pages from parser.yaml (status, connection, channel info)
    do not contain password input fields. Login pages always do.
    This invariant enables login page detection without
    modem-specific configuration.

    See RESOURCE_LOADING_SPEC.md Login Page Detection section.
    """
    lower = text.lower()
    return 'type="password"' in lower or "type='password'" in lower
