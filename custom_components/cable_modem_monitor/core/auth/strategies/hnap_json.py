"""HNAP JSON authentication strategy with HMAC-MD5 challenge-response.

Used by modems like MB8611 and S33 that use JSON-formatted HNAP requests
with a two-step challenge-response authentication protocol.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import requests

from ..base import AuthResult, AuthStrategy
from ..types import AuthErrorType

if TYPE_CHECKING:
    from ..configs import AuthConfig
    from ..hnap import HNAPJsonRequestBuilder

_LOGGER = logging.getLogger(__name__)


class HNAPJsonAuthStrategy(AuthStrategy):
    """HNAP JSON authentication with HMAC-MD5 challenge-response.

    This strategy wraps HNAPJsonRequestBuilder to provide challenge-response
    authentication for modems like MB8611 and S33.

    After successful login, the builder is stored internally and can be
    accessed via the `builder` property for making authenticated HNAP calls.
    """

    def __init__(self) -> None:
        """Initialize the strategy."""
        self._builder: HNAPJsonRequestBuilder | None = None

    @property
    def builder(self) -> HNAPJsonRequestBuilder | None:
        """Get the HNAP request builder after successful authentication.

        Returns:
            HNAPJsonRequestBuilder if authenticated, None otherwise.
            The builder can be used to make authenticated HNAP calls.
        """
        return self._builder

    def login(
        self,
        session: requests.Session,
        base_url: str,
        username: str | None,
        password: str | None,
        config: AuthConfig,
        verbose: bool = False,
    ) -> AuthResult:
        """Perform HNAP JSON authentication with challenge-response.

        Creates an HNAPJsonRequestBuilder and performs the two-step
        challenge-response login. On success, stores the builder for
        subsequent authenticated requests.

        Args:
            session: requests.Session object (modified in-place)
            base_url: Modem base URL (e.g., "https://192.168.100.1")
            username: Username for authentication
            password: Password for authentication
            config: HNAPAuthConfig with endpoint, namespace, empty_action_value
            verbose: If True, log at INFO level

        Returns:
            AuthResult with success status and response data.
        """
        log = _LOGGER.info if verbose else _LOGGER.debug

        if not username or not password:
            _LOGGER.warning("HNAP JSON auth configured but no credentials provided")
            return AuthResult.fail(
                AuthErrorType.MISSING_CREDENTIALS,
                "HNAP auth requires username and password",
            )

        from ..configs import HNAPAuthConfig

        if not isinstance(config, HNAPAuthConfig):
            _LOGGER.error("HNAPJsonAuthStrategy requires HNAPAuthConfig")
            return AuthResult.fail(
                AuthErrorType.STRATEGY_NOT_CONFIGURED,
                "HNAPJsonAuthStrategy requires HNAPAuthConfig",
            )

        # Import builder here to avoid circular imports
        from ..hnap import HNAPJsonRequestBuilder

        # Create builder with config
        self._builder = HNAPJsonRequestBuilder(
            endpoint=config.endpoint,
            namespace=config.namespace,
            empty_action_value=config.empty_action_value,
        )

        log(
            "HNAP JSON auth: endpoint=%s, namespace=%s",
            config.endpoint,
            config.namespace,
        )

        try:
            success, response_text = self._builder.login(session, base_url, username, password)

            if success:
                log("HNAP JSON authentication successful")
                return AuthResult.ok(response_text)
            else:
                _LOGGER.warning("HNAP JSON authentication failed")
                self._builder = None
                # Check for session timeout indicators in response
                if response_text and self._is_session_timeout(response_text):
                    return AuthResult.fail(
                        AuthErrorType.SESSION_EXPIRED,
                        "Session expired - please retry",
                        response_html=response_text,
                        requires_retry=True,
                    )
                return AuthResult.fail(
                    AuthErrorType.INVALID_CREDENTIALS,
                    "HNAP authentication rejected - check username/password",
                    response_html=response_text,
                )

        except requests.exceptions.Timeout as e:
            _LOGGER.warning("HNAP JSON auth timeout: %s", e)
            self._builder = None
            return AuthResult.fail(
                AuthErrorType.CONNECTION_FAILED,
                f"HNAP auth timeout: {e}",
            )
        except requests.exceptions.ConnectionError as e:
            _LOGGER.warning("HNAP JSON auth connection error: %s", e)
            self._builder = None
            return AuthResult.fail(
                AuthErrorType.CONNECTION_FAILED,
                f"HNAP connection error: {e}",
            )
        except Exception as e:
            _LOGGER.warning("HNAP JSON auth failed with exception: %s", e)
            self._builder = None
            return AuthResult.fail(
                AuthErrorType.CONNECTION_FAILED,
                f"HNAP auth error: {e}",
            )

    def _is_session_timeout(self, response_text: str) -> bool:
        """Check if response indicates session timeout."""
        timeout_indicators = [
            "UN-AUTH",
            "session timeout",
            "session expired",
            "not logged in",
        ]
        lower_text = response_text.lower()
        return any(indicator.lower() in lower_text for indicator in timeout_indicators)
