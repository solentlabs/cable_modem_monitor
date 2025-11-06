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

    # Get current data
    data = coordinator.data if coordinator.data else {}

    # Build diagnostics info
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
            "connection_status": data.get("cable_modem_connection_status", "unknown"),
            "downstream_channel_count": data.get("cable_modem_downstream_channel_count", 0),
            "upstream_channel_count": data.get("cable_modem_upstream_channel_count", 0),
            "downstream_channels_parsed": len(data.get("cable_modem_downstream", [])),
            "upstream_channels_parsed": len(data.get("cable_modem_upstream", [])),
            "total_corrected_errors": data.get("cable_modem_total_corrected", 0),
            "total_uncorrected_errors": data.get("cable_modem_total_uncorrected", 0),
            "software_version": data.get("cable_modem_software_version", "Unknown"),
            "system_uptime": data.get("cable_modem_system_uptime", "Unknown"),
        },
        "downstream_channels": [
            {
                "channel": ch.get("channel_id"),
                "frequency": ch.get("frequency"),
                "power": ch.get("power"),
                "snr": ch.get("snr"),
                "corrected": ch.get("corrected"),
                "uncorrected": ch.get("uncorrected"),
            }
            for ch in data.get("cable_modem_downstream", [])
        ],
        "upstream_channels": [
            {
                "channel": ch.get("channel_id"),
                "frequency": ch.get("frequency"),
                "power": ch.get("power"),
            }
            for ch in data.get("cable_modem_upstream", [])
        ],
    }

    # Add error information if last update failed
    # Security: Sanitize exception messages to avoid leaking sensitive information
    if coordinator.last_exception:
        exception_type = type(coordinator.last_exception).__name__
        exception_msg = str(coordinator.last_exception)

        # Sanitize exception message - remove potential credentials, paths, IPs
        import re
        # Remove anything that looks like credentials (password=, user=, etc.)
        exception_msg = re.sub(r'(password|passwd|pwd|token|key|secret|auth)[\s]*[=:]\s*[^\s,}]+',
                               r'\1=***REDACTED***', exception_msg, flags=re.IGNORECASE)
        # Remove file paths
        exception_msg = re.sub(r'/[^\s,}]+', '/***PATH***', exception_msg)
        # Remove IP addresses (basic pattern)
        exception_msg = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '***IP***', exception_msg)
        # Truncate long messages
        if len(exception_msg) > 200:
            exception_msg = exception_msg[:200] + "... (truncated)"

        diagnostics["last_error"] = {
            "type": exception_type,
            "message": exception_msg,
            "note": "Exception details have been sanitized for security"
        }

    return diagnostics
