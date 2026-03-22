"""URL token authentication manager.

See MODEM_YAML_SPEC.md ``url_token`` strategy.
"""

from __future__ import annotations

import base64
import logging
from urllib.parse import urlparse

import requests

from ..models.modem_config.auth import UrlTokenAuth
from .base import AuthResult, BaseAuthManager

_logger = logging.getLogger(__name__)


class UrlTokenAuthManager(BaseAuthManager):
    """Credentials encoded in URL query string.

    The login request encodes credentials as a base64 token in the URL.
    The response sets a session cookie and may contain a server-issued
    token for subsequent data page requests.

    For data requests, the runner extracts the session token from
    cookies using ``session_config.cookie_name`` and passes it to
    the loader.

    Args:
        config: Validated ``UrlTokenAuth`` config from modem.yaml.
    """

    def __init__(self, config: UrlTokenAuth) -> None:
        self._config = config

    def authenticate(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
        *,
        timeout: int = 10,
    ) -> AuthResult:
        """Execute the URL token login flow.

        Steps:
            1. Encode credentials as base64 token.
            2. Build login URL with token in query string.
            3. GET the login URL (optionally with AJAX header).
            4. Extract session token from cookie.
            5. Optionally set Basic auth header for data requests.

        Args:
            session: Session to configure with auth state.
            base_url: Modem base URL.
            username: Username credential.
            password: Password credential.
            timeout: Per-request timeout in seconds.

        Returns:
            AuthResult with login response for the runner to extract
            the session token from cookies.
        """
        config = self._config

        # Step 1: Encode credentials
        credential = base64.b64encode(
            f"{username}:{password}".encode(),
        ).decode("ascii")

        # Step 2: Build login URL
        login_url = f"{base_url}{config.login_page}"
        if config.login_prefix:
            login_url = f"{login_url}?{config.login_prefix}{credential}"
        else:
            login_url = f"{login_url}?{credential}"

        # Step 3: GET login URL
        headers: dict[str, str] = {}
        if config.ajax_login:
            headers["X-Requested-With"] = "XMLHttpRequest"

        try:
            response = session.get(
                login_url,
                headers=headers,
                allow_redirects=True,
                timeout=timeout,
            )
        except requests.RequestException as e:
            return AuthResult(
                success=False,
                error=f"URL token login failed: {e}",
            )

        # Check success indicator
        if config.success_indicator and config.success_indicator not in response.text:
            return AuthResult(
                success=False,
                error=f"Login success indicator '{config.success_indicator}' not found",
            )

        # Set Basic auth header for data requests if configured
        if config.auth_header_data:
            session.auth = (username, password)

        response_path = urlparse(response.url).path if response.url else ""
        _logger.info(
            "URL token login succeeded: cookies=%s",
            list(session.cookies.keys()),
        )

        return AuthResult(
            success=True,
            response=response,
            response_url=response_path,
        )
