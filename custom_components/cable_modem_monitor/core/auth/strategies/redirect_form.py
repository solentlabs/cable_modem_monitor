"""Form-based authentication with redirect validation (e.g., XB7)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import requests

from ..base import AuthResult, AuthStrategy
from ..types import AuthErrorType

if TYPE_CHECKING:
    from ..configs import AuthConfig, RedirectFormAuthConfig

_LOGGER = logging.getLogger(__name__)


class RedirectFormAuthStrategy(AuthStrategy):
    """Form-based authentication with redirect validation (e.g., XB7)."""

    def login(
        self,
        session: requests.Session,
        base_url: str,
        username: str | None,
        password: str | None,
        config: AuthConfig,
        verbose: bool = False,
    ) -> AuthResult:
        """Submit form and validate redirect."""
        if not username or not password:
            _LOGGER.debug("No credentials provided for RedirectFormAuth")
            return AuthResult.fail(
                AuthErrorType.MISSING_CREDENTIALS,
                "RedirectFormAuth requires username and password",
            )

        from ..configs import RedirectFormAuthConfig

        if not isinstance(config, RedirectFormAuthConfig):
            _LOGGER.error("RedirectFormAuthStrategy requires RedirectFormAuthConfig")
            return AuthResult.fail(
                AuthErrorType.STRATEGY_NOT_CONFIGURED,
                "RedirectFormAuthStrategy requires RedirectFormAuthConfig",
            )

        try:
            response = self._post_login_request(session, base_url, username, password, config)
            if response is None:
                return AuthResult.fail(
                    AuthErrorType.INVALID_CREDENTIALS,
                    "Login request failed",
                )

            if not self._validate_redirect_security(response.url, base_url):
                return AuthResult.fail(
                    AuthErrorType.UNKNOWN_ERROR,
                    "Security violation - redirect to different host",
                )

            return self._handle_login_response(session, base_url, response, config)

        except (requests.exceptions.Timeout, requests.exceptions.ReadTimeout) as e:
            _LOGGER.debug("Login timeout (modem may be busy): %s", str(e))
            return AuthResult.fail(
                AuthErrorType.CONNECTION_FAILED,
                f"Login timeout: {e}",
            )
        except requests.exceptions.ConnectionError as e:
            _LOGGER.warning("Login connection error: %s", str(e))
            return AuthResult.fail(
                AuthErrorType.CONNECTION_FAILED,
                f"Connection error: {e}",
            )
        except requests.exceptions.RequestException as e:
            _LOGGER.warning("Login request failed: %s", str(e))
            _LOGGER.debug("Login exception details:", exc_info=True)
            return AuthResult.fail(
                AuthErrorType.UNKNOWN_ERROR,
                f"Request failed: {e}",
            )
        except Exception as e:
            _LOGGER.error("Unexpected login exception: %s", str(e), exc_info=True)
            return AuthResult.fail(
                AuthErrorType.UNKNOWN_ERROR,
                f"Unexpected error: {e}",
            )

    def _post_login_request(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
        config: RedirectFormAuthConfig,
    ) -> requests.Response | None:
        """Post login credentials and return response."""
        login_url = f"{base_url}{config.login_url}"
        login_data = {
            config.username_field: username,
            config.password_field: password,
        }

        _LOGGER.debug("Posting credentials to %s", login_url)
        response = session.post(login_url, data=login_data, timeout=10, allow_redirects=True, verify=session.verify)

        if response.status_code != 200:
            _LOGGER.error("Login failed with status %s", response.status_code)
            return None

        return response

    def _validate_redirect_security(self, redirect_url: str, base_url: str) -> bool:
        """Validate that redirect stayed on same host for security."""
        redirect_parsed = urlparse(redirect_url)
        base_parsed = urlparse(base_url)

        if redirect_parsed.hostname != base_parsed.hostname:
            _LOGGER.error("Security violation - redirect to different host: %s", redirect_url)
            return False

        return True

    def _handle_login_response(
        self,
        session: requests.Session,
        base_url: str,
        response: requests.Response,
        config: RedirectFormAuthConfig,
    ) -> AuthResult:
        """Handle login response and fetch authenticated page if successful."""
        if config.success_redirect_pattern not in response.url:
            _LOGGER.warning("Unexpected redirect to %s", response.url)
            return AuthResult.fail(
                AuthErrorType.INVALID_CREDENTIALS,
                f"Unexpected redirect to {response.url}",
                response_html=response.text,
            )

        _LOGGER.debug("Login successful, redirected to %s", response.url)
        return self._fetch_authenticated_page(session, base_url, config)

    def _fetch_authenticated_page(
        self, session: requests.Session, base_url: str, config: RedirectFormAuthConfig
    ) -> AuthResult:
        """Fetch the authenticated page after successful login."""
        auth_url = f"{base_url}{config.authenticated_page_url}"
        _LOGGER.debug("Fetching authenticated page: %s", auth_url)
        auth_response = session.get(auth_url, timeout=10, verify=session.verify)

        if auth_response.status_code != 200:
            _LOGGER.error("Failed to fetch authenticated page, status %s", auth_response.status_code)
            return AuthResult.fail(
                AuthErrorType.UNKNOWN_ERROR,
                f"Failed to fetch authenticated page, status {auth_response.status_code}",
                response_html=auth_response.text,
            )

        _LOGGER.info("Successfully authenticated and fetched status page (%s bytes)", len(auth_response.text))
        return AuthResult.ok(auth_response.text)
