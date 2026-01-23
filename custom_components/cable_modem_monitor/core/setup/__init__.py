"""Setup utilities for known modems.

This module handles config flow setup for modems with modem.yaml definitions.
For unknown/fallback modems, see core/fallback/discovery/.
"""

from .known_modem import SetupResult, setup_known_modem

__all__ = ["setup_known_modem", "SetupResult"]
