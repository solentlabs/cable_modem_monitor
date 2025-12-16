"""Base class for modem parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.core.auth_config import AuthConfig


class ParserStatus(str, Enum):
    """Parser verification/lifecycle status.

    Tracks where a parser is in its development and validation lifecycle:

    IN_PROGRESS: Parser is actively being developed (not yet released).
                 Use for parsers in feature branches or WIP PRs.

    AWAITING_VERIFICATION: Parser released but awaiting user confirmation.
                           Use after merging, before first user report.

    VERIFIED: Parser confirmed working by at least one user.
              Should have verification_source set to issue/forum link.

    BROKEN: Parser has known issues that prevent normal operation.
            Should have verification_source explaining the problem.

    DEPRECATED: Parser is being phased out (e.g., superseded by better impl).
    """

    IN_PROGRESS = "in_progress"
    AWAITING_VERIFICATION = "awaiting_verification"
    VERIFIED = "verified"
    BROKEN = "broken"
    DEPRECATED = "deprecated"


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

    # System information
    SYSTEM_UPTIME = "system_uptime"
    LAST_BOOT_TIME = "last_boot_time"
    CURRENT_TIME = "current_time"
    HARDWARE_VERSION = "hardware_version"
    SOFTWARE_VERSION = "software_version"

    # Channel data
    DOWNSTREAM_CHANNELS = "downstream_channels"
    UPSTREAM_CHANNELS = "upstream_channels"
    OFDM_DOWNSTREAM = "ofdm_downstream"
    OFDM_UPSTREAM = "ofdm_upstream"

    # Actions
    RESTART = "restart"


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

    # Parser lifecycle status - defaults to AWAITING_VERIFICATION for new parsers
    # Use ParserStatus.VERIFIED after user confirmation, BROKEN for known issues
    status: ParserStatus = ParserStatus.AWAITING_VERIFICATION
    # Optional: Link to issue, forum post, or commit for verification/status
    verification_source: str | None = None

    @property
    def verified(self) -> bool:
        """Backward compatibility: True if status is VERIFIED."""
        return self.status == ParserStatus.VERIFIED

    # Device metadata - for display and mock server
    # Format: "YYYY-MM" or "YYYY" for approximate dates
    release_date: str | None = None  # When modem was first released
    end_of_life: str | None = None  # When discontinued (if applicable)
    docsis_version: str | None = None  # e.g., "3.0", "3.1"
    # Relative path to fixtures in repo (used by mock server and for docs link)
    # e.g., "tests/parsers/netgear/fixtures/c3700"
    fixtures_path: str | None = None

    # Modem network behavior - whether the modem responds to ICMP ping
    # Set to False for modems that block ICMP (e.g., Arris S33)
    # When False: ping check is skipped, health status uses HTTP only,
    # and the Ping Latency sensor is not created
    supports_icmp: bool = True

    # URL patterns this parser can handle.
    #
    # DETECTION CONTRACT:
    # For auto-detection to work, at least one pattern must have 'auth_required': False
    # pointing to a publicly accessible page containing model-identifying strings.
    # Pages requiring auth are invisible to the anonymous probing phase.
    #
    # Each pattern is a dict with:
    #   - 'path': URL path (e.g., "/MotoSwInfo.asp")
    #   - 'auth_method': Authentication method ("none", "basic", "form", "hnap")
    #   - 'auth_required': REQUIRED - explicitly set True or False (no implicit defaults!)
    #
    # Order matters: Put your detection page first if it's publicly accessible.
    # The scraper tries URLs in the order specified.
    #
    # See: tests/parsers/test_parser_contract.py for validation
    url_patterns: list[dict[str, str | bool]] = []

    # Legacy field for backward compatibility (deprecated - use url_patterns)
    auth_type: str = "form"

    # Authentication configuration (new system - optional, for backward compatibility)
    # Parsers should define this as a class attribute
    auth_config: AuthConfig | None = None

    # Capabilities declaration - what data this parser can provide
    # Override in subclasses to declare supported capabilities
    # Format: set of ModemCapability enum values
    # Example: capabilities = {ModemCapability.DOWNSTREAM_CHANNELS, ModemCapability.SYSTEM_UPTIME}
    capabilities: set[ModemCapability] = set()

    # GitHub repo base URL for fixtures links
    GITHUB_REPO_URL = "https://github.com/solentlabs/cable_modem_monitor"

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
            "status": cls.status.value,
            "verified": cls.status == ParserStatus.VERIFIED,  # Backward compat
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

        # Add capabilities as list of strings
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
            # No auth required:
            return (True, None)

            # Form auth that returns HTML:
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
