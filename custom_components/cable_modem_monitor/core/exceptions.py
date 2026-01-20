"""Exceptions for cable modem monitoring.

These exceptions are raised during modem discovery and validation.
They are independent of Home Assistant and can be used in any context.
"""

from __future__ import annotations


class CannotConnectError(Exception):
    """Error to indicate we cannot connect to the modem.

    Raised for network connectivity issues, timeouts, or connection refused.
    """

    def __init__(self, message: str | None = None):
        """Initialize error with optional message."""
        super().__init__(message or "Cannot connect to modem")
        self.user_message = message


class InvalidAuthError(Exception):
    """Error to indicate authentication failed.

    Raised when credentials are rejected by the modem.
    """


class UnsupportedModemError(Exception):
    """Error to indicate modem is not supported.

    Raised when no parser matches the modem's response.
    """
