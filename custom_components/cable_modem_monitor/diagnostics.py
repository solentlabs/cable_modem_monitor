"""Diagnostics support for Cable Modem Monitor."""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _sanitize_log_message(message: str) -> str:
    """Sanitize log message to remove sensitive information.

    Args:
        message: Raw log message

    Returns:
        Sanitized message with credentials, IPs, and paths redacted
    """
    ***REMOVED*** Remove anything that looks like credentials
    message = re.sub(
        r'(password|passwd|pwd|token|key|secret|auth|username|user)[\s]*[=:]\s*[^\s,}\]]+',
        r'\1=***REDACTED***',
        message,
        flags=re.IGNORECASE
    )
    ***REMOVED*** Remove file paths (but keep relative component paths)
    message = re.sub(r'/config/[^\s,}\]]+', '/config/***PATH***', message)
    message = re.sub(r'/home/[^\s,}\]]+', '/home/***PATH***', message)
    ***REMOVED*** Remove private IP addresses (but keep common modem IPs for context)
    message = re.sub(
        r'\b(?!192\.168\.100\.1\b)(?:10\.|172\.(?:1[6-9]|2[0-9]|3[01])\.|192\.168\.)\d{1,3}\.\d{1,3}\b',
        '***PRIVATE_IP***',
        message
    )
    return message


def _get_recent_logs(max_records: int = 150) -> list[dict[str, Any]]:
    """Get recent log records for cable_modem_monitor.

    Args:
        max_records: Maximum number of log records to return

    Returns:
        List of log record dicts with timestamp, level, and message
    """
    ***REMOVED*** Get the logger for our component
    component_logger = logging.getLogger('custom_components.cable_modem_monitor')

    ***REMOVED*** Try to get log records from handlers
    ***REMOVED*** Home Assistant uses a QueueHandler with a MemoryHandler
    recent_logs = []

    ***REMOVED*** Walk up the logger hierarchy to find handlers with records
    current_logger = component_logger
    while current_logger:
        for handler in current_logger.handlers:
            ***REMOVED*** Check if handler has a buffer (MemoryHandler)
            if hasattr(handler, 'buffer'):
                ***REMOVED*** Get records from buffer
                for record in handler.buffer[-max_records:]:
                    if record.name.startswith('custom_components.cable_modem_monitor'):
                        recent_logs.append({
                            'timestamp': record.created,
                            'level': record.levelname,
                            'logger': record.name.replace('custom_components.cable_modem_monitor.', ''),
                            'message': _sanitize_log_message(record.getMessage())
                        })

        ***REMOVED*** Move up the hierarchy
        if not current_logger.propagate:
            break
        current_logger = current_logger.parent

    ***REMOVED*** If we didn't get logs from handlers, return a note
    if not recent_logs:
        recent_logs.append({
            'timestamp': 0,
            'level': 'INFO',
            'logger': 'diagnostics',
            'message': 'No recent logs available in memory. Check Home Assistant logs for full history.'
        })

    ***REMOVED*** Sort by timestamp (most recent last) and limit
    recent_logs.sort(key=lambda x: x.get('timestamp', 0))
    return recent_logs[-max_records:]


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
            "modem_choice": entry.data.get("modem_choice", "not_set"),
            "detected_modem": entry.data.get("detected_modem", "Unknown"),
            "detected_manufacturer": entry.data.get("detected_manufacturer", "Unknown"),
            "parser_name": entry.data.get("parser_name", "Unknown"),
            "working_url": entry.data.get("working_url", "Unknown"),
            "last_detection": entry.data.get("last_detection", "Never"),
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

    ***REMOVED*** Add error information if last update failed
    ***REMOVED*** Security: Sanitize exception messages to avoid leaking sensitive information
    if coordinator.last_exception:
        exception_type = type(coordinator.last_exception).__name__
        exception_msg = str(coordinator.last_exception)

        ***REMOVED*** Sanitize using our helper function
        exception_msg = _sanitize_log_message(exception_msg)

        ***REMOVED*** Truncate long messages
        if len(exception_msg) > 200:
            exception_msg = exception_msg[:200] + "... (truncated)"

        diagnostics["last_error"] = {
            "type": exception_type,
            "message": exception_msg,
            "note": "Exception details have been sanitized for security"
        }

    ***REMOVED*** Add recent logs (last 150 records)
    ***REMOVED*** This is extremely helpful for debugging connection and detection issues
    try:
        recent_logs = _get_recent_logs(max_records=150)
        diagnostics["recent_logs"] = {
            "note": "Recent logs from cable_modem_monitor (sanitized for security)",
            "count": len(recent_logs),
            "logs": recent_logs
        }
    except Exception as err:
        ***REMOVED*** If we can't get logs, add a note but don't fail diagnostics
        _LOGGER.warning("Failed to retrieve recent logs for diagnostics: %s", err)
        diagnostics["recent_logs"] = {
            "note": "Unable to retrieve recent logs",
            "error": str(err)
        }

    return diagnostics
