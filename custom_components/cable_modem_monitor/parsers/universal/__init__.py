"""Universal fallback parsers for cable modems.

These parsers provide generic support for modems that don't have a dedicated
manufacturer-specific parser, typically using SNMP or other standard protocols.

Parsers are auto-discovered - add new parser files to this directory and they will
be automatically registered.
"""

from __future__ import annotations
