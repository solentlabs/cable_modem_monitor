"""URL-based token authentication with session cookie strategy.

Used by modems that:
1. Accept base64-encoded credentials in the URL query parameter
2. Return the session token in the RESPONSE BODY (not cookie value!)
3. Require the session token appended to URLs for authenticated requests

Important: The token for subsequent URLs comes from the login response BODY,
not the cookie value. The typical JavaScript pattern is:

    success: function (result) {
        var token = result;  // Response body IS the token
        window.location.href = "/page.html?ct_" + token;
    }
"""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING

from ..base import AuthResult, AuthStrategy, get_cookie_safe
from ..types import AuthErrorType

if TYPE_CHECKING:
    import requests

    from ..configs import UrlTokenSessionConfig

_LOGGER = logging.getLogger(__name__)


class UrlTokenSessionStrategy(AuthStrategy):
    """URL-based token auth with session cookie strategy.

    Auth flow:
    1. Build base64 token from credentials
    2. Send login request with token in URL and Authorization header
    3. Extract session token from RESPONSE BODY (not cookie!)
    4. Fetch data page with session token in URL (?ct_<token>)
    5. Return authenticated HTML

    Important: The ct_ token comes from the login response body, not the
    cookie value. The cookie is set for session tracking but the URL token
    is the response body text itself.
    """

    def login(
        self,
        session: requests.Session,
        base_url: str,
        username: str | None,
        password: str | None,
        config,
        verbose: bool = False,
    ) -> AuthResult:
        """Authenticate using URL-based token with session cookie."""
        if not username or not password:
            _LOGGER.debug("No credentials provided for URL token auth, skipping")
            return AuthResult.ok()

        from ..configs import UrlTokenSessionConfig

        if not isinstance(config, UrlTokenSessionConfig):
            _LOGGER.error("UrlTokenSessionStrategy requires UrlTokenSessionConfig")
            return AuthResult.fail(
                AuthErrorType.STRATEGY_NOT_CONFIGURED,
                "UrlTokenSessionStrategy requires UrlTokenSessionConfig",
            )

        try:
            return self._execute_auth(session, base_url, username, password, config)
        except Exception as e:
            _LOGGER.error("URL token auth: Error during login: %s", e)
            return AuthResult.fail(
                AuthErrorType.CONNECTION_FAILED,
                f"URL token auth error: {e}",
            )

    def _execute_auth(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
        config: UrlTokenSessionConfig,
    ) -> AuthResult:
        """Execute the authentication flow."""
        # Build base64 token: base64(username:password)
        auth_token = base64.b64encode(f"{username}:{password}".encode()).decode()

        # Send login request - returns (result, session_token_from_body)
        result, session_token = self._send_login_request(session, base_url, auth_token, config)
        if not result.success or result.response_html:
            return result

        # Login succeeded but no data yet - fetch data page using response body token
        return self._fetch_data_page(session, base_url, auth_token, session_token, config)

    def _send_login_request(
        self,
        session: requests.Session,
        base_url: str,
        token: str,
        config: UrlTokenSessionConfig,
    ) -> tuple[AuthResult, str | None]:
        """Send login request and extract session token from response body.

        Returns:
            Tuple of (AuthResult, session_token). The session_token is extracted
            from the response BODY, which is how the modem's JavaScript works.
        """
        login_url = f"{base_url}{config.login_page}?{config.login_prefix}{token}"
        _LOGGER.debug("URL token auth: Attempting login to %s", base_url)

        # Clear any existing session cookie before login (Issue #81)
        # This matches browser behavior: eraseCookie("sessionId") before $.ajax login
        # Without this, the modem rejects re-login attempts with 401 because
        # it sees a login request while a session is already active.
        if config.session_cookie_name in session.cookies:
            del session.cookies[config.session_cookie_name]
            _LOGGER.debug("URL token auth: Cleared existing %s cookie before login", config.session_cookie_name)

        # Build login headers
        headers: dict[str, str] = {"Authorization": f"Basic {token}"}
        if config.ajax_login:
            headers["X-Requested-With"] = "XMLHttpRequest"
            _LOGGER.debug("URL token auth: Using AJAX-style login (X-Requested-With)")

        response = session.get(login_url, headers=headers, timeout=10, verify=False)

        if response.status_code != 200:
            return self._handle_login_error(response), None

        # Check if we got data directly in login response
        if config.success_indicator in response.text:
            _LOGGER.info("URL token auth: Got data directly from login")
            return AuthResult.ok(response.text), None

        # Login OK but no data - extract session token from response body
        # URL token auth returns the session token as plain text in the response body
        session_token = response.text.strip() if response.text else None

        if session_token:
            _LOGGER.debug("URL token auth: Got session token from response body (%d chars)", len(session_token))
        else:
            _LOGGER.warning("URL token auth: No session token in response body")

        return AuthResult.ok(), session_token

    def _handle_login_error(self, response: requests.Response) -> AuthResult:
        """Handle non-200 login response."""
        _LOGGER.warning("URL token auth: Login returned status %d", response.status_code)
        if response.status_code == 401:
            return AuthResult.fail(
                AuthErrorType.INVALID_CREDENTIALS,
                "Invalid credentials (HTTP 401)",
                response_html=response.text,
            )
        return AuthResult.fail(
            AuthErrorType.UNKNOWN_ERROR,
            f"Login returned HTTP {response.status_code}",
            response_html=response.text,
        )

    def _fetch_data_page(
        self,
        session: requests.Session,
        base_url: str,
        auth_token: str,
        session_token: str | None,
        config: UrlTokenSessionConfig,
    ) -> AuthResult:
        """Fetch data page using session token from login response body.

        Args:
            session: requests Session with cookies
            base_url: Modem base URL
            auth_token: Base64 auth token (for Authorization header if needed)
            session_token: Token from login response body (preferred)
            config: Auth configuration
        """
        # Use token from response body; fall back to cookie only if not provided
        if not session_token:
            session_token = get_cookie_safe(session, config.session_cookie_name)
            if session_token:
                _LOGGER.debug("URL token auth: Using token from cookie (fallback)")

        if not session_token:
            _LOGGER.warning("URL token auth: No session token available")
            return AuthResult.ok()  # Return success to allow fallback

        _LOGGER.debug("URL token auth: Fetching data page with session token")

        data_url = f"{base_url}{config.data_page}?{config.token_prefix}{session_token}"

        # Build data request headers - only include Authorization if configured
        # (real browsers don't send Authorization on the redirect, just cookies)
        headers: dict[str, str] = {}
        if config.auth_header_data:
            headers["Authorization"] = f"Basic {auth_token}"

        data_response = session.get(data_url, headers=headers, timeout=10, verify=False)

        if data_response.status_code == 200 and config.success_indicator in data_response.text:
            _LOGGER.info("URL token auth: Authentication successful")
            # Store session token in result for subsequent page fetches (Issue #81)
            return AuthResult.ok(data_response.text, session_token=session_token)

        _LOGGER.warning(
            "URL token auth: Data fetch returned %d, has indicator: %s",
            data_response.status_code,
            config.success_indicator in data_response.text,
        )
        return AuthResult.ok()  # Return success to allow fallback
