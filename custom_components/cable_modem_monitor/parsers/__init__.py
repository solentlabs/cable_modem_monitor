"""Parser plugin discovery and registration.

This module provides the public API for discovering and loading modem parsers.
Parsers are responsible for extracting channel data from modem responses.

Architecture:
    Parsers are organized by manufacturer in the modems/ directory:

    modems/
    ├── index.yaml          ← Parser registry with class names and paths
    ├── arris/
    │   ├── sb8200/
    │   │   ├── modem.yaml  ← Modem configuration (auth, detection, etc.)
    │   │   └── parser.py   ← ArrisSB8200Parser class
    │   └── s33/
    │       └── ...
    ├── motorola/
    │   └── ...
    └── netgear/
        └── ...

Parser Contract:
    All parsers inherit from ModemParser (core.base_parser) and implement:
    - parse_resources(resources: dict[str, Any]) -> dict | None
    - name: str property (human-readable modem name)

Available Functions:
    get_parsers() -> list[type[ModemParser]]
        Discover all available parser classes

    get_parser_by_name(name: str) -> type[ModemParser] | None
        Get parser class by its class name (e.g., "ArrisSB8200Parser")

    get_parser_dropdown_from_index() -> dict[str, str]
        Get parser options for UI dropdown (display_name -> class_name)

Re-exports from core.parser_discovery for backward compatibility.
"""

from __future__ import annotations

from custom_components.cable_modem_monitor.core.parser_discovery import (
    get_parser_by_name,
    get_parser_dropdown_from_index,
    get_parsers,
)

__all__ = ["get_parser_by_name", "get_parser_dropdown_from_index", "get_parsers"]
