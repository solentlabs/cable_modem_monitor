from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from ..base_parser import ModemCapability
from .generic import MotorolaGenericParser

_LOGGER = logging.getLogger(__name__)


class MotorolaMB7621Parser(MotorolaGenericParser):
    """Parser for the Motorola MB7621 cable modem."""

    name = "Motorola MB7621"
    manufacturer = "Motorola"
    models = ["MB7621"]
    priority = 100  # Model-specific parser, try before generic

    # Verification status
    verified = True
    verification_source = "kwschulz (maintainer's personal modem)"

    # Device metadata
    release_date = "2017"
    docsis_version = "3.0"
    fixtures_path = "tests/parsers/motorola/fixtures/mb7621"

    # Capabilities - inherits from generic, explicitly declared for clarity
    capabilities = {
        ModemCapability.DOWNSTREAM_CHANNELS,
        ModemCapability.UPSTREAM_CHANNELS,
        ModemCapability.SYSTEM_UPTIME,
        ModemCapability.SOFTWARE_VERSION,
        ModemCapability.RESTART,
    }

    # MB7621 uses same URL patterns as generic, but we want to check
    # the software info page first to detect MB7621-specific strings
    url_patterns = [
        {
            "path": "/MotoSwInfo.asp",
            "auth_method": "form",
            "auth_required": False,
        },  # Has MB7621 model string, publicly accessible
        {"path": "/MotoConnection.asp", "auth_method": "form", "auth_required": True},
        {"path": "/MotoHome.asp", "auth_method": "form", "auth_required": True},
    ]

    # Override specific methods or add MB7621-specific logic here if needed
    # For now, it inherits all logic from MotorolaGenericParser

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Motorola MB7621 modem."""
        # Check for MB7621-specific indicators in the HTML
        # The model string appears in various pages (like MotoSwInfo.asp)
        return "MB7621" in html or "MB 7621" in html or "2480-MB7621" in html
