"""Action layer for modem operations.

This module provides a clean separation of concerns:
- Loaders handle data fetching (HNAPLoader, HTMLLoader, RESTLoader)
- Parsers handle data parsing only (pure data transformation)
- Actions handle modem operations (restart only - see base.py for hard boundaries)

Architecture:
    ModemAction (base class)
    ├── HNAPRestartAction    - HNAP/SOAP modems
    ├── HTMLRestartAction    - HTML form-based modems
    └── RESTRestartAction    - REST API modems (stub, awaiting capture data)

Usage:
    from core.actions import ActionFactory

    action = ActionFactory.create_restart_action(modem_config)
    if action:
        result = action.execute(session, base_url, hnap_builder)
"""

from .base import ModemAction
from .factory import ActionFactory
from .hnap import HNAPRestartAction
from .html import HTMLRestartAction
from .rest import RESTRestartAction

__all__ = [
    "ActionFactory",
    "HNAPRestartAction",
    "HTMLRestartAction",
    "ModemAction",
    "RESTRestartAction",
]
