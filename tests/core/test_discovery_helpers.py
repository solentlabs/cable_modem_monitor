"""Tests for Parser Discovery Helpers."""

from __future__ import annotations

import pytest

from custom_components.cable_modem_monitor.core.discovery_helpers import ParserNotFoundError


class TestParserNotFoundError:
    """Test ParserNotFoundError exception."""

    def test_exception_creation(self):
        """Test creating ParserNotFoundError."""
        error = ParserNotFoundError("Test message")

        assert str(error) == "Test message"
        assert isinstance(error, Exception)

    def test_exception_can_be_raised(self):
        """Test that exception can be raised and caught."""
        with pytest.raises(ParserNotFoundError) as exc_info:
            raise ParserNotFoundError("No parser found")

        assert "No parser found" in str(exc_info.value)

    def test_exception_with_details(self):
        """Test exception with detailed message."""
        message = "No parser found for modem: Arris SB6183"
        error = ParserNotFoundError(message)

        assert "Arris SB6183" in str(error)
        assert "No parser found" in str(error)
