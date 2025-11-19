"""Tests for Parser Discovery Helpers."""

from __future__ import annotations

import pytest

from custom_components.cable_modem_monitor.core.discovery_helpers import ParserNotFoundError


class TestParserNotFoundError:
    """Test ParserNotFoundError exception."""

    def test_exception_creation_default(self):
        """Test creating ParserNotFoundError with defaults."""
        error = ParserNotFoundError()

        assert str(error) == "Could not detect modem type. No parser matched."
        assert isinstance(error, Exception)
        assert error.modem_info == {}
        assert error.attempted_parsers == []

    def test_exception_with_modem_info(self):
        """Test creating ParserNotFoundError with modem info."""
        modem_info = {"title": "Arris SB6183", "model": "SB6183"}
        error = ParserNotFoundError(modem_info=modem_info)

        assert str(error) == "Could not detect modem type. No parser matched."
        assert error.modem_info == modem_info
        assert error.modem_info["title"] == "Arris SB6183"

    def test_exception_with_attempted_parsers(self):
        """Test exception with list of attempted parsers."""
        attempted = ["ArrisSB6190", "ArrisSB6141", "GenericParser"]
        error = ParserNotFoundError(attempted_parsers=attempted)

        assert str(error) == "Could not detect modem type. No parser matched."
        assert error.attempted_parsers == attempted
        assert len(error.attempted_parsers) == 3

    def test_exception_can_be_raised(self):
        """Test that exception can be raised and caught."""
        with pytest.raises(ParserNotFoundError) as exc_info:
            raise ParserNotFoundError()

        # Assertions after context exit
        error_msg = str(exc_info.value)
        assert "Could not detect modem type" in error_msg
        assert "No parser matched" in error_msg

    def test_get_user_message(self):
        """Test user-friendly error message generation."""
        modem_info = {"title": "Netgear CM1000"}
        attempted = ["NetgearCM600", "GenericParser"]
        error = ParserNotFoundError(modem_info=modem_info, attempted_parsers=attempted)

        user_message = error.get_user_message()

        assert "Netgear CM1000" in user_message
        assert "Tried 2 parsers" in user_message
        assert "not be supported" in user_message

    def test_get_troubleshooting_steps(self):
        """Test troubleshooting steps are provided."""
        error = ParserNotFoundError()
        steps = error.get_troubleshooting_steps()

        assert isinstance(steps, list)
        assert len(steps) > 0
        assert any("IP address" in step for step in steps)
        assert any("GitHub issue" in step for step in steps)

    def test_exception_with_full_context(self):
        """Test exception with complete context information."""
        modem_info = {
            "title": "Motorola MB8611",
            "manufacturer": "Motorola",
            "model": "MB8611",
        }
        attempted = ["MotorolaMB8600", "MotorolaMB7621", "GenericMotorola"]

        error = ParserNotFoundError(modem_info=modem_info, attempted_parsers=attempted)

        # Verify all context is stored
        assert error.modem_info["manufacturer"] == "Motorola"
        assert error.modem_info["model"] == "MB8611"
        assert "MotorolaMB8600" in error.attempted_parsers
        assert "MotorolaMB7621" in error.attempted_parsers

        # Verify user message includes context
        user_msg = error.get_user_message()
        assert "MB8611" in user_msg
        assert "3 parsers" in user_msg
