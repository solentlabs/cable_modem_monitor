"""Circular log buffer for Cable Modem Monitor diagnostics.

Captures INFO+ logs from cable_modem_monitor loggers into a fixed-size circular
buffer that's always available in diagnostics, independent of HA's logging config.
Oldest entries are automatically dropped when the buffer is full.

This addresses HA 2025.11+ where home-assistant.log was removed for HAOS users
and system_log only captures WARNING/ERROR.

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
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Buffer configuration
MAX_LOG_ENTRIES = 200
LOG_BUFFER_KEY = "log_buffer"

# Our domain - imported late to avoid circular imports
DOMAIN = "cable_modem_monitor"


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
        """Add a log entry to the buffer."""
        # Strip the common prefix for cleaner output
        short_logger = logger.replace("custom_components.cable_modem_monitor.", "")
        self.entries.append(
            LogEntry(
                timestamp=time.time(),
                level=level,
                logger=short_logger,
                message=message,
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

    Installed on the cable_modem_monitor logger to capture all INFO+
    logs while still allowing them to propagate to HA's normal handlers.
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


def setup_log_buffer(hass: HomeAssistant) -> None:
    """Set up the log buffer and install the handler.

    Should be called once during integration setup.

    Args:
        hass: Home Assistant instance
    """
    # Create buffer and store in hass.data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    buffer = LogBuffer()
    hass.data[DOMAIN][LOG_BUFFER_KEY] = buffer

    # Install handler on our root logger
    logger = logging.getLogger(f"custom_components.{DOMAIN}")

    # Check if we already have a BufferingHandler (avoid duplicates on reload)
    for handler in logger.handlers:
        if isinstance(handler, BufferingHandler):
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
