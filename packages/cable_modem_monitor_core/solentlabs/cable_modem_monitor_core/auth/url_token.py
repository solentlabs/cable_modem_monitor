"""URL token authentication manager.

See MODEM_YAML_SPEC.md ``url_token`` strategy.
"""

from __future__ import annotations

import base64
import logging
from urllib.parse import urlparse

import requests

from ..models.modem_config.auth import UrlTokenAuth
from .base import AuthContext, AuthResult, BaseAuthManager

_logger = logging.getLogger(__name__)


class UrlTokenAuthManager(BaseAuthManager):
    """Credentials encoded in URL query string.

    The login request encodes credentials as a base64 token in the URL.
    The response may contain a server-issued session token in the body
    (preferred) or set a session cookie (fallback).

    ``success_indicator`` serves dual purpose:
    1. **Data page detection:** Body contains indicator → body is the
       data page, no token to extract.
    2. **Token extraction gate:** Body does not contain indicator →
       body is the session token.
    3. **Empty body fallback:** Fall back to ``cookie_name``.

    Pre-login cookie clearing: if ``cookie_name`` is configured and
    the cookie exists in the session, it is deleted before the login
    request — matching the browser's ``eraseCookie()`` behavior.

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
        log_level: int = logging.DEBUG,
    ) -> AuthResult:
        """Execute the URL token login flow.

        Args:
            session: Session to configure with auth state.
            base_url: Modem base URL.
            username: Username credential.
            password: Password credential.
            timeout: Per-request timeout in seconds.
            log_level: Log level for non-error messages.

        Returns:
            AuthResult with auth_context.url_token for the collector
            to pass to the loader.
        """
        # Clear stale session cookie before login (G-2)
        self._clear_stale_cookie(session, log_level)

        # Send login request
        response = self._send_login_request(
            session,
            base_url,
            username,
            password,
            timeout=timeout,
        )
        if isinstance(response, AuthResult):
            return response  # Error occurred

        # Extract token from response (G-1)
        return self._process_response(
            session,
            response,
            username,
            password,
            log_level,
        )

    def _clear_stale_cookie(
        self,
        session: requests.Session,
        log_level: int,
    ) -> None:
        """Clear stale session cookie before login (G-2)."""
        config = self._config
        if config.cookie_name and config.cookie_name in session.cookies:
            del session.cookies[config.cookie_name]
            _logger.log(
                log_level,
                "URL token auth: cleared stale %s cookie before login",
                config.cookie_name,
            )

    def _send_login_request(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
        *,
        timeout: int,
    ) -> requests.Response | AuthResult:
        """Build and send the login GET request.

        Returns the response on success, or an AuthResult on failure.
        """
        config = self._config

        # Encode credentials
        credential = base64.b64encode(
            f"{username}:{password}".encode(),
        ).decode("ascii")

        # Build login URL
        login_url = f"{base_url}{config.login_page}"
        if config.login_prefix:
            login_url = f"{login_url}?{config.login_prefix}{credential}"
        else:
            login_url = f"{login_url}?{credential}"

        # GET login URL
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
            if isinstance(e, requests.ConnectionError | requests.Timeout):
                raise
            return AuthResult(
                success=False,
                error=f"URL token login failed: {e}",
            )

        if response.status_code != 200:
            return AuthResult(
                success=False,
                error=f"URL token login returned HTTP {response.status_code}",
            )

        return response

    def _process_response(
        self,
        session: requests.Session,
        response: requests.Response,
        username: str,
        password: str,
        log_level: int,
    ) -> AuthResult:
        """Extract session token and build the auth result (G-1).

        Uses ``success_indicator`` as a response type discriminator:
        - Body contains indicator → data page response (no token).
        - Body does not contain indicator → body is the token string.
        - Empty body → fall back to cookie via ``cookie_name``.
        """
        config = self._config
        body = response.text.strip() if response.text else ""

        # Data page detection: indicator present → body is the data page
        if config.success_indicator and config.success_indicator in response.text:
            response_path = urlparse(response.url).path if response.url else ""
            return AuthResult(
                success=True,
                response=response,
                response_url=response_path,
            )

        # Token extraction: body without indicator = token string
        url_token = self._extract_token(session, body, log_level)

        # Set Basic auth header for data requests if configured
        if config.auth_header_data:
            session.auth = (username, password)

        response_path = urlparse(response.url).path if response.url else ""
        _logger.log(
            log_level,
            "URL token login succeeded: cookies=%s",
            list(session.cookies.keys()),
        )

        return AuthResult(
            success=True,
            auth_context=AuthContext(url_token=url_token),
            response=response,
            response_url=response_path,
        )

    def _extract_token(
        self,
        session: requests.Session,
        body: str,
        log_level: int,
    ) -> str:
        """Extract session token from body or cookie.

        Preference: body → cookie → empty string.
        """
        config = self._config

        if body:
            _logger.log(
                log_level,
                "URL token auth: extracted token from body (%d chars)",
                len(body),
            )
            return body

        if config.cookie_name:
            cookie_val = session.cookies.get(config.cookie_name, "") or ""
            if cookie_val:
                _logger.log(
                    log_level,
                    "URL token auth: extracted token from cookie (fallback)",
                )
                return cookie_val

        return ""
