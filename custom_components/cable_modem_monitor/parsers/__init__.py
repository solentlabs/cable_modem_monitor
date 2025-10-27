"""Parser plugin discovery and registration system."""
import logging
import importlib
import os
import pkgutil
from typing import List, Type

from .base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)

def get_parsers() -> List[Type[ModemParser]]:
    """Auto-discover and return all parser modules in this package."""
    parsers = []
    package_dir = os.path.dirname(__file__)

    _LOGGER.debug(f"Starting parser discovery in {package_dir}")
    for _, module_name, _ in pkgutil.iter_modules([package_dir]):
        _LOGGER.debug(f"Found module candidate: {module_name}")
        if module_name in ("base_parser", "__init__", "parser_template"):
            _LOGGER.debug(f"Skipping module: {module_name}")
            continue

        try:
            _LOGGER.debug(f"Attempting to import module: .{module_name}")
            module = importlib.import_module(f".{module_name}", package=__name__)
            _LOGGER.debug(f"Successfully imported module: {module_name}")
            found_parser_in_module = False
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, ModemParser) and attr is not ModemParser:
                    parsers.append(attr)
                    _LOGGER.info(f"Registered parser: {attr.name} ({attr.manufacturer}, models: {attr.models})")
                    found_parser_in_module = True
            if not found_parser_in_module:
                _LOGGER.debug(f"No ModemParser subclass found in module: {module_name}")
        except Exception as e:
            _LOGGER.error(f"Failed to load parser module {module_name}: {e}", exc_info=True)
    _LOGGER.debug(f"Finished parser discovery. Found {len(parsers)} parsers.")

    return parsers