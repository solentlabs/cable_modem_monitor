"""REST API loader for modem JSON endpoints.

Handles loading data from REST API-based cable modems (SuperHub5) that
expose JSON endpoints.
"""

from __future__ import annotations

import logging
from typing import Any

from .base import ResourceLoader

_LOGGER = logging.getLogger(__name__)


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
                url = f"{self.base_url}{path}"
                _LOGGER.debug("RESTLoader fetching: %s", url)

                response = self.session.get(url, timeout=timeout, verify=self.verify_ssl)

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
