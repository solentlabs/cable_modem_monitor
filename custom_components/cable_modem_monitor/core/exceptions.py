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


class ParsingError(Exception):
    """Error wrapping parsing failures with field context.

    Raised when HTML/JSON/XML parsing fails. Provides context about
    what field or data was being parsed when the error occurred.

    Attributes:
        field: Name of the field being parsed (e.g., "downstream_power")
        raw_value: The raw value that failed to parse
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        raw_value: str | None = None,
    ):
        """Initialize parsing error with context.

        Args:
            message: Human-readable error description
            field: Name of the field being parsed
            raw_value: The raw value that failed to parse
        """
        super().__init__(message)
        self.field = field
        self.raw_value = raw_value

    def __str__(self) -> str:
        """Format error with context."""
        parts = [super().__str__()]
        if self.field:
            parts.append(f"field={self.field}")
        if self.raw_value is not None:
            # Truncate long values
            display_value = self.raw_value[:50] + "..." if len(self.raw_value) > 50 else self.raw_value
            parts.append(f"raw_value={display_value!r}")
        return " | ".join(parts)


class ResourceFetchError(Exception):
    """Error for HTTP fetch failures with URL/status context.

    Raised when fetching a resource from the modem fails. Provides
    context about the URL and HTTP status code.

    Attributes:
        url: The URL that failed to fetch
        status_code: HTTP status code (if received)
    """

    def __init__(
        self,
        message: str,
        url: str | None = None,
        status_code: int | None = None,
    ):
        """Initialize fetch error with context.

        Args:
            message: Human-readable error description
            url: The URL that failed to fetch
            status_code: HTTP status code if available
        """
        super().__init__(message)
        self.url = url
        self.status_code = status_code

    def __str__(self) -> str:
        """Format error with context."""
        parts = [super().__str__()]
        if self.url:
            parts.append(f"url={self.url}")
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        return " | ".join(parts)
