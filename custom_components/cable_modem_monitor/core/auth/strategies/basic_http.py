"""HTTP Basic Authentication strategy (RFC 7617).

This strategy sets HTTP Basic Auth credentials on the session and verifies
they work by making a test request to the base URL.

Note: Basic auth is header-based (per-request via session.auth), not
session-based. We do NOT return response HTML - the scraper will fetch
the actual data page with the auth header. Returning HTML from the root
page would break modems like TC4400 where root is a frameset with no
channel data.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..base import AuthResult, AuthStrategy
from ..types import AuthErrorType

if TYPE_CHECKING:
    import requests

    from ..configs import AuthConfig

_LOGGER = logging.getLogger(__name__)

# Default timeout for verification request
DEFAULT_TIMEOUT = 10


class BasicHttpAuthStrategy(AuthStrategy):
    """HTTP Basic Authentication strategy (RFC 7617).

    Sets session.auth for all subsequent requests and verifies
    credentials work by making a test request.
    """

    def login(
        self,
        session: requests.Session,
        base_url: str,
        username: str | None,
        password: str | None,
        config: AuthConfig,
        verbose: bool = False,
    ) -> AuthResult:
        """Set up HTTP Basic Auth on the session and verify it works.

        Args:
            session: requests.Session to configure
            base_url: Modem base URL for verification request
            username: Username for authentication
            password: Password for authentication
            config: Auth configuration (not used for basic auth)
            verbose: If True, log at INFO level

        Returns:
            AuthResult with success status. Note: Does NOT return HTML
            because basic auth is header-based, not session-based.
        """
        log = _LOGGER.info if verbose else _LOGGER.debug

        if not username or not password:
            _LOGGER.warning("Basic auth configured but no credentials provided")
            return AuthResult.fail(
                AuthErrorType.MISSING_CREDENTIALS,
                "Basic auth requires username and password",
            )

        # Attach auth to session (sent with every request)
        session.auth = (username, password)
        log("Basic auth credentials set on session")

        # Verify auth works by fetching base URL
        return self._verify_credentials(session, base_url, log)

    def _verify_credentials(
        self,
        session: requests.Session,
        base_url: str,
        log,
    ) -> AuthResult:
        """Verify credentials work by making a test request.

        Note: We do NOT return response.text because basic auth is per-request
        (header-based via session.auth), not session-based. The scraper will
        fetch the actual data page with the auth header.
        """
        try:
            response = session.get(base_url, timeout=DEFAULT_TIMEOUT)

            if response.status_code == 200:
                log("Basic auth verified successfully")
                return AuthResult.ok()  # No HTML - scraper fetches data page

            if response.status_code == 401:
                _LOGGER.warning("Basic auth failed - invalid credentials (401)")
                session.auth = None  # Clear invalid credentials
                return AuthResult.fail(
                    AuthErrorType.INVALID_CREDENTIALS,
                    "Invalid username or password (HTTP 401)",
                )

            # Other status codes - auth might still work, let scraper try
            log("Basic auth response: %d", response.status_code)
            return AuthResult.ok()  # No HTML - scraper fetches data page

        except Exception as e:
            _LOGGER.warning("Basic auth verification failed: %s", e)
            return AuthResult.fail(
                AuthErrorType.CONNECTION_FAILED,
                f"Connection failed during auth: {e}",
            )
