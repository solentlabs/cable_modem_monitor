import logging
from bs4 import BeautifulSoup
from ..base_parser import ModemParser
from custom_components.cable_modem_monitor.lib.utils import extract_number, extract_float
from .generic import MotorolaGenericParser

_LOGGER = logging.getLogger(__name__)


class MotorolaMB7621Parser(MotorolaGenericParser):
    """Parser for the Motorola MB7621 cable modem."""

    name = "Motorola MB7621"
    manufacturer = "Motorola"
    models = ["MB7621"]
    priority = 100  # Model-specific parser, try before generic

    # MB7621 uses same URL patterns as generic, but we want to check
    # the software info page first to detect MB7621-specific strings
    url_patterns = [
        {"path": "/MotoSwInfo.asp", "auth_method": "form"},  # Has MB7621 model string
        {"path": "/MotoConnection.asp", "auth_method": "form"},
        {"path": "/MotoHome.asp", "auth_method": "form"},
    ]

    # Override specific methods or add MB7621-specific logic here if needed
    # For now, it inherits all logic from MotorolaGenericParser

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Motorola MB7621 modem."""
        # Check for MB7621-specific indicators in the HTML
        # The model string appears in various pages (like MotoSwInfo.asp)
        if "MB7621" in html or "MB 7621" in html or "2480-MB7621" in html:
            return True
        # MB7621 uses the same structure as generic Motorola, so it will
        # match the generic parser. Users should manually select MB7621.
        return False
