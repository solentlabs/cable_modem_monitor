"""Migrate config entry data from v1 to v2.

v1 entries store parser-era keys (``detected_manufacturer``,
``detected_modem``, ``parser_name``, ``auth_*`` fields).  v2 entries
use catalog-based keys (``manufacturer``, ``model``, ``modem_dir``,
``variant``).

The critical step is resolving v1 display names to a catalog
directory path (``modem_dir``).  This requires walking the catalog
at migration time.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH
from solentlabs.cable_modem_monitor_core.catalog_manager import list_modems

_LOGGER = logging.getLogger(__name__)

# v1 keys that do not exist in v2 and must be removed.
V1_STALE_KEYS = frozenset(
    {
        "parser_name",
        "detected_manufacturer",
        "detected_modem",
        "modem_choice",
        "working_url",
        "parser_selected_at",
        "docsis_version",
        "actual_model",
        "auth_strategy",
        "auth_form_config",
        "auth_hnap_config",
        "auth_url_token_config",
        "auth_discovery_status",
        "auth_discovery_failed",
        "auth_discovery_error",
        "auth_type",
        "auth_captured_response",
    }
)


async def async_migrate(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Migrate a v1 config entry to v2 format.

    Returns True on success, False if catalog resolution fails
    (user must reconfigure through the setup wizard).
    """
    old_data = dict(entry.data)
    _LOGGER.debug("v1 entry data keys: %s", sorted(old_data.keys()))

    # --- Extract v1 fields ---
    detected_mfr = old_data.get("detected_manufacturer", "")
    detected_modem = old_data.get("detected_modem", "")
    model = extract_model(detected_modem, detected_mfr)
    protocol = derive_protocol(old_data)

    # --- Resolve to catalog directory (sync I/O → executor) ---
    modem_dir = await hass.async_add_executor_job(resolve_modem_dir, detected_mfr, model)
    if modem_dir is None:
        _LOGGER.error(
            "Cannot resolve v1 modem to catalog: "
            "manufacturer=%r, model=%r (from detected_modem=%r). "
            "Please reconfigure the integration.",
            detected_mfr,
            model,
            detected_modem,
        )
        return False

    # --- Build v2 data (only v2 keys, no leftovers) ---
    new_data: dict[str, Any] = {
        "manufacturer": detected_mfr,
        "model": model,
        "modem_dir": modem_dir,
        "variant": None,
        "user_selected_modem": detected_modem or old_data.get("modem_choice", ""),
        "entity_prefix": old_data.get("entity_prefix", "none"),
        "host": old_data.get("host", ""),
        "username": old_data.get("username", ""),
        "password": old_data.get("password", ""),
        "protocol": protocol,
        "legacy_ssl": old_data.get("legacy_ssl", False),
        "supports_icmp": old_data.get("supports_icmp", False),
        "supports_head": old_data.get("supports_head", False),
        "scan_interval": old_data.get("scan_interval", 600),
        "health_check_interval": 30,
    }

    hass.config_entries.async_update_entry(entry, data=new_data, version=2)

    _LOGGER.info(
        "Migrated entry %s to v2: manufacturer=%s, model=%s, modem_dir=%s",
        entry.entry_id,
        detected_mfr,
        model,
        modem_dir,
    )
    return True


# ------------------------------------------------------------------
# Pure helpers — testable without HA
# ------------------------------------------------------------------


def extract_model(detected_modem: str, manufacturer: str) -> str:
    """Extract model name from v1 display name.

    v1 stores ``detected_modem`` as ``"{manufacturer} {model}"``
    (e.g., ``"ARRIS SB8200"``).  Strip the manufacturer prefix to
    get the bare model string.
    """
    if manufacturer and detected_modem.startswith(manufacturer):
        return detected_modem[len(manufacturer) :].strip()
    # Fallback: take everything after the last space
    parts = detected_modem.rsplit(" ", 1)
    return parts[-1] if parts else detected_modem


def derive_protocol(data: dict[str, Any]) -> str:
    """Derive protocol from v1 entry data.

    Priority:
        1. Parse scheme from ``working_url`` if present.
        2. ``legacy_ssl`` is True → ``"https"``.
        3. Default ``"http"``.
    """
    working_url = data.get("working_url", "")
    if working_url:
        try:
            parsed = urlparse(working_url)
            if parsed.scheme in ("http", "https"):
                return str(parsed.scheme)
        except Exception:
            pass

    if data.get("legacy_ssl"):
        return "https"

    return "http"


def resolve_modem_dir(manufacturer: str, model: str) -> str | None:
    """Resolve v1 manufacturer + model to a catalog-relative path.

    Walks the catalog and tries three match strategies:

        1. Exact manufacturer + model (case-insensitive).
        2. Exact manufacturer + model alias (case-insensitive).
        3. Model-only match — if exactly one catalog modem has this
           model name or alias regardless of manufacturer.  Handles
           cases where the manufacturer string changed between
           versions.

    Returns:
        Relative path from catalog root (e.g., ``"arris/sb8200"``),
        or ``None`` if no match found.
    """
    summaries = list_modems(CATALOG_PATH)
    mfr_lower = manufacturer.lower()
    model_lower = model.lower()

    # Pass 1: exact manufacturer + model
    for s in summaries:
        if s.manufacturer.lower() == mfr_lower and s.model.lower() == model_lower:
            return _relative_dir(s.path)

    # Pass 2: exact manufacturer + model alias
    for s in summaries:
        if s.manufacturer.lower() == mfr_lower and _has_alias(s, model_lower):
            return _relative_dir(s.path)

    # Pass 3: model-only (handles manufacturer renames)
    matches = [s.path for s in summaries if s.model.lower() == model_lower or _has_alias(s, model_lower)]
    if len(matches) == 1:
        return _relative_dir(matches[0])

    return None


def _has_alias(summary: Any, model_lower: str) -> bool:
    """Check if a modem summary has a matching model alias."""
    return any(alias.lower() == model_lower for alias in summary.model_aliases)


def _relative_dir(path: Path) -> str:
    """Return catalog-relative directory path as a string."""
    return str(path.relative_to(CATALOG_PATH))
