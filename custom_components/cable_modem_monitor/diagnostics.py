"""Diagnostics support for Cable Modem Monitor.

This module provides comprehensive diagnostics for troubleshooting cable modem
integrations in Home Assistant. It collects and sanitizes:

- Configuration and detection information
- Modem channel data (downstream/upstream)
- Authentication discovery details
- Recent log entries from cable_modem_monitor
- Raw HTML captures (when available, for debugging parsers)

Security:
    All output is sanitized to remove sensitive information:
    - Credentials (passwords, tokens, secrets)
    - Private IP addresses (except common modem IP 192.168.100.1)
    - File paths
    - MAC addresses and serial numbers (via html_helper.sanitize_html)

    Users are warned to manually verify before sharing diagnostics.

Usage:
    Diagnostics are accessed via Home Assistant's "Download diagnostics" button
    on the integration page. The async_get_config_entry_diagnostics() function
    is the entry point called by Home Assistant.

Functions:
    Sanitization:
        _sanitize_log_message: Remove credentials/IPs from log strings
        _sanitize_url_list: Sanitize captured URL content

    Log Retrieval:
        _get_recent_logs: Main log retrieval orchestrator
        _get_logs_from_system_log_handler: Via system_log.handler.records
        _get_logs_from_system_log_direct: Via system_log.records (legacy)
        _get_logs_from_file: Read from home-assistant.log file

    Info Extraction:
        _get_auth_method: Get auth method from parser
        _get_detection_method: Determine how parser was detected
        _get_auth_discovery_info: Get auth discovery data
        _get_hnap_auth_attempt: Get HNAP auth debug info

    Main:
        _build_diagnostics_dict: Assemble full diagnostics dictionary
        async_get_config_entry_diagnostics: HA entry point (async)
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_AUTH_CAPTURED_RESPONSE,
    CONF_AUTH_DISCOVERY_ERROR,
    CONF_AUTH_DISCOVERY_FAILED,
    CONF_AUTH_DISCOVERY_STATUS,
    CONF_AUTH_FORM_CONFIG,
    CONF_AUTH_STRATEGY,
    DOMAIN,
    VERSION,
)
from .core.log_buffer import get_log_entries
from .core.modem_scraper import _get_parser_url_patterns
from .lib.html_helper import sanitize_html

_LOGGER = logging.getLogger(__name__)

# Constants
LOG_TAIL_BYTES = 100_000  # Read last ~100KB from log file (~500 lines)
MAX_LOG_RECORDS = 150  # Maximum log entries to include in diagnostics


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


def _sanitize_url_list(url_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sanitize a list of captured URL entries.

    Args:
        url_list: List of URL data dicts with optional 'content' field

    Returns:
        List of sanitized URL data dicts
    """
    sanitized = []
    for url_data in url_list:
        entry = url_data.copy()
        if "content" in entry:
            entry["content"] = sanitize_html(entry["content"])
            entry["sanitized_size_bytes"] = len(entry["content"])
        sanitized.append(entry)
    return sanitized


def _create_log_entry(
    timestamp: float | str,
    level: str,
    logger: str,
    message: str,
) -> dict[str, Any]:
    """Create a sanitized log entry dictionary.

    Args:
        timestamp: Unix timestamp or ISO string
        level: Log level (INFO, WARNING, ERROR, etc.)
        logger: Logger name (will have prefix stripped)
        message: Log message (will be sanitized)

    Returns:
        Formatted log entry dict
    """
    return {
        "timestamp": timestamp,
        "level": level,
        "logger": str(logger).replace("custom_components.cable_modem_monitor.", ""),
        "message": _sanitize_log_message(str(message)),
    }


def _no_logs_available_entry() -> list[dict[str, Any]]:
    """Return a placeholder when no logs are available.

    Returns:
        List with single informational entry explaining log sources
    """
    return [
        {
            "timestamp": time.time(),
            "level": "INFO",
            "logger": "diagnostics",
            "message": (
                "No logs captured yet. The integration's log buffer may not have "
                "been initialized (happens on first setup). Try reloading the "
                "integration and capturing diagnostics again."
            ),
        }
    ]


def _get_logs_from_system_log_handler(handler: Any) -> list[dict[str, Any]]:
    """Extract logs from system_log handler.records.

    This is the modern HA approach where system_log exposes a DomainData
    object with a handler attribute containing LogRecord objects.

    Args:
        handler: system_log.handler object with records attribute

    Returns:
        List of log entries, empty if no matching logs found
    """
    logs: list[dict[str, Any]] = []

    if not hasattr(handler, "records"):
        _LOGGER.debug("handler.records not found, attributes: %s", dir(handler))
        return logs

    _LOGGER.debug("handler.records found, record count: %d", len(handler.records))

    for record in handler.records:
        if "cable_modem_monitor" in record.name:
            logs.append(
                _create_log_entry(
                    timestamp=record.created,
                    level=record.levelname,
                    logger=record.name,
                    message=record.getMessage(),
                )
            )

    if logs:
        _LOGGER.debug("Retrieved %d logs from system_log handler", len(logs))

    return logs


def _parse_legacy_record(record: Any) -> dict[str, Any] | None:
    """Parse a single record from system_log.records (legacy format).

    Handles multiple record formats:
    - SimpleEntry named tuples with name/message attributes
    - Standard LogRecord objects with getMessage()
    - Legacy tuple format: (name, timestamp, level, message, ...)

    Args:
        record: A log record in various possible formats

    Returns:
        Formatted log entry dict, or None if not a cable_modem_monitor log
    """
    try:
        # Format 1: SimpleEntry or LogRecord-like with name and message attrs
        if hasattr(record, "name") and hasattr(record, "message"):
            if "cable_modem_monitor" not in str(record.name):
                return None

            level = getattr(record, "level", "ERROR")
            if isinstance(level, int):
                level = logging.getLevelName(level)

            timestamp = getattr(record, "timestamp", None) or getattr(record, "created", None)

            return _create_log_entry(
                timestamp=timestamp if timestamp is not None else time.time(),
                level=str(level),
                logger=str(record.name),
                message=str(record.message),
            )

        # Format 2: Standard LogRecord with getMessage()
        if hasattr(record, "getMessage"):
            if "cable_modem_monitor" not in record.name:
                return None

            return _create_log_entry(
                timestamp=record.created,
                level=record.levelname,
                logger=record.name,
                message=record.getMessage(),
            )

        # Format 3: Legacy tuple (name, timestamp, level, message, ...)
        if isinstance(record, tuple) and len(record) >= 4:
            logger_name = record[0]
            if "cable_modem_monitor" not in str(logger_name):
                return None

            timestamp = record[1] if len(record) > 1 else time.time()
            level = record[2] if len(record) > 2 else "ERROR"
            message = record[3] if len(record) > 3 else "Unknown"

            if isinstance(level, int):
                level = logging.getLevelName(level)

            return _create_log_entry(
                timestamp=timestamp,
                level=str(level),
                logger=str(logger_name),
                message=str(message),
            )

    except (IndexError, AttributeError) as e:
        _LOGGER.debug("Error parsing log record: %s", e)

    return None


def _get_logs_from_system_log_direct(system_log: Any) -> list[dict[str, Any]]:
    """Extract logs from system_log.records directly (older HA versions).

    This handles older Home Assistant versions where system_log exposes
    records directly as SimpleEntry named tuples or LogRecord objects.

    Args:
        system_log: system_log object with records attribute

    Returns:
        List of log entries, empty if no matching logs found
    """
    logs: list[dict[str, Any]] = []

    if not hasattr(system_log, "records"):
        return logs

    _LOGGER.debug("system_log.records found (direct), record count: %d", len(system_log.records))

    for record in system_log.records:
        entry = _parse_legacy_record(record)
        if entry:
            logs.append(entry)

    if logs:
        _LOGGER.debug("Retrieved %d error logs from system_log (direct)", len(logs))
    else:
        _LOGGER.debug("No cable_modem_monitor errors found in system_log (only errors/warnings are stored)")

    return logs


def _get_logs_from_file(log_file_path: Path) -> list[dict[str, Any]]:
    """Read logs from a Home Assistant log file.

    Reads the tail of the log file and parses entries matching
    the cable_modem_monitor logger pattern.

    Args:
        log_file_path: Path to the home-assistant.log file

    Returns:
        List of log entries, empty list with info message if file not found
    """
    if not log_file_path.exists():
        _LOGGER.debug("Log file not found at %s", log_file_path)
        return _no_logs_available_entry()

    # Read last N bytes from log file (faster than reading entire file)
    with open(log_file_path, "rb") as f:
        f.seek(0, 2)
        file_size = f.tell()

        read_size = min(LOG_TAIL_BYTES, file_size)
        f.seek(max(0, file_size - read_size))

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

    logs: list[dict[str, Any]] = []
    for line in lines:
        match = log_pattern.match(line)
        if match:
            timestamp_str, level, logger, message = match.groups()
            logs.append(
                _create_log_entry(
                    timestamp=timestamp_str,
                    level=level,
                    logger=logger if logger else "__init__",
                    message=message,
                )
            )

    if logs:
        _LOGGER.debug("Retrieved %d logs from log file", len(logs))

    return logs


def _get_recent_logs(hass: HomeAssistant, max_records: int = MAX_LOG_RECORDS) -> list[dict[str, Any]]:
    """Get recent log records for cable_modem_monitor.

    Attempts multiple methods to retrieve logs:
    1. Our own log buffer (captures INFO+ since integration start)
    2. system_log integration (WARNING/ERROR only)
    3. home-assistant.log file (if enabled, removed in HA 2025.11+ by default)

    Args:
        hass: Home Assistant instance
        max_records: Maximum number of log records to return

    Returns:
        List of log record dicts with timestamp, level, logger, and message
    """
    # Method 1: Our own log buffer (most reliable, captures INFO+)
    logs = get_log_entries(hass)
    if logs:
        _LOGGER.debug("Retrieved %d logs from internal buffer", len(logs))
        return logs[-max_records:]

    # Method 2: Try system_log integration (WARNING/ERROR only)
    try:
        if "system_log" in hass.data:
            system_log = hass.data["system_log"]
            _LOGGER.debug("system_log found in hass.data, type: %s", type(system_log))

            # Try handler.records (modern approach)
            if hasattr(system_log, "handler"):
                _LOGGER.debug("system_log.handler found, type: %s", type(system_log.handler))
                logs = _get_logs_from_system_log_handler(system_log.handler)
                if logs:
                    return logs[-max_records:]

            # Try direct records access (older HA versions)
            logs = _get_logs_from_system_log_direct(system_log)
            if logs:
                return logs[-max_records:]

            _LOGGER.debug("system_log found but no usable records, attributes: %s", dir(system_log))
        else:
            _LOGGER.debug("system_log not found in hass.data, available keys: %s", list(hass.data.keys())[:10])
    except Exception as err:
        _LOGGER.warning("Could not retrieve logs from system_log: %s", err, exc_info=True)

    # Method 3: Try reading from log file (removed in HA 2025.11+ by default)
    try:
        log_file_path = Path(hass.config.path("home-assistant.log"))
        logs = _get_logs_from_file(log_file_path)
        if logs:
            return logs[-max_records:]
    except Exception as err:
        _LOGGER.warning("Failed to read logs from file: %s", err)

    # No logs found from any source
    return _no_logs_available_entry()


def _extract_auth_method(url_patterns: list[dict[str, Any]] | None) -> str:
    """Extract auth method from URL patterns list.

    Pure function that determines auth method from parser URL patterns.

    Args:
        url_patterns: List of URL pattern dicts from parser, or None

    Returns:
        Auth method: "form", "basic", "hnap", "none", etc.
    """
    if not url_patterns:
        return "none"
    return str(url_patterns[0].get("auth_method", "none"))


def _get_auth_method_from_coordinator(coordinator: Any) -> str:
    """Get auth method by extracting URL patterns from coordinator.

    This is a thin wrapper that handles HA object traversal and delegates
    to the pure _extract_auth_method function.

    Uses _get_parser_url_patterns() which checks both modem.yaml config
    (via adapter) and parser class attributes, ensuring correct auth_method
    is reported even for parsers that rely solely on modem.yaml.

    Args:
        coordinator: DataUpdateCoordinator with scraper reference

    Returns:
        Auth method: "form", "basic", "hnap", "none", or "unknown"
    """
    try:
        scraper = getattr(coordinator, "scraper", None)
        if not scraper:
            return "unknown"

        parser = getattr(scraper, "parser", None)
        if not parser:
            return "unknown"

        # Use _get_parser_url_patterns which checks modem.yaml via adapter
        # This fixes incorrect "none" for parsers without class-level url_patterns
        url_patterns = _get_parser_url_patterns(parser)
        return _extract_auth_method(url_patterns)
    except Exception:
        return "unknown"


def _get_detection_method(data: Mapping[str, Any]) -> str:
    """Determine how parser was detected.

    Pure function that analyzes config entry data to determine detection method.

    Args:
        data: Config entry data (MappingProxyType or dict)

    Returns:
        Detection method: "user_selected" or "auto_detected"
    """
    # Prefer explicit detection_method if stored (new entries)
    stored_method = data.get("detection_method")
    if stored_method in ("auto_detected", "user_selected"):
        return str(stored_method)

    # Fallback for legacy entries without detection_method field:
    # Infer from whether modem_choice matches parser_name
    modem_choice = data.get("modem_choice", "auto")
    parser_name = data.get("parser_name")
    last_detection = data.get("last_detection")

    # If modem_choice matches parser_name and we have a detection timestamp,
    # auto-detection ran and cached the result
    if modem_choice == parser_name and last_detection:
        return "auto_detected"
    else:
        # User explicitly selected a specific parser from dropdown
        return "user_selected"


def _get_auth_discovery_info(data: Mapping[str, Any]) -> dict[str, Any]:
    """Get authentication discovery information from config data.

    Pure function that extracts auth debugging info from response-driven
    auth discovery. For modems with unknown auth patterns, captured_response
    contains the login page HTML and headers for debugging.

    Args:
        data: Config entry data (MappingProxyType or dict)

    Returns:
        Dict with auth discovery status, strategy, and debug info
    """
    # Get strategy info
    strategy = data.get(CONF_AUTH_STRATEGY)
    form_config = data.get(CONF_AUTH_FORM_CONFIG)
    status = data.get(CONF_AUTH_DISCOVERY_STATUS, "not_run")
    failed = data.get(CONF_AUTH_DISCOVERY_FAILED, False)
    error = data.get(CONF_AUTH_DISCOVERY_ERROR)
    captured_response = data.get(CONF_AUTH_CAPTURED_RESPONSE)

    info: dict[str, Any] = {
        "status": status,
        "strategy": strategy or "not_set",
    }

    # Include form config if present (for form-based auth debugging)
    if form_config:
        # Sanitize form config - it shouldn't contain sensitive data but be safe
        safe_form_config = {k: v for k, v in form_config.items() if k not in ("password", "secret")}
        info["form_config"] = safe_form_config

    # Include failure info if discovery failed
    if failed:
        info["discovery_failed"] = True
        info["note"] = (
            "Auth discovery failed but modem may still work. " "Please share diagnostics to help improve detection."
        )

    if error:
        info["error"] = _sanitize_log_message(error)

    # Include captured response for unknown patterns (very helpful for debugging)
    if captured_response:
        info["captured_response"] = {
            "status_code": captured_response.get("status_code"),
            "url": captured_response.get("url"),
            "headers": {k: _sanitize_log_message(str(v)) for k, v in captured_response.get("headers", {}).items()},
            # Truncate and sanitize HTML sample
            "html_sample": sanitize_html((captured_response.get("html_sample") or "")[:3000]),
            "note": (
                "Captured response from unknown auth pattern. "
                "This helps developers add support for your modem's auth method."
            ),
        }

    # Add explanation based on strategy
    strategy_notes = {
        "no_auth": "Modem allows anonymous access - no login required",
        "basic_http": "HTTP Basic Auth (401 challenge-response)",
        "form_plain": "HTML form login",
        "hnap_session": "HNAP/SOAP protocol (Arris S33, Motorola MB8611)",
        "url_token_session": "URL-based token auth (SB8200 HTTPS)",
        "unknown": "Unknown auth pattern - captured for debugging",
    }
    if strategy and strategy in strategy_notes:
        description = strategy_notes[strategy]
        # Add encoding detail for form_plain
        if strategy == "form_plain" and form_config:
            encoding = form_config.get("password_encoding", "plain")
            if encoding == "base64":
                description += " with base64-encoded credentials"
            else:
                description += " with plain-text credentials"
        info["strategy_description"] = description

    return info


def _get_hnap_auth_attempt(coordinator) -> dict[str, Any]:
    """Get HNAP authentication attempt details from the parser if available.

    This retrieves the last HNAP login request/response data from the parser's
    JSON builder, which is invaluable for debugging authentication failures.
    Users can compare these requests with what their browser sends to identify
    differences (e.g., missing fields, wrong format).

    Args:
        coordinator: DataUpdateCoordinator with scraper reference

    Returns:
        Dict with auth attempt details or explanatory note if not available
    """
    try:
        # Navigate: coordinator -> scraper -> auth_handler -> hnap_builder
        scraper = getattr(coordinator, "scraper", None)
        if not scraper:
            return {"note": "Scraper not available"}

        auth_handler = getattr(scraper, "_auth_handler", None)
        if not auth_handler:
            return {"note": "Auth handler not available (might be using no-auth mode)"}

        json_builder = auth_handler.get_hnap_builder()
        if not json_builder:
            return {"note": "Not an HNAP modem (no JSON builder)"}

        auth_attempt = json_builder.get_last_auth_attempt()
        if not auth_attempt:
            return {"note": "No HNAP auth attempt recorded yet"}

        # Sanitize the auth attempt data
        sanitized: dict[str, Any] = {}
        for key, value in auth_attempt.items():
            if value is None:
                sanitized[key] = None
            elif isinstance(value, str):
                sanitized[key] = _sanitize_log_message(value)
            elif isinstance(value, dict):
                # For request dicts, keep structure but sanitize strings
                sanitized[key] = {
                    k: _sanitize_log_message(str(v)) if isinstance(v, str) else v for k, v in value.items()
                }
            else:
                sanitized[key] = value

        return {
            "note": "HNAP auth attempt captured - compare with browser Network tab",
            "data": sanitized,
        }

    except Exception as e:
        _LOGGER.debug("Error getting HNAP auth attempt: %s", e)
        return {"note": f"Error retrieving auth data: {type(e).__name__}"}


def _build_diagnostics_dict(hass: HomeAssistant, coordinator, entry: ConfigEntry) -> dict[str, Any]:
    """Build the main diagnostics dictionary from coordinator data."""
    data = coordinator.data if coordinator.data else {}

    diagnostics = {
        # Solent Labs™ metadata - helps identify official diagnostics captures
        "_solentlabs": {
            "tool": "cable_modem_monitor/diagnostics",
            "version": VERSION,
            "captured_at": datetime.now().isoformat(),
            "note": "Captured with Solent Labs™ Cable Modem Monitor diagnostics",
        },
        # PII review guidance - displayed prominently for users sharing diagnostics
        "_review_before_sharing": {
            "warning": (
                "Automated sanitization is best-effort, not foolproof. "
                "Modem manufacturers store data in unpredictable formats. "
                "Please verify your credentials are not present before sharing."
            ),
            "checklist": [
                "Search this file for your WiFi network name (SSID)",
                "Search this file for your WiFi password",
                "Search this file for your router admin password",
                "Check that public IPs show as ***PUBLIC_IP***",
            ],
            "how_to_search": "Use Ctrl+F (Cmd+F on Mac) in your text editor",
            "if_you_find_credentials": (
                "Replace them with ***REDACTED*** and note it in your GitHub issue " "so we can improve the sanitizer."
            ),
            "documentation": "https://github.com/solentlabs/cable_modem_monitor/blob/main/docs/MODEM_REQUEST.md",
        },
        "config_entry": {
            "title": entry.title,
            "host": entry.data.get("host"),
            "has_credentials": bool(entry.data.get("username") and entry.data.get("password")),
            "supports_icmp": entry.data.get("supports_icmp", False),
        },
        "detection": {
            "method": _get_detection_method(entry.data),
            "user_selection": entry.data.get("modem_choice", "auto"),
            "parser": entry.data.get("parser_name", "Unknown"),
            "manufacturer": entry.data.get("detected_manufacturer", "Unknown"),
            "model": entry.data.get("detected_modem", "Unknown"),
            "docsis_version": entry.data.get("docsis_version", "Unknown"),
            "working_url": entry.data.get("working_url") or "Unknown",
            "protocol": "https" if (entry.data.get("working_url") or "").startswith("https") else "http",
            "auth_method": _get_auth_method_from_coordinator(coordinator),
            "legacy_ssl": entry.data.get("legacy_ssl", False),
            "last_detection": entry.data.get("last_detection", "Never"),
        },
        # Auth discovery info - shows how authentication was detected
        "auth_discovery": _get_auth_discovery_info(entry.data),
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
                "modulation": ch.get("modulation"),
                "channel_type": ch.get("channel_type"),
            }
            for ch in data.get("cable_modem_downstream", [])
        ],
        "upstream_channels": [
            {
                "channel": ch.get("channel_id"),
                "frequency": ch.get("frequency"),
                "power": ch.get("power"),
                "modulation": ch.get("modulation"),
                "channel_type": ch.get("channel_type"),
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

    # Add HNAP authentication attempt details if available
    # This helps debug auth failures by showing exactly what requests we sent
    diagnostics["hnap_auth_debug"] = _get_hnap_auth_attempt(coordinator)

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
        try:
            expires_at = datetime.fromisoformat(capture.get("ttl_expires", ""))
            if datetime.now() < expires_at:
                # Sanitize content in captured URLs and failed URLs
                sanitized_urls = _sanitize_url_list(capture.get("urls", []))
                sanitized_failed = _sanitize_url_list(capture.get("failed_urls", []))

                diagnostics["raw_html_capture"] = {
                    "captured_at": capture.get("timestamp"),
                    "expires_at": capture.get("ttl_expires"),
                    "trigger": capture.get("trigger", "unknown"),
                    "note": (
                        "Raw HTML has been sanitized to remove sensitive information "
                        "(MACs, serials, passwords, private IPs)"
                    ),
                    "url_count": len(sanitized_urls),
                    "failed_url_count": len(sanitized_failed),
                    "total_size_kb": sum(u.get("size_bytes", 0) for u in sanitized_urls) / 1024,
                    "urls": sanitized_urls,
                    "failed_urls": sanitized_failed,
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

    # Run diagnostics building in executor to avoid blocking I/O in event loop
    # (_get_recent_logs reads from log file which is blocking)
    return cast(
        dict[str, Any],
        await hass.async_add_executor_job(_build_diagnostics_dict, hass, coordinator, entry),
    )
