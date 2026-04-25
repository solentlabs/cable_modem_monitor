"""Step 1: Structural validation.

Verifies the HAR file is valid JSON with the expected structure:
log.entries array, each entry has request and response objects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from solentlabs.cable_modem_monitor_core.har import LfsPointerError, load_har_json

from .har_utils import HARD_STOP_PREFIX


def validate_structure(har_path: Path, issues: list[str]) -> dict[str, Any] | None:
    """Validate HAR file structure. Returns parsed HAR dict or None on failure.

    Appends HARD STOP issues for: missing file, invalid JSON, missing log key,
    empty entries, missing request/response objects.
    """
    if not har_path.exists():
        issues.append(f"{HARD_STOP_PREFIX} HAR file not found: {har_path}")
        return None

    try:
        har_data: dict[str, Any] = load_har_json(har_path)
    except LfsPointerError as e:
        issues.append(f"{HARD_STOP_PREFIX} {e}")
        return None
    except json.JSONDecodeError as e:
        issues.append(f"{HARD_STOP_PREFIX} HAR file is not valid JSON: {e}")
        return None

    if "log" not in har_data:
        issues.append(f"{HARD_STOP_PREFIX} HAR missing 'log' key")
        return None

    entries = har_data["log"].get("entries")
    if not entries:
        issues.append(f"{HARD_STOP_PREFIX} HAR has no entries (log.entries is empty)")
        return None

    for i, entry in enumerate(entries):
        if "request" not in entry:
            issues.append(f"{HARD_STOP_PREFIX} entry[{i}] missing 'request' object")
            return None
        if "response" not in entry:
            issues.append(f"{HARD_STOP_PREFIX} entry[{i}] missing 'response' object")
            return None

    return har_data
