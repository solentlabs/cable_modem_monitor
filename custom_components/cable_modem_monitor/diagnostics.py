"""Diagnostics support for Cable Modem Monitor."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    ***REMOVED*** Get current data
    data = coordinator.data if coordinator.data else {}

    ***REMOVED*** Build diagnostics info
    diagnostics = {
        "config_entry": {
            "title": entry.title,
            "host": entry.data.get("host"),
            "has_credentials": bool(entry.data.get("username") and entry.data.get("password")),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
        },
        "modem_data": {
            "connection_status": data.get("connection_status", "unknown"),
            "downstream_channel_count": data.get("downstream_channel_count", 0),
            "upstream_channel_count": data.get("upstream_channel_count", 0),
            "downstream_channels_parsed": len(data.get("downstream", [])),
            "upstream_channels_parsed": len(data.get("upstream", [])),
            "total_corrected_errors": data.get("total_corrected", 0),
            "total_uncorrected_errors": data.get("total_uncorrected", 0),
            "software_version": data.get("software_version", "Unknown"),
            "system_uptime": data.get("system_uptime", "Unknown"),
        },
        "downstream_channels": [
            {
                "channel": ch.get("channel"),
                "frequency": ch.get("frequency"),
                "power": ch.get("power"),
                "snr": ch.get("snr"),
                "corrected": ch.get("corrected"),
                "uncorrected": ch.get("uncorrected"),
            }
            for ch in data.get("downstream", [])
        ],
        "upstream_channels": [
            {
                "channel": ch.get("channel"),
                "frequency": ch.get("frequency"),
                "power": ch.get("power"),
            }
            for ch in data.get("upstream", [])
        ],
    }

    ***REMOVED*** Add error information if last update failed
    if coordinator.last_exception:
        diagnostics["last_error"] = {
            "type": type(coordinator.last_exception).__name__,
            "message": str(coordinator.last_exception),
        }

    return diagnostics
