"""Base class for modem parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.core.auth_config import AuthConfig


class ModemParser(ABC):
    """Abstract base class for modem-specific HTML parsers."""

    # Parser metadata (override in subclasses)
    name: str = "Unknown"
    manufacturer: str = "Unknown"
    models: list[str] = []  # e.g., ["MB7621", "MB8600"]

    # Priority for parser selection (higher = tried first)
    # Use 100 for model-specific parsers, 50 for generic/fallback parsers
    # Default is 50 for backward compatibility
    priority: int = 50

    # URL patterns this parser can handle
    # Each pattern is a dict with 'path' and optionally 'auth_required'
    # auth_required: boolean (default True) - if False, can try without auth
    # The scraper will try URLs in the order specified
    url_patterns: list[dict[str, str | bool]] = []

    # Legacy field for backward compatibility (deprecated - use url_patterns)
    auth_type: str = "form"

    # Authentication configuration (new system - optional, for backward compatibility)
    # Parsers should define this as a class attribute
    auth_config: AuthConfig | None = None

    @classmethod
    @abstractmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """
        Detect if this parser can handle the modem's HTML.

        Args:
            soup: BeautifulSoup parsed HTML
            url: The URL that returned this HTML
            html: Raw HTML string

        Returns:
            True if this parser can handle this modem, False otherwise

        Example:
            return soup.find(string="Motorola Cable Modem") is not None
        """
        raise NotImplementedError

    @abstractmethod
    def login(self, session, base_url, username, password) -> bool | tuple[bool, str | None]:
        """
        Log in to the modem.

        Returns:
            bool: True if login successful (old style)
            tuple[bool, str | None]: (success, html) where html is authenticated page content
                                     or None if no credentials provided or login failed
        """
        raise NotImplementedError

    @abstractmethod
    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """
        Parse all data from the modem.

        Args:
            soup: BeautifulSoup object of the main page
            session: Optional requests.Session for fetching additional pages
            base_url: Optional base URL of the modem (e.g., "http://192.168.100.1")

        Returns:
            Dict with all parsed data:
            {
                "downstream": [],
                "upstream": [],
                "system_info": {},
            }
        """
        raise NotImplementedError
