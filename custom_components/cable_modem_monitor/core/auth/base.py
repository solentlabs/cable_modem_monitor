"""Base classes for authentication strategies."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .types import AuthErrorType

if TYPE_CHECKING:
    import requests

    from .configs import AuthConfig

_LOGGER = logging.getLogger(__name__)


def get_cookie_safe(session: requests.Session, name: str) -> str | None:
    """Safely get a cookie value by name, handling duplicate cookies.

    Some modems (e.g., SB8200 business firmware) set the same cookie name
    with different paths (e.g., "/" and "/cmconnectionstatus.html"). This
    function handles that edge case by preferring non-empty values and
    root path cookies.

    Args:
        session: requests.Session with cookies
        name: Cookie name to look up

    Returns:
        Cookie value if found, None otherwise

    Raises:
        ValueError: If more than 2 cookies with the same name exist
    """

    # Collect all cookies with matching name, filtering out empty values
    # Some modems (SB8200 business) set empty cookie on landing page,
    # then real value on login - we want the real value
    matches = [(c.value, c.path) for c in session.cookies if c.name == name and c.value]

    if len(matches) == 0:
        return None

    if len(matches) == 1:
        return matches[0][0]

    if len(matches) == 2:
        # Prefer root path "/" over specific path
        for value, path in matches:
            if path == "/":
                return value
        # No root path, return first match
        _LOGGER.debug(
            "Two %s cookies with non-root paths %s, using first",
            name,
            [m[1] for m in matches],
        )
        return matches[0][0]

    # 3+ cookies is unexpected - log details and raise
    paths = [m[1] for m in matches]
    raise ValueError(
        f"Unexpected: {len(matches)} cookies named '{name}' with paths {paths}. "
        "Expected at most 2 (root and page-specific)."
    )


@dataclass
class AuthResult:
    """Result of an authentication attempt.

    Provides structured information about success/failure, error type,
    and response data. The error_type field enables callers to provide
    specific feedback to users about why auth failed.

    Attributes:
        success: Whether authentication succeeded
        response_html: HTML from authenticated page (if applicable)
        error_type: Classification of error (NONE if success=True)
        error_message: Human-readable error description (if failed)
        requires_retry: Whether the caller should retry (e.g., session expired)

    Note:
        This class is iterable for backward compatibility with code that
        unpacks the result as `success, html = handler.authenticate(...)`.
    """

    success: bool
    response_html: str | None = None
    error_type: AuthErrorType = AuthErrorType.NONE
    error_message: str | None = None
    requires_retry: bool = False

    def __iter__(self):
        """Allow unpacking as (success, html) for backward compatibility."""
        return iter((self.success, self.response_html))

    @classmethod
    def ok(cls, response_html: str | None = None) -> AuthResult:
        """Create successful result."""
        return cls(success=True, response_html=response_html)

    @classmethod
    def fail(
        cls,
        error_type: AuthErrorType,
        message: str | None = None,
        response_html: str | None = None,
        requires_retry: bool = False,
    ) -> AuthResult:
        """Create failure result with error classification."""
        return cls(
            success=False,
            response_html=response_html,
            error_type=error_type,
            error_message=message,
            requires_retry=requires_retry,
        )


class AuthStrategy(ABC):
    """Abstract base class for authentication strategies.

    All authentication strategies must implement the login() method.
    The login method modifies the session in-place (e.g., setting cookies,
    auth headers) and returns an AuthResult with success/failure details.
    """

    @abstractmethod
    def login(
        self,
        session: requests.Session,
        base_url: str,
        username: str | None,
        password: str | None,
        config: AuthConfig,
        verbose: bool = False,
    ) -> AuthResult:
        """Authenticate with the modem.

        Args:
            session: requests.Session object (modified in-place)
            base_url: Modem base URL (e.g., "http://192.168.100.1")
            username: Username for authentication
            password: Password for authentication
            config: Authentication configuration object
            verbose: If True, log at INFO level (for config_flow discovery).
                     If False, log at DEBUG level (for routine polling).

        Returns:
            AuthResult with success status, response HTML, and error details.
            Use AuthResult.ok() for success and AuthResult.fail() for failures.
        """
        raise NotImplementedError
