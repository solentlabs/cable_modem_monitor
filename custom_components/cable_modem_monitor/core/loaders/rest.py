"""REST API loader for modem JSON endpoints.

Handles loading data from REST API-based cable modems (SuperHub5) that
expose JSON endpoints.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING
from typing import Any

from .base import ResourceLoader

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    import requests


class RESTLoader(ResourceLoader):
    """Fetcher for REST API-based modem interfaces.

    Some modems (SuperHub5) expose REST APIs with JSON responses instead of
    HTML pages. This fetcher handles fetching and parsing those endpoints.

    The endpoints are declared in modem.yaml pages.data, same as HTML pages,
    but the response is parsed as JSON instead of HTML.
    """

    def fetch(self) -> dict[str, Any]:
        """Fetch all JSON endpoints declared in modem.yaml pages.data.

        Returns:
            Dict mapping paths to parsed JSON objects, e.g.:
            {
                "/rest/v1/cablemodem/downstream": {"channels": [...]},
                "/rest/v1/cablemodem/upstream": {"channels": [...]},
                "/rest/v1/cablemodem/state_": {"cablemodem": {...}},
            }
        """
        resources: dict[str, Any] = {}
        timeout = self._get_timeout()

        for path in self._get_unique_paths():
            try:
                self._set_api_session_cookies(path)
                url = self._build_url(path)
                _LOGGER.debug("RESTLoader fetching: %s", url)

                response = self.session.get(
                    url,
                    headers=self._build_headers(path),
                    timeout=timeout,
                    verify=self.verify_ssl,
                )

                if response.ok:
                    try:
                        data = response.json()
                        resources[path] = data
                        _LOGGER.debug(
                            "RESTLoader fetched %s: %d keys",
                            path,
                            len(data) if isinstance(data, dict) else 1,
                        )
                    except ValueError as e:
                        _LOGGER.warning(
                            "RESTLoader failed to parse JSON from %s: %s",
                            path,
                            e,
                        )
                else:
                    _LOGGER.warning(
                        "RESTLoader failed to fetch %s: status %d",
                        path,
                        response.status_code,
                    )
            except Exception as e:
                _LOGGER.warning("RESTLoader error fetching %s: %s", path, e)

        return resources

    def _build_headers(self, path: str) -> dict[str, str]:
        """Build headers for REST requests."""
        referer = self.base_url if self.base_url.endswith("/") else f"{self.base_url}/"
        headers = {"Referer": referer, "Accept": "*/*"}

        # Technicolor-style JSON APIs commonly require AJAX header.
        if "/api/" in path:
            headers["X-Requested-With"] = "XMLHttpRequest"

        return headers

    def _build_url(self, path: str) -> str:
        """Build request URL, adding cache-busting timestamp for API endpoints."""
        url = f"{self.base_url}{path}"
        if "/api/" not in path:
            return url

        separator = "&" if "?" in url else "?"
        return f"{url}{separator}_={int(time.time() * 1000)}"

    def _set_api_session_cookies(self, path: str) -> None:
        """Set browser-like cookies commonly required by Technicolor APIs."""
        if "/api/" not in path:
            return
        self.session.cookies.set("theme-value", "css/theme/dark/", path="/")
        self.session.cookies.set("time", str(int(time.time())), path="/")
