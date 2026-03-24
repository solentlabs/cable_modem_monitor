"""Format-specific parser implementations.

Each module implements parsing for one data format (HTML table, JSON,
HNAP, JavaScript, etc.). All follow the same contract: take a parser
config section and pre-fetched resources, return extracted channel or
system_info data.

Registered in ``parsers.registries`` for dispatch by the coordinator.
"""
