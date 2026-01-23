"""Parser plugin discovery and registration system.

Parser Auto-Discovery
--------------------
Parsers are automatically discovered at runtime from modems/{mfr}/{model}/parser.py.

To add a new parser:

1. Create a file: modems/[manufacturer]/[model]/parser.py
2. Define a class that inherits from ModemParser (or a manufacturer base class)
3. Set the required class attributes: name, manufacturer, models
4. Implement: parse_resources()
5. Configure detection hints in modem.yaml (pre_auth, post_auth patterns)
6. Run `make sync` to copy to custom_components/modems/

The discovery system will automatically:
- Find your parser class in modems/{mfr}/{model}/parser.py
- Register it for modem detection
- Include it in the parser dropdown
- Sort it appropriately (by manufacturer, then name)

Note: Parser source of truth is modems/{mfr}/{model}/parser.py.
Files in custom_components/modems/ are synced from there during build.
Detection is handled by YAML hints (HintMatcher), not by parser code.
Authentication is handled by the auth system, not by parsers.
"""

from __future__ import annotations

import importlib
import logging
import os
from types import ModuleType

import yaml  # type: ignore[import-untyped]

from custom_components.cable_modem_monitor.core.base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)

# Global cache for discovered parsers to avoid repeated filesystem scans
_PARSER_CACHE: list[type[ModemParser]] | None = None

# Cache for parser name lookups (built from discovery, not hardcoded)
_PARSER_NAME_CACHE: dict[str, type[ModemParser]] | None = None

# Cache for the modem index (loaded once from index.yaml)
_MODEM_INDEX: dict | None = None

# Name → path lookup for O(1) parser loading (built from index.yaml)
_NAME_TO_PATH: dict[str, str] | None = None


def clear_parser_caches() -> None:
    """Clear all parser caches.

    Useful for testing when you need to force re-discovery.
    """
    global _PARSER_CACHE, _PARSER_NAME_CACHE, _MODEM_INDEX, _NAME_TO_PATH
    _PARSER_CACHE = None
    _PARSER_NAME_CACHE = None
    _MODEM_INDEX = None
    _NAME_TO_PATH = None
    _LOGGER.debug("Cleared all parser caches")


def get_parser_dropdown_from_index() -> list[str]:
    """Get parser display names from index.yaml for dropdown.

    This is the fast path for building the config flow dropdown - reads
    pre-computed names from index.yaml without importing any parser modules.

    The Universal Fallback Parser is appended at the end to allow users to
    install the integration even when their modem isn't auto-detected. This
    enables HTML capture for developing new parsers.

    Returns:
        Sorted list of parser display names (e.g., ["ARRIS SB6190", "Motorola MB7621", ...])
        with fallback parser at the end.
    """
    index = _load_modem_index()
    modems = index.get("modems", {})

    # Build list of (manufacturer, name) for sorting
    # Unverified modems get " *" suffix in the dropdown
    entries: list[tuple[str, str]] = []
    for entry in modems.values():
        name = entry.get("name")
        manufacturer = entry.get("manufacturer", "")
        verified = entry.get("verified", False)
        if name:
            # Skip unknown manufacturer (fallback is added manually at the end)
            if manufacturer == "Unknown":
                continue
            display_name = name if verified else f"{name} *"
            entries.append((manufacturer, display_name))

    # Sort by manufacturer, then name (matching get_parsers() sort order)
    entries.sort(key=lambda x: (x[0], x[1]))

    # Add fallback parser at end - allows installation for unsupported modems
    # so users can capture HTML diagnostics for parser development
    dropdown = [name for _, name in entries]
    dropdown.append("Unknown Modem (Fallback Mode)")

    return dropdown


def _load_modem_index() -> dict:
    """Load the modem index from index.yaml.

    Returns cached index if already loaded. Also builds the name→path
    lookup table for O(1) parser loading.
    """
    global _MODEM_INDEX, _NAME_TO_PATH

    if _MODEM_INDEX is not None:
        return _MODEM_INDEX

    core_dir = os.path.dirname(__file__)  # core/
    base_path = os.path.dirname(core_dir)  # custom_components/cable_modem_monitor/
    index_path = os.path.join(base_path, "modems", "index.yaml")

    try:
        with open(index_path) as f:
            _MODEM_INDEX = yaml.safe_load(f) or {}

        # Build name→path lookup for O(1) access
        _NAME_TO_PATH = {}
        modems = _MODEM_INDEX.get("modems", {})
        for entry in modems.values():
            path = entry.get("path")
            name = entry.get("name")
            if path and name:
                _NAME_TO_PATH[name] = path

        _LOGGER.debug(
            "Loaded modem index with %d entries (%d in name lookup)",
            len(modems),
            len(_NAME_TO_PATH),
        )
    except FileNotFoundError:
        _LOGGER.warning("Modem index not found at %s", index_path)
        _MODEM_INDEX = {"modems": {}}
        _NAME_TO_PATH = {}
    except (yaml.YAMLError, OSError, ValueError, TypeError) as e:
        # yaml.YAMLError: malformed YAML
        # OSError: permission/IO errors
        # ValueError/TypeError: unexpected data structure
        _LOGGER.error("Failed to load modem index: %s", e)
        _MODEM_INDEX = {"modems": {}}
        _NAME_TO_PATH = {}

    return _MODEM_INDEX


def _find_parser_in_module(
    module: ModuleType,
    expected_name: str | None = None,
) -> type[ModemParser] | None:
    """Find a ModemParser subclass in a module.

    Args:
        module: The imported module to search
        expected_name: If provided, only return a parser with this exact name

    Returns:
        The parser class if found, None otherwise
    """
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, ModemParser)
            and attr is not ModemParser
            and attr.__module__ == module.__name__
            and (expected_name is None or attr.name == expected_name)
        ):
            return attr
    return None


def _load_parser_direct(parser_name: str) -> type[ModemParser] | None:
    """Load a single parser directly by name using index.yaml.

    This is the fast path for known modems - O(1) lookup, single module import.

    Args:
        parser_name: Display name like "Motorola MB7621"

    Returns:
        Parser class if found and loaded, None otherwise
    """
    # Ensure index is loaded (builds _NAME_TO_PATH)
    _load_modem_index()

    if _NAME_TO_PATH is None:
        return None

    parser_path = _NAME_TO_PATH.get(parser_name)
    if not parser_path:
        _LOGGER.debug("Parser '%s' not found in index", parser_name)
        return None

    # Build module path: modems/{mfr}/{model}/parser.py
    # -> custom_components.cable_modem_monitor.modems.{mfr}.{model}.parser
    module_name = f"custom_components.cable_modem_monitor.modems.{parser_path.replace('/', '.')}.parser"

    try:
        _LOGGER.debug("Direct loading parser module: %s", module_name)
        module = importlib.import_module(module_name)

        parser_cls = _find_parser_in_module(module, expected_name=parser_name)
        if parser_cls:
            _LOGGER.debug("Direct loaded parser: %s", parser_cls.name)
            return parser_cls

        _LOGGER.warning(
            "Parser class with name '%s' not found in module %s",
            parser_name,
            module_name,
        )
        return None

    except (ImportError, AttributeError, TypeError, ValueError) as e:
        # ImportError: module not found
        # AttributeError: class not found in module
        # TypeError/ValueError: class instantiation or config issues
        _LOGGER.error("Failed to direct load parser '%s': %s", parser_name, e)
        return None


def get_parser_by_name(parser_name: str) -> type[ModemParser] | None:
    """Load a specific parser by name.

    Fast path: Uses index.yaml for O(1) lookup and direct loading.
    Fallback: Full discovery if direct load fails.

    Special case: The Universal Fallback Parser is not in modems/ so it's
    loaded directly from parsers/universal/fallback.py.

    Args:
        parser_name: The name of the parser (e.g., "Motorola MB8611")

    Returns:
        Parser class if found, None otherwise
    """
    global _PARSER_NAME_CACHE

    # Strip " *" suffix used to mark unverified parsers in the UI
    parser_name_clean = parser_name.rstrip(" *")

    _LOGGER.debug("Attempting to get parser by name: %s", parser_name_clean)

    # Special case: Universal Fallback Parser is not in modems/ directory
    if parser_name_clean == "Unknown Modem (Fallback Mode)":
        from custom_components.cable_modem_monitor.parsers.universal.fallback import (
            UniversalFallbackParser,
        )

        return UniversalFallbackParser

    # Fast path: Check name cache first (already loaded parsers)
    if _PARSER_NAME_CACHE is not None:
        parser_cls = _PARSER_NAME_CACHE.get(parser_name_clean)
        if parser_cls:
            _LOGGER.debug("Found parser '%s' in name cache", parser_name_clean)
            return parser_cls

    # Fast path: Try direct load from index.yaml (O(1) lookup, single module import)
    parser_cls = _load_parser_direct(parser_name_clean)
    if parser_cls:
        # Add to name cache for future lookups
        if _PARSER_NAME_CACHE is None:
            _PARSER_NAME_CACHE = {}
        _PARSER_NAME_CACHE[parser_name_clean] = parser_cls
        _LOGGER.debug("Direct loaded parser '%s'", parser_name_clean)
        return parser_cls

    # Fallback: Full discovery
    _LOGGER.debug("Direct load failed, falling back to full discovery")

    # Build complete name cache from all discovered parsers
    if _PARSER_NAME_CACHE is None:
        _PARSER_NAME_CACHE = {}
    for cls in get_parsers():
        _PARSER_NAME_CACHE[cls.name] = cls

    parser_cls = _PARSER_NAME_CACHE.get(parser_name_clean)
    if parser_cls:
        _LOGGER.debug("Found parser '%s' via full discovery", parser_name_clean)
        return parser_cls

    _LOGGER.warning("Parser '%s' not found", parser_name_clean)
    return None


def _discover_parsers(base_path: str) -> list[type[ModemParser]]:
    """Discover parsers from modems/{mfr}/{model}/parser.py structure.

    Args:
        base_path: Path to custom_components/cable_modem_monitor/

    Returns:
        List of discovered parser classes (unsorted)
    """
    parsers: list[type[ModemParser]] = []
    modems_dir = os.path.join(base_path, "modems")

    if not os.path.isdir(modems_dir):
        _LOGGER.debug("No modems/ directory found at %s", modems_dir)
        return parsers

    _LOGGER.debug("Scanning modems/ directory: %s", modems_dir)

    discovered_names: set[str] = set()

    for mfr_name in os.listdir(modems_dir):
        mfr_path = os.path.join(modems_dir, mfr_name)
        if not os.path.isdir(mfr_path) or mfr_name.startswith("__"):
            continue

        for model_name in os.listdir(mfr_path):
            model_path = os.path.join(mfr_path, model_name)
            parser_file = os.path.join(model_path, "parser.py")

            if not os.path.isfile(parser_file):
                continue

            _LOGGER.debug("Found parser.py: %s/%s/parser.py", mfr_name, model_name)

            try:
                module_name = f"custom_components.cable_modem_monitor.modems.{mfr_name}.{model_name}.parser"
                _LOGGER.debug("Attempting to import: %s", module_name)

                module = importlib.import_module(module_name)

                # Find all parser classes in the module (some modules may have multiple)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, ModemParser)
                        and attr is not ModemParser
                        and attr.__module__ == module.__name__
                        and attr.name not in discovered_names
                    ):
                        parsers.append(attr)
                        discovered_names.add(attr.name)
                        _LOGGER.debug(
                            "Registered parser: %s (%s, models: %s)",
                            attr.name,
                            attr.manufacturer,
                            attr.models,
                        )
            except (ImportError, AttributeError, TypeError, ValueError, SyntaxError) as e:
                # ImportError: module or dependency not found
                # AttributeError: class attribute access errors
                # TypeError/ValueError: class config issues
                # SyntaxError: parser.py has syntax errors
                _LOGGER.error(
                    "Failed to load parser from modems/%s/%s: %s",
                    mfr_name,
                    model_name,
                    e,
                    exc_info=True,
                )

    return parsers


def _sort_parsers(parsers: list[type[ModemParser]]) -> None:
    """Sort parsers alphabetically by manufacturer, then name.

    Generic parsers go last within their manufacturer group.
    Unknown manufacturer goes to the very end.

    Args:
        parsers: List to sort in place
    """

    def sort_key(parser: type[ModemParser]) -> tuple[str, str]:
        if parser.manufacturer == "Unknown":
            return ("ZZZZ", "ZZZZ")
        if "Generic" in parser.name:
            return (parser.manufacturer, "ZZZZ")
        return (parser.manufacturer, parser.name)

    parsers.sort(key=sort_key)


def get_parsers(use_cache: bool = True) -> list[type[ModemParser]]:
    """Auto-discover and return all parser modules.

    Scans modems/{mfr}/{model}/parser.py for parser classes.

    Args:
        use_cache: If True, return cached parsers if available (faster).
                   Set to False to force re-discovery (useful for testing).

    Returns:
        List of all discovered parser classes, sorted by manufacturer then name
    """
    global _PARSER_CACHE
    global _PARSER_NAME_CACHE

    if use_cache and _PARSER_CACHE is not None:
        _LOGGER.debug("Returning %d cached parsers (skipped discovery)", len(_PARSER_CACHE))
        return _PARSER_CACHE

    # Clear name cache when re-discovering (ensures consistency)
    if not use_cache:
        _PARSER_NAME_CACHE = None

    _LOGGER.debug("Starting parser discovery")

    core_dir = os.path.dirname(__file__)  # core/
    base_path = os.path.dirname(core_dir)  # custom_components/cable_modem_monitor/

    parsers = _discover_parsers(base_path)
    _sort_parsers(parsers)

    _LOGGER.debug("Finished parser discovery. Found %d parsers.", len(parsers))
    _LOGGER.debug("Parser order: %s", [p.name for p in parsers])

    _PARSER_CACHE = parsers

    return parsers
