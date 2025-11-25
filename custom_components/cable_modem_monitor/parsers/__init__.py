"""Parser plugin discovery and registration system.

Parser Auto-Discovery
--------------------
Parsers are automatically discovered at runtime. To add a new parser:

1. Create a file: parsers/[manufacturer]/[model].py
2. Define a class that inherits from ModemParser (or a manufacturer base class)
3. Set the required class attributes: name, manufacturer, models
4. Implement: can_parse(), login(), parse()

That's it! No need to update any registry or mapping files.

The discovery system will automatically:
- Find your parser class
- Register it for modem detection
- Include it in the parser dropdown
- Sort it appropriately (by manufacturer, then name)
"""

from __future__ import annotations

import importlib
import logging
import os
import pkgutil

from .base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)

***REMOVED*** Global cache for discovered parsers to avoid repeated filesystem scans
_PARSER_CACHE: list[type[ModemParser]] | None = None

***REMOVED*** Cache for parser name lookups (built from discovery, not hardcoded)
_PARSER_NAME_CACHE: dict[str, type[ModemParser]] | None = None


def get_parser_by_name(parser_name: str) -> type[ModemParser] | None:
    """
    Load a specific parser by name.

    Uses the discovery cache for fast lookups. If the cache is empty,
    triggers discovery first.

    Args:
        parser_name: The name of the parser (e.g., "Motorola MB8611 (Static)")

    Returns:
        Parser class if found, None otherwise
    """
    global _PARSER_NAME_CACHE

    _LOGGER.debug("Attempting to get parser by name: %s", parser_name)

    ***REMOVED*** Build the name cache if not already built
    if _PARSER_NAME_CACHE is None:
        _LOGGER.debug("Building parser name cache from discovery")
        _PARSER_NAME_CACHE = {}
        for cls in get_parsers():
            _PARSER_NAME_CACHE[cls.name] = cls

    ***REMOVED*** Look up in cache
    parser_cls = _PARSER_NAME_CACHE.get(parser_name)
    if parser_cls:
        _LOGGER.debug("Found parser '%s' in cache", parser_name)
        return parser_cls

    _LOGGER.warning("Parser '%s' not found in discovered parsers", parser_name)
    return None


def get_parsers(use_cache: bool = True) -> list[type[ModemParser]]:  ***REMOVED*** noqa: C901
    """
    Auto-discover and return all parser modules in this package.

    Args:
        use_cache: If True, return cached parsers if available (faster).
                   Set to False to force re-discovery (useful for testing).

    Returns:
        List of all discovered parser classes
    """
    global _PARSER_CACHE
    global _PARSER_NAME_CACHE

    ***REMOVED*** Return cached parsers if available
    if use_cache and _PARSER_CACHE is not None:
        _LOGGER.debug("Returning %d cached parsers (skipped discovery)", len(_PARSER_CACHE))
        return _PARSER_CACHE

    ***REMOVED*** Clear name cache when re-discovering (ensures consistency)
    if not use_cache:
        _PARSER_NAME_CACHE = None

    parsers = []
    package_dir = os.path.dirname(__file__)

    _LOGGER.debug("Starting parser discovery in %s", package_dir)

    ***REMOVED*** Iterate through manufacturer subdirectories (e.g., 'arris', 'motorola', 'technicolor')
    for manufacturer_dir_name in os.listdir(package_dir):
        manufacturer_dir_path = os.path.join(package_dir, manufacturer_dir_name)
        if not os.path.isdir(manufacturer_dir_path) or manufacturer_dir_name.startswith("__"):
            continue

        _LOGGER.debug("Searching in manufacturer directory: %s", manufacturer_dir_name)

        ***REMOVED*** Recursively find modules within each manufacturer directory
        for _, module_name, _ in pkgutil.iter_modules([manufacturer_dir_path]):
            _LOGGER.debug("Found module candidate: %s in %s", module_name, manufacturer_dir_name)
            if module_name in ("base_parser", "__init__", "parser_template"):
                _LOGGER.debug("Skipping module: %s", module_name)
                continue

            try:
                ***REMOVED*** Construct the full module path relative to the 'parsers' package
                full_module_name = f".{manufacturer_dir_name}.{module_name}"
                _LOGGER.debug("Attempting to import module: %s", full_module_name)
                module = importlib.import_module(full_module_name, package=__name__)
                _LOGGER.debug("Successfully imported module: %s", full_module_name)

                found_parser_in_module = False
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    ***REMOVED*** Only register parsers defined in this module (not imported ones)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, ModemParser)
                        and attr is not ModemParser
                        and attr.__module__ == module.__name__
                    ):
                        parsers.append(attr)
                        _LOGGER.info(
                            "Registered parser: %s (%s, models: %s)", attr.name, attr.manufacturer, attr.models
                        )
                        found_parser_in_module = True
                if not found_parser_in_module:
                    _LOGGER.debug("No ModemParser subclass found in module: %s", full_module_name)
            except Exception as e:
                _LOGGER.error("Failed to load parser module %s: %s", full_module_name, e, exc_info=True)

    ***REMOVED*** Sort parsers to match dropdown order (alphabetical by manufacturer, then name)
    ***REMOVED*** Generic parsers go last within their manufacturer group
    ***REMOVED*** Unknown manufacturer (fallback) goes to the very end
    def sort_key(parser):
        ***REMOVED*** Unknown manufacturer goes last
        if parser.manufacturer == "Unknown":
            return ("ZZZZ", "ZZZZ")
        ***REMOVED*** Within each manufacturer, Generic parsers go last
        if "Generic" in parser.name:
            return (parser.manufacturer, "ZZZZ")
        ***REMOVED*** Regular parsers sort by manufacturer then name
        return (parser.manufacturer, parser.name)

    parsers.sort(key=sort_key)

    _LOGGER.debug("Finished parser discovery. Found %d parsers.", len(parsers))
    _LOGGER.debug("Parser order (alphabetical): %s", [p.name for p in parsers])

    ***REMOVED*** Cache the results
    _PARSER_CACHE = parsers

    return parsers
