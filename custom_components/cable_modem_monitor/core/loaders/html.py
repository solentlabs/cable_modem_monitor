"""HTML page loader for modem web interfaces.

Handles loading HTML pages from cable modem web interfaces, including:
- Standard HTTP GET requests
- URL token authentication (SB8200-style)
- Multi-page loading based on modem.yaml pages.data
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup

from ..auth.base import get_cookie_safe
from .base import ResourceLoader

if TYPE_CHECKING:
    import requests

_LOGGER = logging.getLogger(__name__)


class HTMLLoader(ResourceLoader):
    """Fetcher for HTML-based modem web interfaces.

    Handles fetching HTML pages and parsing them into BeautifulSoup objects.
    Supports URL token authentication for modems like the SB8200 that require
    session tokens in the URL query string.

    Attributes:
        url_token_config: Configuration for URL token auth (if applicable)
    """

    def __init__(
        self,
        session: requests.Session,
        base_url: str,
        modem_config: dict[str, Any],
        verify_ssl: bool = False,
        url_token_config: dict[str, str] | None = None,
    ):
        """Initialize the HTML fetcher.

        Args:
            session: Authenticated requests.Session
            base_url: Modem base URL
            modem_config: Modem configuration from modem.yaml
            verify_ssl: Whether to verify SSL certificates
            url_token_config: URL token auth config (from modem.yaml auth.url_token):
                - session_cookie: Cookie name containing session token
                - token_prefix: Prefix for token in URL (e.g., "ct_")
        """
        super().__init__(session, base_url, modem_config, verify_ssl)
        self._url_token_config = url_token_config

    def fetch(self) -> dict[str, Any]:
        """Fetch all HTML pages declared in modem.yaml pages.data.

        Returns:
            Dict mapping paths to BeautifulSoup objects, e.g.:
            {
                "/cmconnectionstatus.html": <BeautifulSoup>,
                "/cmswinfo.html": <BeautifulSoup>,
            }
        """
        resources: dict[str, Any] = {}
        timeout = self._get_timeout()

        for path in self._get_unique_paths():
            # Skip HNAP endpoints - those are handled by HNAPFetcher
            if "/HNAP" in path.upper():
                _LOGGER.debug("HTMLLoader skipping HNAP endpoint: %s", path)
                continue

            try:
                url = self._build_authenticated_url(path)
                _LOGGER.debug("HTMLLoader fetching: %s", url)

                response = self.session.get(url, timeout=timeout, verify=self.verify_ssl)

                if response.ok:
                    soup = BeautifulSoup(response.text, "html.parser")
                    resources[path] = soup
                    _LOGGER.debug(
                        "HTMLLoader fetched %s (%d bytes)",
                        path,
                        len(response.text),
                    )
                else:
                    _LOGGER.warning(
                        "HTMLLoader failed to fetch %s: status %d",
                        path,
                        response.status_code,
                    )
            except Exception as e:
                _LOGGER.warning("HTMLLoader error fetching %s: %s", path, e)

        return resources

    def _build_authenticated_url(self, path: str) -> str:
        """Build URL with session token if URL token auth is configured.

        For SB8200-style auth, the session token must be appended to each URL
        as a query parameter (e.g., ?ct_<token>).

        Args:
            path: Path to request (e.g., "/cmswinfo.html")

        Returns:
            Full URL with token appended if applicable
        """
        url = f"{self.base_url}{path}"

        if not self._url_token_config:
            _LOGGER.debug("HTMLLoader: No url_token_config, skipping token append")
            return url

        # Get session token from cookies
        cookie_name = self._url_token_config.get("session_cookie", "sessionId")
        token = get_cookie_safe(self.session, cookie_name)

        if not token:
            _LOGGER.debug(
                "HTMLLoader: No token found in cookie '%s' (cookies: %s)",
                cookie_name,
                list(self.session.cookies.keys()),
            )
            return url

        prefix = self._url_token_config.get("token_prefix", "ct_")
        # Handle URLs that already have query params
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{prefix}{token}"
        _LOGGER.debug("HTMLLoader appended token to URL: %s", path)

        return url
