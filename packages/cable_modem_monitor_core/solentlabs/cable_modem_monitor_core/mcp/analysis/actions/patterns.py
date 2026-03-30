"""Load action detection patterns from JSON.

Single source of truth for logout and restart URL patterns. Adding a
new pattern = one line in ``action_patterns.json``, no code changes.

Patterns are stored as regex strings in JSON and compiled on load.
All matching is case-insensitive.
"""

from __future__ import annotations

import functools
import json
import re
from pathlib import Path
from typing import Any

_PATTERNS_PATH = Path(__file__).parent / "action_patterns.json"


@functools.lru_cache(maxsize=1)
def _load_patterns() -> dict[str, Any]:
    """Load and cache the action patterns JSON."""
    data: dict[str, Any] = json.loads(_PATTERNS_PATH.read_text(encoding="utf-8"))
    return data


def get_logout_patterns() -> tuple[re.Pattern[str], ...]:
    """Return compiled logout URL regex patterns."""
    data = _load_patterns()
    return tuple(re.compile(p, re.IGNORECASE) for p in data["logout_url_patterns"])


def get_restart_patterns() -> tuple[re.Pattern[str], ...]:
    """Return compiled restart URL regex patterns."""
    data = _load_patterns()
    return tuple(re.compile(p, re.IGNORECASE) for p in data["restart_url_patterns"])
