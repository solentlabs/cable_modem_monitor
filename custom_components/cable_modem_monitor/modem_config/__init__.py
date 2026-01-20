"""Modem configuration module.

Provides declarative modem configuration via modem.yaml files.
Each modem.yaml is the single source of truth for:
    - Authentication strategy and credentials
    - Detection hints (login_markers, model_strings)
    - Parser class and module location
    - Capabilities and behaviors

Key functions:
    - get_auth_adapter_for_parser(): Get auth config for a parser class
    - load_modem_config(): Load a modem.yaml by path
    - get_aggregated_auth_patterns(): Get all known auth patterns from index
"""

from .adapter import (
    ModemConfigAuthAdapter,
    get_auth_adapter_for_parser,
    get_modem_config_for_parser,
)
from .loader import (
    async_discover_modems,
    async_load_modem_config,
    async_load_modem_config_by_parser,
    discover_modems,
    get_aggregated_auth_patterns,
    get_modem_by_model,
    load_modem_config,
    load_modem_config_by_parser,
    load_modem_index,
)
from .schema import AuthStrategy, ModemConfig

__all__ = [
    "AuthStrategy",
    "ModemConfig",
    "ModemConfigAuthAdapter",
    "async_discover_modems",
    "async_load_modem_config",
    "async_load_modem_config_by_parser",
    "discover_modems",
    "get_aggregated_auth_patterns",
    "get_auth_adapter_for_parser",
    "get_modem_by_model",
    "get_modem_config_for_parser",
    "load_modem_config",
    "load_modem_config_by_parser",
    "load_modem_index",
]
