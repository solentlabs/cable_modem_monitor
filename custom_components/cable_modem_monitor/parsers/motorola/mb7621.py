import logging
from bs4 import BeautifulSoup
from .generic import MotorolaGenericParser

_LOGGER = logging.getLogger(__name__)


class MotorolaMB7621Parser(MotorolaGenericParser):
    """Parser for the Motorola MB7621 cable modem."""

    name = "Motorola MB7621"
    manufacturer = "Motorola"
    models = ["MB7621"]
    priority = 100  ***REMOVED*** Model-specific parser, try before generic

    ***REMOVED*** MB7621 uses same URL patterns as generic, but we want to check
    ***REMOVED*** the software info page first to detect MB7621-specific strings
    url_patterns = [
        {"path": "/MotoSwInfo.asp", "auth_method": "form"},  ***REMOVED*** Has MB7621 model string
        {"path": "/MotoConnection.asp", "auth_method": "form"},
        {"path": "/MotoHome.asp", "auth_method": "form"},
    ]

    ***REMOVED*** Override specific methods or add MB7621-specific logic here if needed
    ***REMOVED*** For now, it inherits all logic from MotorolaGenericParser

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Motorola MB7621 modem."""
        ***REMOVED*** Check for MB7621-specific indicators in the HTML
        ***REMOVED*** The model string appears in various pages (like MotoSwInfo.asp)
        if "MB7621" in html or "MB 7621" in html or "2480-MB7621" in html:
            return True
        ***REMOVED*** MB7621 uses the same structure as generic Motorola, so it will
        ***REMOVED*** match the generic parser. Users should manually select MB7621.
        return False
