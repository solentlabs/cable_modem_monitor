"""Tests for the log buffer module."""

import logging

from custom_components.cable_modem_monitor.core.log_buffer import (
    BufferingHandler,
    LogBuffer,
    LogEntry,
)


class TestLogEntry:
    """Tests for LogEntry dataclass."""

    def test_to_dict(self):
        """Test LogEntry converts to dict correctly."""
        entry = LogEntry(
            timestamp=1234567890.123,
            level="INFO",
            logger="config_flow",
            message="Test message",
        )
        result = entry.to_dict()

        assert result["timestamp"] == 1234567890.123
        assert result["level"] == "INFO"
        assert result["logger"] == "config_flow"
        assert result["message"] == "Test message"


class TestLogBuffer:
    """Tests for LogBuffer class."""

    def test_add_entry(self):
        """Test adding entries to buffer."""
        buffer = LogBuffer()
        buffer.add("INFO", "custom_components.cable_modem_monitor.config_flow", "Test")

        entries = buffer.get_entries()
        assert len(entries) == 1
        assert entries[0]["level"] == "INFO"
        assert entries[0]["logger"] == "config_flow"  # Prefix stripped
        assert entries[0]["message"] == "Test"

    def test_rotation(self):
        """Test buffer rotates when full."""
        from collections import deque

        buffer = LogBuffer(entries=deque(maxlen=3))

        buffer.add("INFO", "logger", "First")
        buffer.add("INFO", "logger", "Second")
        buffer.add("INFO", "logger", "Third")
        buffer.add("INFO", "logger", "Fourth")

        entries = buffer.get_entries()
        assert len(entries) == 3
        assert entries[0]["message"] == "Second"
        assert entries[2]["message"] == "Fourth"

    def test_clear(self):
        """Test clearing buffer."""
        buffer = LogBuffer()
        buffer.add("INFO", "logger", "Test")
        buffer.clear()

        assert buffer.get_entries() == []


class TestBufferingHandler:
    """Tests for BufferingHandler class."""

    def test_captures_logs(self):
        """Test handler captures log records to buffer."""
        buffer = LogBuffer()
        handler = BufferingHandler(buffer, level=logging.INFO)
        handler.setFormatter(logging.Formatter("%(message)s"))

        # Create a logger and attach handler
        logger = logging.getLogger("test_buffer_handler")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        try:
            logger.info("Test INFO message")
            logger.warning("Test WARNING message")
            logger.debug("Test DEBUG message")  # Should not be captured

            entries = buffer.get_entries()
            assert len(entries) == 2
            assert entries[0]["level"] == "INFO"
            assert entries[1]["level"] == "WARNING"
        finally:
            logger.removeHandler(handler)

    def test_filters_by_level(self):
        """Test handler respects log level filter."""
        buffer = LogBuffer()
        handler = BufferingHandler(buffer, level=logging.WARNING)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = logging.getLogger("test_level_filter")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        try:
            logger.info("INFO - should not capture")
            logger.warning("WARNING - should capture")

            entries = buffer.get_entries()
            assert len(entries) == 1
            assert entries[0]["level"] == "WARNING"
        finally:
            logger.removeHandler(handler)
