"""Base class for modem parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.core.auth_config import AuthConfig


class ModemCapability(str, Enum):
    """Standardized capability names for modem parsers.

    These are the common field names that parsers can declare support for.
    The integration uses these to conditionally create entities.

    System Information:
        SYSTEM_UPTIME: Current uptime string (e.g., "7 days 00:00:01")
        LAST_BOOT_TIME: Calculated boot timestamp (ISO format)
        CURRENT_TIME: Current system time from modem
        HARDWARE_VERSION: Hardware/board version
        SOFTWARE_VERSION: Firmware/software version

    Channel Data:
        DOWNSTREAM_CHANNELS: DOCSIS 3.0 downstream channels
        UPSTREAM_CHANNELS: DOCSIS 3.0 upstream channels
        OFDM_DOWNSTREAM: DOCSIS 3.1 OFDM downstream channels
        OFDM_UPSTREAM: DOCSIS 3.1 OFDM upstream channels

    Actions:
        RESTART: Modem can be restarted via the integration
    """

    ***REMOVED*** System information
    SYSTEM_UPTIME = "system_uptime"
    LAST_BOOT_TIME = "last_boot_time"
    CURRENT_TIME = "current_time"
    HARDWARE_VERSION = "hardware_version"
    SOFTWARE_VERSION = "software_version"

    ***REMOVED*** Channel data
    DOWNSTREAM_CHANNELS = "downstream_channels"
    UPSTREAM_CHANNELS = "upstream_channels"
    OFDM_DOWNSTREAM = "ofdm_downstream"
    OFDM_UPSTREAM = "ofdm_upstream"

    ***REMOVED*** Actions
    RESTART = "restart"


class ModemParser(ABC):
    """Abstract base class for modem-specific HTML parsers."""

    ***REMOVED*** Parser metadata (override in subclasses)
    name: str = "Unknown"
    manufacturer: str = "Unknown"
    models: list[str] = []  ***REMOVED*** e.g., ["MB7621", "MB8600"]

    ***REMOVED*** Priority for parser selection (higher = tried first)
    ***REMOVED*** Use 100 for model-specific parsers, 50 for generic/fallback parsers
    ***REMOVED*** Default is 50 for backward compatibility
    priority: int = 50

    ***REMOVED*** Verification status - defaults to False until confirmed by real user
    ***REMOVED*** Set to True only after verification by maintainer or user report
    verified: bool = False
    ***REMOVED*** Optional: Link to issue, forum post, or commit confirming verification
    verification_source: str | None = None

    ***REMOVED*** Device metadata - for display and mock server
    ***REMOVED*** Format: "YYYY-MM" or "YYYY" for approximate dates
    release_date: str | None = None  ***REMOVED*** When modem was first released
    end_of_life: str | None = None  ***REMOVED*** When discontinued (if applicable)
    docsis_version: str | None = None  ***REMOVED*** e.g., "3.0", "3.1"
    ***REMOVED*** Relative path to fixtures in repo (used by mock server and for docs link)
    ***REMOVED*** e.g., "tests/parsers/netgear/fixtures/c3700"
    fixtures_path: str | None = None

    ***REMOVED*** URL patterns this parser can handle
    ***REMOVED*** Each pattern is a dict with 'path' and optionally 'auth_required'
    ***REMOVED*** auth_required: boolean (default True) - if False, can try without auth
    ***REMOVED*** The scraper will try URLs in the order specified
    url_patterns: list[dict[str, str | bool]] = []

    ***REMOVED*** Legacy field for backward compatibility (deprecated - use url_patterns)
    auth_type: str = "form"

    ***REMOVED*** Authentication configuration (new system - optional, for backward compatibility)
    ***REMOVED*** Parsers should define this as a class attribute
    auth_config: AuthConfig | None = None

    ***REMOVED*** Capabilities declaration - what data this parser can provide
    ***REMOVED*** Override in subclasses to declare supported capabilities
    ***REMOVED*** Format: set of ModemCapability enum values
    ***REMOVED*** Example: capabilities = {ModemCapability.DOWNSTREAM_CHANNELS, ModemCapability.SYSTEM_UPTIME}
    capabilities: set[ModemCapability] = set()

    ***REMOVED*** GitHub repo base URL for fixtures links
    GITHUB_REPO_URL = "https://github.com/kwschulz/cable_modem_monitor"

    @classmethod
    def has_capability(cls, capability: ModemCapability) -> bool:
        """Check if this parser supports a specific capability.

        Args:
            capability: The ModemCapability to check for

        Returns:
            True if the parser declares support for this capability
        """
        return capability in cls.capabilities

    @classmethod
    def get_fixtures_url(cls) -> str | None:
        """Get the GitHub URL for this parser's fixtures.

        Returns:
            Full GitHub URL to fixtures directory, or None if not available
        """
        if cls.fixtures_path:
            return f"{cls.GITHUB_REPO_URL}/tree/main/{cls.fixtures_path}"
        return None

    @classmethod
    def get_device_metadata(cls) -> dict:
        """Get device metadata for display and mock server.

        Returns:
            Dictionary with all available device metadata
        """
        metadata = {
            "name": cls.name,
            "manufacturer": cls.manufacturer,
            "models": cls.models,
            "verified": cls.verified,
            "docsis_version": cls.docsis_version,
        }

        if cls.release_date:
            metadata["release_date"] = cls.release_date
        if cls.end_of_life:
            metadata["end_of_life"] = cls.end_of_life
        if cls.fixtures_path:
            metadata["fixtures_path"] = cls.fixtures_path
            metadata["fixtures_url"] = cls.get_fixtures_url()
        if cls.verification_source:
            metadata["verification_source"] = cls.verification_source

        ***REMOVED*** Add capabilities as list of strings
        metadata["capabilities"] = [cap.value for cap in cls.capabilities]

        return metadata

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
    def login(self, session, base_url, username, password) -> tuple[bool, str | None]:
        """
        Log in to the modem.

        Returns:
            tuple[bool, str | None]: (success, authenticated_html)
                - success: True if login succeeded or no login required
                - authenticated_html: HTML content from login response, or None if not applicable

        Example implementations:
            ***REMOVED*** No auth required:
            return (True, None)

            ***REMOVED*** Form auth that returns HTML:
            response = session.post(url, data=credentials)
            return (response.ok, response.text if response.ok else None)
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
