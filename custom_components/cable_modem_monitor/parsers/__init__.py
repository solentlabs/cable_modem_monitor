"""Parser plugin discovery and registration system."""
import logging
import importlib
import pkgutil
from typing import Optional, Type
from bs4 import BeautifulSoup

from .base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class ParserRegistry:
    """Registry for auto-discovering and managing modem parsers."""

    def __init__(self):
        """Initialize the parser registry."""
        self._parsers: list[Type[ModemParser]] = []
        self._discover_parsers()

    def _discover_parsers(self):
        """Auto-discover all parser modules in this package."""
        ***REMOVED*** Get all modules in parsers/ directory
        import os
        package_dir = os.path.dirname(__file__)

        for _, module_name, _ in pkgutil.iter_modules([package_dir]):
            ***REMOVED*** Skip base_parser, __init__, and template
            if module_name in ("base_parser", "__init__", "parser_template"):
                continue

            try:
                ***REMOVED*** Import the module
                module = importlib.import_module(f".{module_name}", package=__name__)

                ***REMOVED*** Find classes that inherit from ModemParser
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, ModemParser)
                        and attr is not ModemParser
                    ):
                        self._parsers.append(attr)
                        _LOGGER.info(
                            f"Registered parser: {attr.name} "
                            f"({attr.manufacturer}, models: {attr.models})"
                        )

            except Exception as e:
                _LOGGER.error(f"Failed to load parser module {module_name}: {e}")

    def detect_parser(
        self, soup: BeautifulSoup, url: str, html: str
    ) -> Optional[ModemParser]:
        """
        Detect which parser can handle this modem's HTML.

        Args:
            soup: BeautifulSoup parsed HTML
            url: The URL that returned this HTML
            html: Raw HTML string

        Returns:
            Instance of the appropriate parser, or None if no parser matches
        """
        for parser_class in self._parsers:
            try:
                if parser_class.can_parse(soup, url, html):
                    _LOGGER.info(
                        f"Detected modem: {parser_class.name} "
                        f"(manufacturer: {parser_class.manufacturer})"
                    )
                    return parser_class()
            except Exception as e:
                _LOGGER.debug(f"Parser {parser_class.name} detection failed: {e}")

        _LOGGER.warning("No parser detected for this modem HTML")
        return None

    def list_parsers(self) -> list[Type[ModemParser]]:
        """Get list of all registered parsers."""
        return self._parsers


***REMOVED*** Global registry instance
_registry = ParserRegistry()


def detect_parser(soup: BeautifulSoup, url: str, html: str) -> Optional[ModemParser]:
    """Convenience function to detect parser."""
    return _registry.detect_parser(soup, url, html)


def list_parsers() -> list[Type[ModemParser]]:
    """Convenience function to list all registered parsers."""
    return _registry.list_parsers()
