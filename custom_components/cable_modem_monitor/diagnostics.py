"""Diagnostics support for Cable Modem Monitor."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .utils.html_helper import sanitize_html

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


def _get_recent_logs(hass: HomeAssistant, max_records: int = 150) -> list[dict[str, Any]]:  # noqa: C901
    """Get recent log records for cable_modem_monitor.

    Args:
        hass: Home Assistant instance
        max_records: Maximum number of log records to return

    Returns:
        List of log record dicts with timestamp, level, and message
    """
    from pathlib import Path

    recent_logs = []

    # Method 1: Try to get logs from system_log integration (if available)
    try:
        if "system_log" in hass.data:
            system_log = hass.data["system_log"]
            _LOGGER.debug("system_log found in hass.data, type: %s", type(system_log))

            # system_log exposes a DomainData object with a handler attribute
            if hasattr(system_log, "handler"):
                handler = system_log.handler
                _LOGGER.debug("system_log.handler found, type: %s", type(handler))

                if hasattr(handler, "records"):
                    _LOGGER.debug("handler.records found, record count: %d", len(handler.records))
                    for record in handler.records:
                        # Filter for cable_modem_monitor logs
                        if "cable_modem_monitor" in record.name:
                            sanitized_message = _sanitize_log_message(record.getMessage())
                            recent_logs.append(
                                {
                                    "timestamp": record.created,
                                    "level": record.levelname,
                                    "logger": record.name.replace("custom_components.cable_modem_monitor.", ""),
                                    "message": sanitized_message,
                                }
                            )

                    # If we found logs via system_log, return them
                    if recent_logs:
                        _LOGGER.debug("Retrieved %d logs from system_log handler", len(recent_logs))
                        return recent_logs[-max_records:]
                else:
                    _LOGGER.debug("handler.records not found, attributes: %s", dir(handler))
            # Also try direct records access (older HA versions)
            elif hasattr(system_log, "records"):
                _LOGGER.debug("system_log.records found (direct), record count: %d", len(system_log.records))

                # system_log only stores errors/warnings, not INFO/DEBUG logs
                # Record format is: (logger_name, (file, line_num), exception_or_none)
                for record in system_log.records:
                    try:
                        if isinstance(record, tuple) and len(record) >= 3:
                            logger_name, location_info, exception_info = record[0], record[1], record[2]

                            # Filter for cable_modem_monitor logs
                            if "cable_modem_monitor" in str(logger_name):
                                # Extract file and line number if available
                                file_info = ""
                                if isinstance(location_info, tuple) and len(location_info) >= 2:
                                    file_info = f" at {location_info[0]}:{location_info[1]}"

                                # Format the message
                                message = f"Error{file_info}"
                                if exception_info:
                                    message += f": {str(exception_info)[:200]}"

                                sanitized_message = _sanitize_log_message(message)
                                recent_logs.append(
                                    {
                                        "timestamp": 0,  # system_log doesn't store timestamp in this format
                                        "level": "ERROR",  # system_log only stores errors/warnings
                                        "logger": str(logger_name).replace(
                                            "custom_components.cable_modem_monitor.", ""
                                        ),
                                        "message": sanitized_message,
                                    }
                                )
                        elif hasattr(record, "name"):
                            # LogRecord object format (fallback for older versions)
                            if "cable_modem_monitor" in record.name:
                                sanitized_message = _sanitize_log_message(record.getMessage())
                                recent_logs.append(
                                    {
                                        "timestamp": record.created,
                                        "level": record.levelname,
                                        "logger": record.name.replace("custom_components.cable_modem_monitor.", ""),
                                        "message": sanitized_message,
                                    }
                                )
                    except (IndexError, AttributeError) as e:
                        _LOGGER.debug("Error parsing log record: %s", e)
                        continue

                # If we found logs via system_log, return them
                if recent_logs:
                    _LOGGER.debug("Retrieved %d error logs from system_log (direct)", len(recent_logs))
                    return recent_logs[-max_records:]
                else:
                    _LOGGER.debug("No cable_modem_monitor errors found in system_log (only errors/warnings are stored)")
            else:
                _LOGGER.debug("system_log found but no records/handler attribute, attributes: %s", dir(system_log))
        else:
            _LOGGER.debug("system_log not found in hass.data, available keys: %s", list(hass.data.keys())[:10])
    except Exception as err:
        _LOGGER.warning("Could not retrieve logs from system_log: %s", err, exc_info=True)

    # Method 2: Try to read from Home Assistant's log file
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
                    "message": (
                        "No logs available in diagnostics. "
                        "Note: system_log only captures errors/warnings, not INFO/DEBUG logs. "
                        "For full logs: 1) Check HA logs UI, 2) Use 'journalctl -u home-assistant' (supervised), "
                        "or 3) Check container logs (Docker/dev environments)."
                    ),
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
            _LOGGER.debug("Retrieved %d logs from log file", len(recent_logs))
            return recent_logs[-max_records:]

    except Exception as err:
        _LOGGER.warning("Failed to read logs from file: %s", err)

    # If we couldn't get logs, return a note
    return [
        {
            "timestamp": 0,
            "level": "INFO",
            "logger": "diagnostics",
            "message": (
                "No logs available in diagnostics. "
                "Note: system_log only captures errors/warnings, not INFO/DEBUG logs. "
                "For full logs: 1) Check HA logs UI, 2) Use 'journalctl -u home-assistant' (supervised), "
                "or 3) Check container logs (Docker/dev environments)."
            ),
        }
    ]


def _get_detection_method(entry: ConfigEntry) -> str:
    """Determine how parser was detected.

    Args:
        entry: Config entry to analyze

    Returns:
        Detection method: "user_selected", "cached", or "auto_detected"
    """
    modem_choice = entry.data.get("modem_choice", "auto")
    cached_parser = entry.data.get("parser_name")

    if modem_choice != "auto":
        return "user_selected"
    elif cached_parser:
        return "cached"
    else:
        return "auto_detected"


def _build_diagnostics_dict(hass: HomeAssistant, coordinator, entry: ConfigEntry) -> dict[str, Any]:
    """Build the main diagnostics dictionary from coordinator data."""
    data = coordinator.data if coordinator.data else {}

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
            "parser_detection": {
                "user_selected": entry.data.get("modem_choice", "not_set"),
                "auto_detection_used": entry.data.get("modem_choice", "auto") == "auto",
                "detection_method": _get_detection_method(entry),
                "parser_class": entry.data.get("parser_name", "Unknown"),
            },
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
            "health_status": data.get("health_status", "not_available"),
            "health_diagnosis": data.get("health_diagnosis", ""),
            "ping_success": data.get("ping_success", False),
            "ping_latency_ms": data.get("ping_latency_ms"),
            "http_success": data.get("http_success", False),
            "http_latency_ms": data.get("http_latency_ms"),
            "consecutive_failures": data.get("consecutive_failures", 0),
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

    # Add parser detection history if available (helpful for troubleshooting)
    if "_parser_detection_history" in data:
        diagnostics["parser_detection_history"] = data["_parser_detection_history"]
    else:
        diagnostics["parser_detection_history"] = {
            "note": "Parser detection succeeded on first attempt",
            "attempted_parsers": [],
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

    # Add raw HTML capture if available and not expired
    if coordinator.data and "_raw_html_capture" in coordinator.data:
        capture = coordinator.data["_raw_html_capture"]

        # Check if capture has expired (5 minute TTL)
        from datetime import datetime

        try:
            expires_at = datetime.fromisoformat(capture.get("ttl_expires", ""))
            if datetime.now() < expires_at:
                # Sanitize HTML in each captured URL
                sanitized_urls = []
                for url_data in capture.get("urls", []):
                    sanitized_url = url_data.copy()
                    if "html" in sanitized_url:
                        sanitized_url["html"] = sanitize_html(sanitized_url["html"])
                        # Add size info for sanitized HTML
                        sanitized_url["sanitized_size_bytes"] = len(sanitized_url["html"])
                    sanitized_urls.append(sanitized_url)

                diagnostics["raw_html_capture"] = {
                    "captured_at": capture.get("timestamp"),
                    "expires_at": capture.get("ttl_expires"),
                    "trigger": capture.get("trigger", "unknown"),
                    "note": (
                        "Raw HTML has been sanitized to remove sensitive information "
                        "(MACs, serials, passwords, private IPs)"
                    ),
                    "url_count": len(sanitized_urls),
                    "total_size_kb": sum(u.get("size_bytes", 0) for u in sanitized_urls) / 1024,
                    "urls": sanitized_urls,
                }
                _LOGGER.info("Including raw HTML capture in diagnostics (%d URLs)", len(sanitized_urls))
            else:
                _LOGGER.debug("Raw HTML capture has expired, not including in diagnostics")
        except (ValueError, TypeError) as e:
            _LOGGER.warning("Error checking HTML capture expiry: %s", e)

    return diagnostics


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    # Check if coordinator exists (might not if setup failed)
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    if not coordinator:
        # Return basic diagnostics if coordinator doesn't exist
        return {
            "error": "Integration not fully initialized - coordinator not found",
            "config_entry": {
                "title": entry.title,
                "host": entry.data.get("host"),
                "entry_id": entry.entry_id,
                "state": str(entry.state),
            },
        }

    return _build_diagnostics_dict(hass, coordinator, entry)
