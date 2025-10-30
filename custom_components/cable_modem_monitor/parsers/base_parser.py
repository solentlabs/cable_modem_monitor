"""Base class for modem parsers."""
from abc import ABC, abstractmethod
from bs4 import BeautifulSoup


class ModemParser(ABC):
    """Abstract base class for modem-specific HTML parsers."""

    ***REMOVED*** Parser metadata (override in subclasses)
    name: str = "Unknown"
    manufacturer: str = "Unknown"
    models: list[str] = []  ***REMOVED*** e.g., ["MB7621", "MB8600"]

    ***REMOVED*** URL patterns this parser can handle
    ***REMOVED*** Each pattern is a dict with 'path' and 'auth_method'
    ***REMOVED*** auth_method can be: 'none', 'basic', 'form'
    ***REMOVED*** The scraper will try URLs in the order specified
    url_patterns: list[dict[str, str]] = []

    ***REMOVED*** Legacy field for backward compatibility (deprecated - use url_patterns)
    auth_type: str = 'form'

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
    def login(self, session, base_url, username, password) -> bool:
        """Log in to the modem."""
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

    