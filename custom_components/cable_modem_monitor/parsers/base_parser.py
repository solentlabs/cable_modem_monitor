"""Base class for modem parsers."""
from abc import ABC, abstractmethod
from typing import Optional
from bs4 import BeautifulSoup


class ModemParser(ABC):
    """Abstract base class for modem-specific HTML parsers."""

    # Parser metadata (override in subclasses)
    name: str = "Unknown"
    manufacturer: str = "Unknown"
    models: list[str] = []  # e.g., ["MB7621", "MB8600"]

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
    def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """
        Parse downstream channel data.

        Returns:
            List of dicts, each representing one downstream channel:
            [
                {
                    "channel_id": "1",
                    "frequency": 591000000,  # Hz
                    "power": 5.2,            # dBmV
                    "snr": 40.5,             # dB
                    "modulation": "QAM256",  # optional
                    "corrected": 123,        # optional
                    "uncorrected": 0,        # optional
                },
                ...
            ]
        """
        raise NotImplementedError

    @abstractmethod
    def parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """
        Parse upstream channel data.

        Returns:
            List of dicts, each representing one upstream channel:
            [
                {
                    "channel_id": "1",
                    "frequency": 36500000,  # Hz
                    "power": 42.0,          # dBmV
                    "modulation": "QPSK",   # optional
                },
                ...
            ]
        """
        raise NotImplementedError

    def parse_system_info(self, soup: BeautifulSoup) -> dict:
        """
        Parse system information (optional).

        Returns:
            Dict with optional fields:
            {
                "software_version": "1.0.0.15",
                "hardware_version": "v1.0",
                "system_uptime": "5 days, 3 hours",
                "downstream_channel_count": 24,
                "upstream_channel_count": 4,
            }
        """
        return {}

    def validate_downstream(self, channel: dict) -> bool:
        """
        Validate a downstream channel dict.
        Override if parser has special validation needs.

        Args:
            channel: Channel dict to validate

        Returns:
            True if channel is valid, False otherwise
        """
        required = ["channel_id", "frequency", "power", "snr"]
        return all(
            field in channel and channel[field] is not None for field in required
        )

    def validate_upstream(self, channel: dict) -> bool:
        """
        Validate an upstream channel dict.
        Override if parser has special validation needs.

        Args:
            channel: Channel dict to validate

        Returns:
            True if channel is valid, False otherwise
        """
        # Require channel_id and power, but frequency is optional
        # (some modems don't report upstream frequency)
        return (
            "channel_id" in channel
            and channel["channel_id"] is not None
            and "power" in channel
            and channel["power"] is not None
        )
