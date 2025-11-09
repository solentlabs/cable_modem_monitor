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
    # Remove anything that looks like credentials
    message = re.sub(
        r"(password|passwd|pwd|token|key|secret|auth|username|user)[\s]*[=:]\s*[^\s,}\]]+",
        r"\1=***REDACTED***",
        message,
        flags=re.IGNORECASE,
    )
    # Remove file paths (but keep relative component paths)
    message = re.sub(r"/config/[^\s,}\]]+", "/config/***PATH***", message)
    message = re.sub(r"/home/[^\s,}\]]+", "/home/***PATH***", message)
    # Remove private IP addresses (but keep common modem IPs for context)
    message = re.sub(
        r"\b(?!192\.168\.100\.1\b)(?:10\.|172\.(?:1[6-9]|2[0-9]|3[01])\.|192\.168\.)\d{1,3}\.\d{1,3}\b",
        "***PRIVATE_IP***",
        message,
    )
    return message


def _get_recent_logs(hass: HomeAssistant, max_records: int = 150) -> list[dict[str, Any]]:
    """Get recent log records for cable_modem_monitor.

    Args:
        hass: Home Assistant instance
        max_records: Maximum number of log records to return

    Returns:
        List of log record dicts with timestamp, level, and message
    """
    import re
    from pathlib import Path

    recent_logs = []

    # Try to read from Home Assistant's log file
    try:
        # Home Assistant stores logs in config/home-assistant.log
        log_file = Path(hass.config.path("home-assistant.log"))

        if not log_file.exists():
            _LOGGER.debug("Log file not found at %s", log_file)
            return [
                {
                    "timestamp": 0,
                    "level": "INFO",
                    "logger": "diagnostics",
                    "message": "Log file not available. Check Home Assistant logs for full history.",
                }
            ]

        # Read last N lines from log file (much faster than reading entire file)
        # Read more lines than max_records to account for non-matching lines
        with open(log_file, "rb") as f:
            # Seek to end of file
            f.seek(0, 2)
            file_size = f.tell()

            # Read last ~100KB (should be plenty for 150 log entries)
            # Average log line is ~200 bytes, so 100KB ~= 500 lines
            read_size = min(100000, file_size)
            f.seek(max(0, file_size - read_size))

            # Read and decode
            tail_data = f.read().decode("utf-8", errors="ignore")
            lines = tail_data.split("\n")

        # Parse log lines for cable_modem_monitor entries
        # Format: 2025-11-09 04:39:46.123 INFO (MainThread) [custom_components.cable_modem_monitor.config_flow] Message
        log_pattern = re.compile(
            r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+"  # timestamp
            r"(\w+)\s+"  # level
            r"\([^)]+\)\s+"  # thread
            r"\[custom_components\.cable_modem_monitor\.?([^\]]*)\]\s+"  # logger
            r"(.+)$"  # message
        )

        for line in lines:
            match = log_pattern.match(line)
            if match:
                timestamp_str, level, logger, message = match.groups()

                # Sanitize the message
                sanitized_message = _sanitize_log_message(message)

                recent_logs.append(
                    {
                        "timestamp": timestamp_str,
                        "level": level,
                        "logger": logger if logger else "__init__",
                        "message": sanitized_message,
                    }
                )

        # If we found logs, return the most recent ones
        if recent_logs:
            return recent_logs[-max_records:]

    except Exception as err:
        _LOGGER.warning("Failed to read logs from file: %s", err)

    # If we couldn't get logs, return a note
    return [
        {
            "timestamp": 0,
            "level": "INFO",
            "logger": "diagnostics",
            "message": "Unable to retrieve recent logs. Check Home Assistant logs for full history.",
        }
    ]


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
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

    # Add error information if last update failed
    # Security: Sanitize exception messages to avoid leaking sensitive information
    if coordinator.last_exception:
        exception_type = type(coordinator.last_exception).__name__
        exception_msg = str(coordinator.last_exception)

        # Sanitize using our helper function
        exception_msg = _sanitize_log_message(exception_msg)

        # Truncate long messages
        if len(exception_msg) > 200:
            exception_msg = exception_msg[:200] + "... (truncated)"

        diagnostics["last_error"] = {
            "type": exception_type,
            "message": exception_msg,
            "note": "Exception details have been sanitized for security",
        }

    # Add recent logs (last 150 records)
    # This is extremely helpful for debugging connection and detection issues
    try:
        recent_logs = _get_recent_logs(hass, max_records=150)
        diagnostics["recent_logs"] = {
            "note": "Recent logs from cable_modem_monitor (sanitized for security)",
            "count": len(recent_logs),
            "logs": recent_logs,
        }
    except Exception as err:
        # If we can't get logs, add a note but don't fail diagnostics
        _LOGGER.warning("Failed to retrieve recent logs for diagnostics: %s", err)
        diagnostics["recent_logs"] = {"note": "Unable to retrieve recent logs", "error": str(err)}

    return diagnostics
