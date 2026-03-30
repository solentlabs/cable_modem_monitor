"""Circular log buffer for Cable Modem Monitor diagnostics.

Captures INFO+ logs from both the HA adapter
(``custom_components.cable_modem_monitor``) and Core package
(``solentlabs.cable_modem_monitor_core``) loggers into a fixed-size
circular buffer.  Always available in diagnostics, independent of HA's
logging config.  Oldest entries are automatically dropped when the
buffer is full.

Messages are sanitized and logger prefixes stripped at capture time so
the buffer never holds sensitive data.

This addresses HA 2025.11+ where home-assistant.log was removed for
HAOS users and system_log only captures WARNING/ERROR.

Usage:
    # In __init__.py during setup:
    from .core.log_buffer import setup_log_buffer
    setup_log_buffer(hass)

    # In diagnostics.py:
    from .core.log_buffer import get_log_entries
    logs = get_log_entries(hass)
"""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Buffer configuration
MAX_LOG_ENTRIES = 200
LOG_BUFFER_KEY = "log_buffer"

# Our domain
DOMAIN = "cable_modem_monitor"

# Loggers to capture: HA adapter + Core package
_MONITORED_LOGGERS = (
    f"custom_components.{DOMAIN}",
    "solentlabs.cable_modem_monitor_core",
)

# Prefixes to strip for cleaner diagnostics output (trailing dot included)
_LOGGER_PREFIXES = (
    f"custom_components.{DOMAIN}.",
    "solentlabs.cable_modem_monitor_core.",
)


# ------------------------------------------------------------------
# Shared helpers — used by log_buffer and diagnostics
# ------------------------------------------------------------------


def strip_logger_prefix(logger_name: str) -> str:
    """Strip known logger prefixes for cleaner diagnostics output.

    Removes the HA adapter or Core package prefix so diagnostics show
    ``auth.form`` instead of
    ``solentlabs.cable_modem_monitor_core.auth.form``.
    """
    for prefix in _LOGGER_PREFIXES:
        if logger_name.startswith(prefix):
            return logger_name[len(prefix) :]
    return logger_name


def sanitize_log_message(message: str) -> str:
    """Remove private IPs and file paths from a log message.

    Applied at capture time so the buffer never holds user-specific data.
    We only capture logs from our own code (Core + HA adapter), which
    never logs raw credentials.  Scrubbing targets the two things that
    can leak user environment info: private IPs and filesystem paths.

    The modem gateway IP (192.168.100.1) is preserved — it appears in
    every modem interaction and is not user-specific.
    """
    message = re.sub(r"/config/[^\s,}\]]+", "/config/***PATH***", message)
    message = re.sub(r"/home/[^\s,}\]]+", "/home/***PATH***", message)
    message = re.sub(
        r"\b(?!192\.168\.100\.1\b)" r"(?:10\.|172\.(?:1[6-9]|2[0-9]|3[01])\.|192\.168\.)" r"\d{1,3}\.\d{1,3}\b",
        "***PRIVATE_IP***",
        message,
    )
    return message


# ------------------------------------------------------------------
# Data types
# ------------------------------------------------------------------


@dataclass
class LogEntry:
    """A single log entry."""

    timestamp: float
    level: str
    logger: str
    message: str

    def to_dict(self) -> dict:
        """Convert to dictionary for diagnostics output."""
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
        }


@dataclass
class LogBuffer:
    """Fixed-size circular buffer using deque. Drops oldest when full."""

    entries: deque[LogEntry] = field(default_factory=lambda: deque(maxlen=MAX_LOG_ENTRIES))

    def add(self, level: str, logger: str, message: str) -> None:
        """Add a sanitized log entry to the buffer.

        Logger prefixes are stripped and messages are sanitized at
        capture time so the buffer never holds sensitive data.
        """
        self.entries.append(
            LogEntry(
                timestamp=time.time(),
                level=level,
                logger=strip_logger_prefix(logger),
                message=sanitize_log_message(message),
            )
        )

    def get_entries(self) -> list[dict]:
        """Get all entries as list of dicts."""
        return [entry.to_dict() for entry in self.entries]

    def clear(self) -> None:
        """Clear all entries."""
        self.entries.clear()


class BufferingHandler(logging.Handler):
    """Log handler that captures entries to our buffer.

    Installed on both the HA adapter and Core package loggers to capture
    all INFO+ logs while still allowing them to propagate to HA's normal
    handlers.
    """

    def __init__(self, buffer: LogBuffer, level: int = logging.INFO) -> None:
        """Initialize the handler."""
        super().__init__(level)
        self.buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the buffer."""
        try:
            message = self.format(record)
            self.buffer.add(record.levelname, record.name, message)
        except Exception:
            # Never let logging errors break the application
            self.handleError(record)


# ------------------------------------------------------------------
# Setup and retrieval
# ------------------------------------------------------------------


def setup_log_buffer(hass: HomeAssistant) -> None:
    """Set up the log buffer and install handlers on monitored loggers.

    Attaches a ``BufferingHandler`` to both the HA adapter logger
    (``custom_components.cable_modem_monitor``) and the Core package
    logger (``solentlabs.cable_modem_monitor_core``).  On reload, reuses
    the existing buffer to preserve log history.

    Args:
        hass: Home Assistant instance
    """
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Recover existing buffer (survives reload — loggers are singletons
    # so their handlers persist even when hass.data is cleared)
    buffer = _find_existing_buffer(hass)
    if buffer is None:
        buffer = LogBuffer()
    hass.data[DOMAIN][LOG_BUFFER_KEY] = buffer

    # Attach handler to each monitored logger (skip if already attached)
    for logger_name in _MONITORED_LOGGERS:
        _ensure_handler(logging.getLogger(logger_name), buffer)

    # Sync Core logger level with HA logger.  Core logs under
    # "solentlabs.*", HA adapter under "custom_components.*".  Users
    # setting debug on the HA namespace would otherwise miss all Core
    # logs.  We mirror the HA level but cap it at INFO — HA defaults
    # its root to WARNING, which would suppress Core INFO logs without
    # this cap.  min() ensures: DEBUG HA → DEBUG Core, WARNING HA → INFO Core.
    ha_logger = logging.getLogger(f"custom_components.{DOMAIN}")
    core_logger = logging.getLogger("solentlabs.cable_modem_monitor_core")
    core_logger.setLevel(min(ha_logger.getEffectiveLevel(), logging.INFO))


def _find_existing_buffer(hass: HomeAssistant) -> LogBuffer | None:
    """Find an existing log buffer from hass.data or logger handlers.

    Checks hass.data first (normal path), then falls back to inspecting
    logger handlers (recovers buffer after hass.data is cleared during
    reload).
    """
    if DOMAIN in hass.data:
        buf = hass.data[DOMAIN].get(LOG_BUFFER_KEY)
        if isinstance(buf, LogBuffer):
            return buf
    for logger_name in _MONITORED_LOGGERS:
        for handler in logging.getLogger(logger_name).handlers:
            if isinstance(handler, BufferingHandler):
                return handler.buffer
    return None


def _ensure_handler(logger: logging.Logger, buffer: LogBuffer) -> None:
    """Add a BufferingHandler to the logger if not already present."""
    if any(isinstance(h, BufferingHandler) for h in logger.handlers):
        return
    handler = BufferingHandler(buffer, level=logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def get_log_buffer(hass: HomeAssistant) -> LogBuffer | None:
    """Get the log buffer from hass.data.

    Args:
        hass: Home Assistant instance

    Returns:
        LogBuffer instance or None if not set up
    """
    if DOMAIN not in hass.data:
        return None
    buffer = hass.data[DOMAIN].get(LOG_BUFFER_KEY)
    if isinstance(buffer, LogBuffer):
        return buffer
    return None


def get_log_entries(hass: HomeAssistant) -> list[dict]:
    """Get log entries for diagnostics.

    Args:
        hass: Home Assistant instance

    Returns:
        List of log entry dicts, or empty list if buffer not available
    """
    buffer = get_log_buffer(hass)
    if buffer is None:
        return []
    return buffer.get_entries()
