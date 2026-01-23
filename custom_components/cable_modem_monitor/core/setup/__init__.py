"""Setup utilities for modems.

This module handles config flow setup for modems with modem.yaml definitions.
For unknown/fallback modems, see core/fallback/discovery/.
"""

from .modem import SetupResult, setup_modem

__all__ = ["setup_modem", "SetupResult"]
