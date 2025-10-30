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

    ***REMOVED*** Override specific methods or add MB7621-specific logic here if needed
    ***REMOVED*** For now, it inherits all logic from MotorolaGenericParser

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Motorola MB7621 modem."""
        ***REMOVED*** More specific detection for MB7621 if available, otherwise rely on generic
        if "MB7621" in html and "Motorola Cable Modem" in soup.title.string:
            return True
        return super().can_parse(soup, url, html)
