"""PostProcessor for {manufacturer}/{model} — channel data extraction.

Extracts downstream and upstream channel data from JS variable
assignments inside ``<script>`` tags at ``/php/status_docsis_data.php``.
Extracts ``software_version`` from ``/php/status_about_data.php``.

The response body is HTML containing::

    json_dsData = [{...}, {...}, ...];
    json_usData = [{...}, {...}, ...];

Each JSON object has these fields (downstream example)::

    {"ChannelType": "SC-QAM", "Frequency": 570,
     "PowerLevel": "0.3/60.3", "SNRLevel": 40.4,
     "Modulation": "256QAM", "ChannelID": "11",
     "LockStatus": "Locked"}

PostProcessor scope
-------------------
This PostProcessor handles two things that parser.yaml cannot express:

1. **JSON extraction from ``<script>`` tags** — the data is JSON arrays
   assigned to JS variables, not a standalone JSON endpoint or a
   pipe-delimited tagValueList.  No existing parser format handles this.
   Candidate for a future Core ``js_json`` parser format.

2. **PowerLevel splitting** — ``"0.3/60.3"`` is ``dBmV/dBµV``.
   The ``/`` separator and take-first logic has no parser.yaml equivalent.
   Candidate for a future ``split`` type or ``separator`` parameter.

Field mapping, type conversion, and lock status filtering use Core's
``convert_value`` to stay consistent with parser.yaml-driven parsers.
"""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup
from solentlabs.cable_modem_monitor_core.parsers.type_conversion import convert_value

# Regex to extract JSON array assigned to a JS variable.
# Matches: varName = [{...}, ...];
_JS_ARRAY_RE = re.compile(
    r"(json_dsData|json_usData)\s*=\s*(\[.*?\])\s*;",
    re.DOTALL,
)

# Regex to extract simple JS variable assignments (for system_info).
_JS_VAR_RE = re.compile(r"(?:var\s+)?(\w+)\s*=\s*'([^']*)'")

# Source JSON key → (canonical field name, Core field type).
# fmt: off
_DS_FIELD_MAP: list[tuple[str, str, str]] = [
    ("ChannelID",   "channel_id",  "integer"),
    ("Frequency",   "frequency",   "frequency"),
    ("SNRLevel",    "snr",         "float"),
    ("Modulation",  "modulation",  "string"),
    ("LockStatus",  "lock_status", "lock_status"),
    ("ChannelType", "channel_type", "string"),
]

_US_FIELD_MAP: list[tuple[str, str, str]] = [
    ("ChannelID",   "channel_id",  "integer"),
    ("Frequency",   "frequency",   "frequency"),
    ("Modulation",  "modulation",  "string"),
    ("LockStatus",  "lock_status", "lock_status"),
    ("ChannelType", "channel_type", "string"),
]
# fmt: on

# Channel type normalization (modem values → canonical).
_CHANNEL_TYPE_MAP: dict[str, str] = {
    "SC-QAM": "qam",
    "OFDM": "ofdm",
    "OFDMA": "ofdma",
}

# Lock status values this modem uses that Core's convert_value doesn't
# recognize.  Mapped to Core-standard values before conversion.
_LOCK_STATUS_MAP: dict[str, str] = {
    "OPERATE": "Locked",
    "SUCCESS": "Locked",
    "ACTIVE": "Active",
}


class PostProcessor:
    """Extract channel data from JS-embedded JSON arrays."""

    def parse_downstream(
        self,
        channels: list[dict[str, Any]],
        resources: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Extract downstream channels from json_dsData."""
        raw = _extract_js_array(resources, "json_dsData")
        return [ch for ch in (_map_channel(r, _DS_FIELD_MAP) for r in raw) if ch]

    def parse_upstream(
        self,
        channels: list[dict[str, Any]],
        resources: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Extract upstream channels from json_usData."""
        raw = _extract_js_array(resources, "json_usData")
        return [ch for ch in (_map_channel(r, _US_FIELD_MAP) for r in raw) if ch]

    def parse_system_info(
        self,
        system_info: dict[str, Any],
        resources: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract software_version from status_about_data.php."""
        for resource in resources.values():
            if not isinstance(resource, BeautifulSoup):
                continue
            for script in resource.find_all("script"):
                text = script.string
                if not text or "js_FWVersion" not in text:
                    continue
                for match in _JS_VAR_RE.finditer(text):
                    if match.group(1) == "js_FWVersion":
                        system_info["software_version"] = match.group(2)
                        return system_info
        return system_info


def _extract_js_array(
    resources: dict[str, Any],
    var_name: str,
) -> list[dict[str, Any]]:
    """Find and parse a JSON array from a JS variable assignment.

    Searches all HTML resources for a ``<script>`` block containing
    ``var_name = [...];`` and returns the parsed JSON array.

    .. note::
        Candidate for a future Core parser format (``js_json``) that
        extracts JSON arrays from JS variable assignments in HTML.
    """
    for resource in resources.values():
        if not isinstance(resource, BeautifulSoup):
            continue
        for script in resource.find_all("script"):
            text = script.string
            if not text or var_name not in text:
                continue
            for match in _JS_ARRAY_RE.finditer(text):
                if match.group(1) == var_name:
                    try:
                        data = json.loads(match.group(2))
                        if isinstance(data, list):
                            return data
                    except json.JSONDecodeError:
                        continue
    return []


def _map_channel(
    raw: dict[str, Any],
    field_map: list[tuple[str, str, str]],
) -> dict[str, Any] | None:
    """Map raw modem JSON fields to canonical output fields.

    Uses Core's ``convert_value`` for type conversion. Filters out
    unlocked channels. Handles PowerLevel splitting and channel type
    normalization.

    Returns ``None`` for unlocked channels (filtered out by caller).
    """
    result: dict[str, Any] = {}

    for src_key, dst_field, field_type in field_map:
        raw_value = raw.get(src_key)
        if raw_value is None:
            continue
        # Normalize non-standard lock status values before Core conversion.
        if field_type == "lock_status" and isinstance(raw_value, str):
            raw_value = _LOCK_STATUS_MAP.get(raw_value, raw_value)
        converted = convert_value(raw_value, field_type)
        if converted is not None:
            result[dst_field] = converted

    # Filter: only locked channels.
    if result.get("lock_status") != "locked":
        return None

    # Normalize channel_type.
    ct = result.get("channel_type", "")
    result["channel_type"] = _CHANNEL_TYPE_MAP.get(ct, ct.lower())

    # PowerLevel: "dBmV/dBµV" — take first value (dBmV).
    # See module docstring for rationale and future extraction note.
    result["power"] = _split_power(str(raw.get("PowerLevel", "")))

    return result


def _split_power(value: str) -> float:
    """Extract dBmV from dual 'dBmV/dBµV' PowerLevel format.

    Takes the first value before the ``/`` separator.
    Falls back to parsing the whole string if no separator.

    The second value is dBµV (= dBmV + 60), which is redundant.

    .. note::
        Candidate for a future ``parser.yaml`` feature (e.g., a
        ``split`` type or ``separator`` parameter). When that feature
        exists, this function can be replaced by declarative config.
    """
    part = value.split("/", maxsplit=1)[0]
    try:
        return float(part)
    except (ValueError, TypeError):
        return 0.0
