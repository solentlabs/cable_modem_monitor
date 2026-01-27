"""Base class for resource loaders.

Resource loaders handle all HTTP/API calls for a modem. They abstract away:
- URL building (including auth token injection)
- Protocol-specific calls (HTML GET, HNAP SOAP, REST API)
- Response parsing (HTML to BeautifulSoup, JSON to dict)

This keeps parsers focused purely on data extraction.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import requests

_LOGGER = logging.getLogger(__name__)


class ResourceLoader(ABC):
    """Abstract base class for resource loaders.

    Loaders are responsible for loading all resources declared in modem.yaml
    and returning them in a format suitable for parsers.

    Attributes:
        session: Authenticated requests.Session
        base_url: Modem base URL (e.g., "http://192.168.100.1")
        modem_config: Modem configuration from modem.yaml
        verify_ssl: Whether to verify SSL certificates
    """

    def __init__(
        self,
        session: requests.Session,
        base_url: str,
        modem_config: dict[str, Any],
        verify_ssl: bool = False,
    ):
        """Initialize the resource loader.

        Args:
            session: Authenticated requests.Session
            base_url: Modem base URL
            modem_config: Modem configuration dict from modem.yaml
            verify_ssl: Whether to verify SSL certificates
        """
        self.session = session
        self.base_url = base_url
        self.modem_config = modem_config
        self.verify_ssl = verify_ssl

    @abstractmethod
    def fetch(self) -> dict[str, Any]:
        """Fetch all resources declared in modem.yaml.

        Returns:
            Dict mapping resource identifiers to content:
            - HTML pages: path -> BeautifulSoup
            - JSON endpoints: path -> dict
            - HNAP actions: action_name -> response dict
        """
        raise NotImplementedError

    def _get_pages_data(self) -> dict[str, str]:
        """Get pages.data from modem.yaml config.

        Returns:
            Dict mapping data types to paths, e.g.:
            {"downstream_channels": "/MotoConnection.asp", ...}
        """
        pages: dict[str, Any] = self.modem_config.get("pages", {})
        result: dict[str, str] = pages.get("data", {})
        return result

    def _get_unique_paths(self) -> set[str]:
        """Get unique paths from pages.data.

        Returns:
            Set of unique paths to fetch
        """
        pages_data = self._get_pages_data()
        return set(pages_data.values())

    def _get_timeout(self) -> int:
        """Get request timeout from modem config.

        Returns:
            Timeout in seconds (from modem.yaml)

        Raises:
            KeyError: If timeout is missing from modem_config (indicates schema issue)
        """
        if "timeout" not in self.modem_config:
            raise KeyError("timeout not found in modem_config - check schema defaults")
        timeout: int = self.modem_config["timeout"]
        return timeout
