"""Parser plugin discovery and registration system."""

from __future__ import annotations

import importlib
import logging
import os
import pkgutil

from .base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


def get_parsers() -> list[type[ModemParser]]:
    """Auto-discover and return all parser modules in this package."""
    parsers = []
    package_dir = os.path.dirname(__file__)

    _LOGGER.debug(f"Starting parser discovery in {package_dir}")

    # Iterate through manufacturer subdirectories (e.g., 'arris', 'motorola', 'technicolor')
    for manufacturer_dir_name in os.listdir(package_dir):
        manufacturer_dir_path = os.path.join(package_dir, manufacturer_dir_name)
        if not os.path.isdir(manufacturer_dir_path) or manufacturer_dir_name.startswith("__"):
            continue

        _LOGGER.debug(f"Searching in manufacturer directory: {manufacturer_dir_name}")

        # Recursively find modules within each manufacturer directory
        for _, module_name, _ in pkgutil.iter_modules([manufacturer_dir_path]):
            _LOGGER.debug(f"Found module candidate: {module_name} in {manufacturer_dir_name}")
            if module_name in ("base_parser", "__init__", "parser_template"):
                _LOGGER.debug(f"Skipping module: {module_name}")
                continue

            try:
                # Construct the full module path relative to the 'parsers' package
                full_module_name = f".{manufacturer_dir_name}.{module_name}"
                _LOGGER.debug(f"Attempting to import module: {full_module_name}")
                module = importlib.import_module(full_module_name, package=__name__)
                _LOGGER.debug(f"Successfully imported module: {full_module_name}")

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
                        _LOGGER.info(f"Registered parser: {attr.name} ({attr.manufacturer}, models: {attr.models})")
                        found_parser_in_module = True
                if not found_parser_in_module:
                    _LOGGER.debug(f"No ModemParser subclass found in module: {full_module_name}")
            except Exception as e:
                _LOGGER.error(f"Failed to load parser module {full_module_name}: {e}", exc_info=True)

    # Sort parsers by manufacturer, then by priority (higher priority first)
    # This ensures model-specific parsers are tried before generic ones within the same manufacturer
    parsers.sort(key=lambda p: (p.manufacturer, p.priority), reverse=True)

    _LOGGER.debug(f"Finished parser discovery. Found {len(parsers)} parsers.")
    _LOGGER.debug(f"Parser order by priority: {[f'{p.name} (priority={p.priority})' for p in parsers]}")

    return parsers
