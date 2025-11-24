"""Parser plugin discovery and registration system."""

from __future__ import annotations

import importlib
import logging
import os
import pkgutil

from .base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)

# Global cache for discovered parsers to avoid repeated filesystem scans
_PARSER_CACHE: list[type[ModemParser]] | None = None

# Mapping of parser names to their module paths for direct loading
_PARSER_MODULE_MAP = {
    "ARRIS SB6141": ("arris", "sb6141", "ARRISSb6141Parser"),
    "ARRIS SB6190": ("arris", "sb6190", "ArrisSB6190Parser"),
    "Motorola MB Series (Generic)": ("motorola", "generic", "MotorolaGenericParser"),
    "Motorola MB7621": ("motorola", "mb7621", "MotorolaMB7621Parser"),
    "Motorola MB8611 (HNAP)": ("motorola", "mb8611_hnap", "MotorolaMB8611HnapParser"),
    "Motorola MB8611 (Static)": ("motorola", "mb8611_static", "MotorolaMB8611StaticParser"),
    "Netgear C3700": ("netgear", "c3700", "NetgearC3700Parser"),
    "Netgear CM600": ("netgear", "cm600", "NetgearCM600Parser"),
    "Technicolor TC4400": ("technicolor", "tc4400", "TechnicolorTC4400Parser"),
    "Technicolor XB7": ("technicolor", "xb7", "TechnicolorXB7Parser"),
    "Unknown Modem (Fallback Mode)": ("universal", "fallback", "UniversalFallbackParser"),
}


def get_parser_by_name(parser_name: str) -> type[ModemParser] | None:
    """
    Load a specific parser by name without scanning all parsers.

    This is much faster than get_parsers() when you know which parser you need.

    Args:
        parser_name: The name of the parser (e.g., "Motorola MB8611 (Static)")

    Returns:
        Parser class if found, None otherwise
    """
    _LOGGER.debug("Attempting to get parser by name: %s", parser_name)
    if parser_name not in _PARSER_MODULE_MAP:
        _LOGGER.warning("Parser '%s' not found in known parsers map", parser_name)
        return None

    manufacturer, module_name, class_name = _PARSER_MODULE_MAP[parser_name]
    _LOGGER.debug(
        "Found parser details in map: manufacturer=%s, module=%s, class=%s",
        manufacturer,
        module_name,
        class_name,
    )

    try:
        # Import only the specific parser module
        full_module_name = f".{manufacturer}.{module_name}"
        _LOGGER.debug("Loading specific parser module: %s", full_module_name)
        module = importlib.import_module(full_module_name, package=__name__)
        _LOGGER.debug("Successfully imported module: %s", full_module_name)

        # Get the parser class
        parser_class = getattr(module, class_name, None)
        if parser_class:
            _LOGGER.debug("Found class '%s' in module '%s'", class_name, full_module_name)
            if issubclass(parser_class, ModemParser):
                _LOGGER.info("Loaded parser: %s (skipped discovery - direct load)", parser_name)
                return parser_class  # type: ignore[no-any-return]
            else:
                _LOGGER.error(
                    "Class '%s' found in module '%s' is not a subclass of ModemParser",
                    class_name,
                    full_module_name,
                )
        else:
            _LOGGER.error("Parser class %s not found in module %s", class_name, full_module_name)
        return None

    except Exception as e:
        _LOGGER.error("Failed to load parser %s: %s", parser_name, e, exc_info=True)
        return None


def get_parsers(use_cache: bool = True) -> list[type[ModemParser]]:  # noqa: C901
    """
    Auto-discover and return all parser modules in this package.

    Args:
        use_cache: If True, return cached parsers if available (faster).
                   Set to False to force re-discovery (useful for testing).

    Returns:
        List of all discovered parser classes
    """
    global _PARSER_CACHE

    # Return cached parsers if available
    if use_cache and _PARSER_CACHE is not None:
        _LOGGER.debug("Returning %d cached parsers (skipped discovery)", len(_PARSER_CACHE))
        return _PARSER_CACHE

    parsers = []
    package_dir = os.path.dirname(__file__)

    _LOGGER.debug("Starting parser discovery in %s", package_dir)

    # Iterate through manufacturer subdirectories (e.g., 'arris', 'motorola', 'technicolor')
    for manufacturer_dir_name in os.listdir(package_dir):
        manufacturer_dir_path = os.path.join(package_dir, manufacturer_dir_name)
        if not os.path.isdir(manufacturer_dir_path) or manufacturer_dir_name.startswith("__"):
            continue

        _LOGGER.debug("Searching in manufacturer directory: %s", manufacturer_dir_name)

        # Recursively find modules within each manufacturer directory
        for _, module_name, _ in pkgutil.iter_modules([manufacturer_dir_path]):
            _LOGGER.debug("Found module candidate: %s in %s", module_name, manufacturer_dir_name)
            if module_name in ("base_parser", "__init__", "parser_template"):
                _LOGGER.debug("Skipping module: %s", module_name)
                continue

            try:
                # Construct the full module path relative to the 'parsers' package
                full_module_name = f".{manufacturer_dir_name}.{module_name}"
                _LOGGER.debug("Attempting to import module: %s", full_module_name)
                module = importlib.import_module(full_module_name, package=__name__)
                _LOGGER.debug("Successfully imported module: %s", full_module_name)

                found_parser_in_module = False
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    # Only register parsers defined in this module (not imported ones)
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

    # Sort parsers to match dropdown order (alphabetical by manufacturer, then name)
    # Generic parsers go last within their manufacturer group
    # Unknown manufacturer (fallback) goes to the very end
    def sort_key(parser):
        # Unknown manufacturer goes last
        if parser.manufacturer == "Unknown":
            return ("ZZZZ", "ZZZZ")
        # Within each manufacturer, Generic parsers go last
        if "Generic" in parser.name:
            return (parser.manufacturer, "ZZZZ")
        # Regular parsers sort by manufacturer then name
        return (parser.manufacturer, parser.name)

    parsers.sort(key=sort_key)

    _LOGGER.debug("Finished parser discovery. Found %d parsers.", len(parsers))
    _LOGGER.debug("Parser order (alphabetical): %s", [p.name for p in parsers])

    # Cache the results
    _PARSER_CACHE = parsers

    return parsers
