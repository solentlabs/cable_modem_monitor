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

    Some modems set the same cookie name
    with different paths (e.g., "/" and "/cmconnectionstatus.html"). This
    function handles that edge case by:
    1. Filtering out empty values (some firmware sets empty cookie on landing page)
    2. Preferring root path "/" over page-specific paths
    3. Returning first match if no root path found

    Args:
        session: requests.Session with cookies
        name: Cookie name to look up

    Returns:
        Cookie value if found, None otherwise
    """

    # Collect all cookies with matching name, filtering out empty values
    # Some modems set empty cookie on landing page, then real value on
    # login - we want the real value
    matches = [(c.value, c.path) for c in session.cookies if c.name == name and c.value]

    if len(matches) == 0:
        return None

    if len(matches) == 1:
        return matches[0][0]

    # 2+ cookies: prefer root path "/" over specific paths
    for value, path in matches:
        if path == "/":
            return value

    # No root path, return first match
    _LOGGER.debug(
        "%d %s cookies with non-root paths %s, using first",
        len(matches),
        name,
        [m[1] for m in matches],
    )
    return matches[0][0]


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
        session_token: Session token for subsequent requests (URL token auth).
            This is the token from the response body that should be used for
            ?ct_<token> in subsequent page fetches. Issue #81: This token is
            different from the cookie value on some firmware.

    Note:
        This class is iterable for backward compatibility with code that
        unpacks the result as `success, html = handler.authenticate(...)`.
    """

    success: bool
    response_html: str | None = None
    error_type: AuthErrorType = AuthErrorType.NONE
    error_message: str | None = None
    requires_retry: bool = False
    session_token: str | None = None

    def __iter__(self):
        """Allow unpacking as (success, html) for backward compatibility."""
        return iter((self.success, self.response_html))

    @classmethod
    def ok(cls, response_html: str | None = None, session_token: str | None = None) -> AuthResult:
        """Create successful result.

        Args:
            response_html: HTML from authenticated page (if applicable)
            session_token: Session token for subsequent requests (URL token auth)
        """
        return cls(success=True, response_html=response_html, session_token=session_token)

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
