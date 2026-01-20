"""Parser utility functions for cable modem monitoring.

Pure utility functions for parser selection, sorting, and display formatting.
These are independent of Home Assistant and can be used in any context (CLI, tests, etc.).

This module contains functions that operate on parser classes but don't perform
any I/O (loading, discovery). For parser loading/discovery, see:
- core/parser_discovery.py - Parser class loading and discovery
- modem_config/loader.py - Modem YAML configuration loading
- modem_config/adapter.py - Config-to-parser adapters

Functions:
    Sorting & Display:
        sort_parsers_for_dropdown: Sort parsers for UI dropdown display
        get_parser_display_name: Get parser name with verification status indicator

    Selection:
        select_parser_for_validation: Select parser class for config flow validation

    Formatting:
        create_title: Create user-friendly title from detection info

Design Notes:
    - All functions are pure (no side effects, no I/O)
    - Accept parser classes/sequences, not instances
    - Return primitive types or parser classes (not instances)
    - 100% test coverage via tests/core/test_parser_utils.py
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


def sort_parsers_for_dropdown(parsers: Sequence[type[ModemParser]]) -> list[type[ModemParser]]:
    """Sort parsers for dropdown display.

    Order: alphabetical by manufacturer, then by name.
    Generic parsers appear last within their manufacturer group.
    Unknown/Fallback parsers appear at the very end.

    Args:
        parsers: List of parser classes to sort

    Returns:
        Sorted list of parser classes
    """

    def sort_key(p: type[ModemParser]) -> tuple[str, str]:
        if p.manufacturer == "Unknown":
            return ("ZZZZ", "ZZZZ")
        if "Generic" in p.name:
            return (p.manufacturer, "ZZZZ")
        return (p.manufacturer, p.name)

    return sorted(parsers, key=sort_key)


def get_parser_display_name(parser_class: type[ModemParser]) -> str:
    """Get display name for parser with verification status.

    Args:
        parser_class: Parser class to get name for

    Returns:
        Display name with " *" suffix if not verified
    """
    from .base_parser import ParserStatus

    name: str = str(parser_class.name)
    # Status is cached on class via __init_subclass__ (no I/O)
    if parser_class.status != ParserStatus.VERIFIED:
        name += " *"
    return name


def select_parser_for_validation(
    all_parsers: Sequence[type[ModemParser]],
    modem_choice: str | None,
    cached_parser_name: str | None,
) -> tuple[type[ModemParser] | None, str | None]:
    """Select parser class for validation.

    Args:
        all_parsers: List of available parser classes
        modem_choice: User-selected parser name or None/auto for auto-detection
        cached_parser_name: Previously detected parser name or None

    Returns:
        tuple of (selected_parser_class, parser_name_hint) where:
        - selected_parser_class: Parser class or None if using auto-detection
        - parser_name_hint: Cached parser name or None
    """
    if modem_choice and modem_choice != "auto":
        # User explicitly selected a parser - return the CLASS, not instance
        # Strip " *" suffix if present for matching
        choice_clean = modem_choice.rstrip(" *")
        for parser_class in all_parsers:
            if parser_class.name == choice_clean:
                _LOGGER.info("User selected parser: %s", parser_class.name)
                return parser_class, None  # Return class, not instance
        return None, None
    else:
        # Auto mode - use all parsers with cached name hint
        _LOGGER.info(
            "Using auto-detection mode (modem_choice=%s, cached_parser=%s)",
            modem_choice,
            cached_parser_name,
        )
        if cached_parser_name:
            _LOGGER.info("Will try cached parser first: %s", cached_parser_name)
        else:
            _LOGGER.info("No cached parser, will try all available parsers")
        return None, cached_parser_name


def create_title(detection_info: dict, host: str) -> str:
    """Create user-friendly title from detection info.

    Args:
        detection_info: Dict with modem_name and manufacturer keys
        host: Modem IP address or hostname

    Returns:
        Formatted title string like "Manufacturer Model (host)"
    """
    detected_modem = detection_info.get("modem_name", "Cable Modem")
    detected_manufacturer = detection_info.get("manufacturer", "")

    # Avoid duplicate manufacturer name if already in modem name
    if (
        detected_manufacturer
        and detected_manufacturer != "Unknown"
        and not detected_modem.startswith(detected_manufacturer)
    ):
        return f"{detected_manufacturer} {detected_modem} ({host})"
    else:
        return f"{detected_modem} ({host})"
