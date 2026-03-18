"""Phase 6 - System info detection.

Detects system_info sources across multiple pages and formats:
html_fields (label/id based), javascript, json. Builds a multi-source
configuration matching the parser.yaml system_info schema.

Per docs/ONBOARDING_SPEC.md Phase 6 and docs/PARSING_SPEC.md system_info section.
"""

from __future__ import annotations

from typing import Any

from ..format.types import DetectedLabelPair, PageAnalysis
from .types import (
    SystemInfoDetail,
    SystemInfoFieldDetail,
    SystemInfoSourceDetail,
)

# -----------------------------------------------------------------------
# System info label-to-field mapping (ONBOARDING_SPEC Phase 6)
# -----------------------------------------------------------------------

# Maps lowercase label text -> (canonical_field, tier)
_LABEL_FIELD_MAP: dict[str, tuple[str, int]] = {
    # Tier 1 canonical
    "system up time": ("system_uptime", 1),
    "uptime": ("system_uptime", 1),
    "system uptime": ("system_uptime", 1),
    "software version": ("software_version", 1),
    "firmware version": ("software_version", 1),
    "sw version": ("software_version", 1),
    "hardware version": ("hardware_version", 1),
    "hw version": ("hardware_version", 1),
    "model": ("hardware_version", 1),
    "network access": ("network_access", 1),
    "cable modem status": ("network_access", 1),
    # Tier 2 registered
    "boot status": ("boot_status", 2),
    "boot state": ("boot_status", 2),
    "serial number": ("serial_number", 2),
    "docsis version": ("docsis_version", 2),
    "temperature": ("temperature", 2),
}

# ID-based label mapping (element ids commonly used for system info)
_ID_FIELD_MAP: dict[str, tuple[str, int]] = {
    "systemuptime": ("system_uptime", 1),
    "firmwareversion": ("software_version", 1),
    "softwareversion": ("software_version", 1),
    "hardwareversion": ("hardware_version", 1),
    "networkaccess": ("network_access", 1),
    "bootstate": ("boot_status", 2),
    "serialnumber": ("serial_number", 2),
    "docsisversion": ("docsis_version", 2),
}

# JSON key mapping for system info
_JSON_SYSINFO_MAP: dict[str, tuple[str, int]] = {
    "uptime": ("system_uptime", 1),
    "systemuptime": ("system_uptime", 1),
    "system_uptime": ("system_uptime", 1),
    "firmwareversion": ("software_version", 1),
    "firmware_version": ("software_version", 1),
    "softwareversion": ("software_version", 1),
    "software_version": ("software_version", 1),
    "hardwareversion": ("hardware_version", 1),
    "hardware_version": ("hardware_version", 1),
    "model": ("hardware_version", 1),
    "networkaccess": ("network_access", 1),
    "network_access": ("network_access", 1),
    "status": ("network_access", 1),
    "bootstatus": ("boot_status", 2),
    "boot_status": ("boot_status", 2),
    "serialnumber": ("serial_number", 2),
    "serial_number": ("serial_number", 2),
    "docsisversion": ("docsis_version", 2),
    "docsis_version": ("docsis_version", 2),
}


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------


def detect_system_info(
    pages: list[PageAnalysis],
    warnings: list[str],
) -> SystemInfoDetail | None:
    """Detect system_info sources across all analyzed pages.

    Scans label-value pairs, JS functions, and JSON data for system info
    fields. Returns a multi-source SystemInfoDetail or None if nothing
    found.
    """
    sources: list[SystemInfoSourceDetail] = []

    for page in pages:
        # html_fields: label-value pairs
        if page.label_pairs:
            fields = _match_label_pairs(page.label_pairs)
            if fields:
                sources.append(
                    SystemInfoSourceDetail(
                        format="html_fields",
                        resource=page.resource,
                        fields=fields,
                    )
                )

        # javascript: JS functions with system info patterns
        for js_func in page.js_functions:
            name_lower = js_func.name.lower()
            if "system" in name_lower or "info" in name_lower:
                fields = _match_js_system_info(js_func.values)
                if fields:
                    sources.append(
                        SystemInfoSourceDetail(
                            format="javascript",
                            resource=page.resource,
                            fields=fields,
                        )
                    )

        # json: JSON data with system info keys
        if page.json_data is not None:
            fields = _match_json_system_info(page.json_data)
            if fields:
                sources.append(
                    SystemInfoSourceDetail(
                        format="json",
                        resource=page.resource,
                        fields=fields,
                    )
                )

    if not sources:
        return None

    return SystemInfoDetail(sources=sources)


# -----------------------------------------------------------------------
# HTML label-value matching
# -----------------------------------------------------------------------


def _match_label_pairs(
    pairs: list[DetectedLabelPair],
) -> list[SystemInfoFieldDetail]:
    """Match detected label-value pairs to system info fields."""
    fields: list[SystemInfoFieldDetail] = []
    seen_fields: set[str] = set()

    for pair in pairs:
        field_name, _tier = _match_label(pair.label, pair.selector_type)
        if not field_name or field_name in seen_fields:
            continue

        seen_fields.add(field_name)
        fields.append(
            SystemInfoFieldDetail(
                field=field_name,
                type="string",
                selector_type=pair.selector_type,
                selector_value=pair.selector_value,
            )
        )

    return fields


def _match_label(label: str, selector_type: str) -> tuple[str, int]:
    """Match a label or id to a system info field name.

    Returns (field_name, tier) or ("", 0).
    """
    normalized = label.strip().lower().rstrip(":")

    if selector_type == "id":
        # Try id-based mapping first
        if normalized in _ID_FIELD_MAP:
            return _ID_FIELD_MAP[normalized]
        # Fall through to label-based
        normalized_no_caps = normalized.replace("_", " ")
        if normalized_no_caps in _LABEL_FIELD_MAP:
            return _LABEL_FIELD_MAP[normalized_no_caps]
    else:
        if normalized in _LABEL_FIELD_MAP:
            return _LABEL_FIELD_MAP[normalized]

    return "", 0


# -----------------------------------------------------------------------
# JavaScript system info matching
# -----------------------------------------------------------------------


def _match_js_system_info(
    values: list[str],
) -> list[SystemInfoFieldDetail]:
    """Match JS delimited values to system info fields.

    JS system info functions typically have key-value pairs or
    positional fields. This is a best-effort heuristic.
    """
    fields: list[SystemInfoFieldDetail] = []
    seen: set[str] = set()

    for value in values:
        stripped = value.strip()
        if not stripped:
            continue

        # Check if value looks like a system info label
        field_name, _tier = _match_label(stripped, "label")
        if field_name and field_name not in seen:
            seen.add(field_name)
            fields.append(
                SystemInfoFieldDetail(
                    field=field_name,
                    type="string",
                    source=stripped,
                )
            )

    return fields


# -----------------------------------------------------------------------
# JSON system info matching
# -----------------------------------------------------------------------


def _match_json_system_info(
    data: dict[str, Any],
) -> list[SystemInfoFieldDetail]:
    """Match JSON keys to system info fields."""
    fields: list[SystemInfoFieldDetail] = []
    seen: set[str] = set()

    _walk_json_for_sysinfo(data, fields, seen, "")

    return fields


def _walk_json_for_sysinfo(
    data: dict[str, Any],
    fields: list[SystemInfoFieldDetail],
    seen: set[str],
    prefix: str,
) -> None:
    """Recursively walk JSON looking for system info fields."""
    for key, value in data.items():
        normalized = key.strip().lower()

        if normalized in _JSON_SYSINFO_MAP:
            field_name, _tier = _JSON_SYSINFO_MAP[normalized]
            if field_name not in seen and isinstance(value, str | int | float):
                seen.add(field_name)
                source_key = f"{prefix}.{key}" if prefix else key
                fields.append(
                    SystemInfoFieldDetail(
                        field=field_name,
                        type="string",
                        source=source_key,
                    )
                )

        # Recurse into nested dicts (but not lists)
        if isinstance(value, dict):
            child_prefix = f"{prefix}.{key}" if prefix else key
            _walk_json_for_sysinfo(value, fields, seen, child_prefix)
