"""URL token authentication manager.

See MODEM_YAML_SPEC.md ``url_token`` strategy.
"""

from __future__ import annotations

import base64
import logging
from urllib.parse import urlparse

import requests

from ..models.modem_config.auth import UrlTokenAuth
from ..models.modem_config.session import SessionConfig
from .base import AuthResult, BaseAuthManager

_logger = logging.getLogger(__name__)


class UrlTokenAuthManager(BaseAuthManager):
    """Credentials encoded in URL query string.

    The login request encodes credentials as a base64 token in the URL.
    The response sets a session cookie and may contain a server-issued
    token for subsequent data page requests.

    For data requests, the loader appends
    ``?{token_prefix}{session_token}`` to each URL.

    Args:
        config: Validated ``UrlTokenAuth`` config from modem.yaml.
        session_config: Session config (for ``cookie_name``,
            ``token_prefix``).
    """

    def __init__(
        self,
        config: UrlTokenAuth,
        session_config: SessionConfig | None = None,
    ) -> None:
        self._config = config
        self._cookie_name = session_config.cookie_name if session_config else ""
        self._token_prefix = session_config.token_prefix if session_config else ""

    def authenticate(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
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

        Returns:
            AuthResult with ``auth_context["url_token"]`` for the loader.
        """
        config = self._config
        timeout = getattr(self, "_timeout", 10)

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

        # Step 4: Extract session token from cookie
        url_token = ""
        if self._cookie_name:
            url_token = session.cookies.get(self._cookie_name, "") or ""

        # Step 5: Set Basic auth header for data requests if configured
        if config.auth_header_data:
            session.auth = (username, password)

        response_path = urlparse(response.url).path if response.url else ""
        _logger.debug(
            "URL token login succeeded: token=%s, cookies=%s",
            bool(url_token),
            list(session.cookies.keys()),
        )

        auth_context: dict[str, str] = {}
        if url_token:
            auth_context["url_token"] = url_token

        return AuthResult(
            success=True,
            auth_context=auth_context,
            response=response,
            response_url=response_path,
        )
