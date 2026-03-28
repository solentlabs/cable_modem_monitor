"""HTML form POST authentication manager.

See MODEM_YAML_SPEC.md ``form`` strategy.
"""

from __future__ import annotations

import base64
import logging
from urllib.parse import urlparse

import requests

from ..models.modem_config.auth import FormAuth
from .base import AuthResult, BaseAuthManager

_logger = logging.getLogger(__name__)


class FormAuthManager(BaseAuthManager):
    """HTML form POST login.

    POSTs credentials to a configured endpoint and evaluates the
    response for success. Supports password encoding (plain or base64),
    hidden form fields, login page pre-fetch, and success detection
    via redirect URL or response body indicator.

    Args:
        config: Validated ``FormAuth`` config from modem.yaml.
    """

    def __init__(self, config: FormAuth) -> None:
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
        """Execute the form login flow.

        Steps:
            1. Pre-fetch login page if configured (to get cookies/nonces).
            2. Build form data with credentials and hidden fields.
            3. POST to the login endpoint.
            4. Evaluate success via redirect or indicator.

        Args:
            session: Session to configure with auth state.
            base_url: Modem base URL.
            username: Username credential.
            password: Password credential.
            timeout: Per-request timeout in seconds.

        Returns:
            AuthResult with login response for auth response reuse.
        """
        config = self._config

        # Step 1: Pre-fetch login page if configured
        if config.login_page:
            try:
                session.get(
                    f"{base_url}{config.login_page}",
                    timeout=timeout,
                )
            except requests.RequestException as e:
                if isinstance(e, requests.ConnectionError | requests.Timeout):
                    raise
                return AuthResult(
                    success=False,
                    error=f"Login page pre-fetch failed: {e}",
                )

        # Step 2: Build form data
        encoded_password = _encode_password(password, config.encoding)
        form_data: dict[str, str] = {
            config.username_field: username,
            config.password_field: encoded_password,
        }
        form_data.update(config.hidden_fields)

        # Step 3: POST to login endpoint
        login_url = f"{base_url}{config.action}"
        try:
            response = session.request(
                config.method,
                login_url,
                data=form_data,
                allow_redirects=True,
                timeout=timeout,
            )
        except requests.RequestException as e:
            if isinstance(e, requests.ConnectionError | requests.Timeout):
                raise
            return AuthResult(
                success=False,
                error=f"Login POST failed: {e}",
            )

        # Step 4: Evaluate success
        error = _check_success(config, response)
        if error:
            return AuthResult(success=False, error=error)

        response_path = urlparse(response.url).path if response.url else ""
        _logger.debug(
            "Form login succeeded: status=%d, url=%s, cookies=%s",
            response.status_code,
            response_path,
            list(session.cookies.keys()),
        )

        return AuthResult(
            success=True,
            response=response,
            response_url=response_path,
        )


def _encode_password(password: str, encoding: str) -> str:
    """Encode the password per the configured encoding."""
    if encoding == "base64":
        return base64.b64encode(password.encode("utf-8")).decode("ascii")
    return password


def _check_success(config: FormAuth, response: requests.Response) -> str:
    """Check if the login response indicates success.

    Returns an error message on failure, empty string on success.
    """
    if config.success is None:
        # No explicit success criteria — accept any non-401
        if response.status_code == 401:
            return "Login returned 401 Unauthorized"
        return ""

    if config.success.redirect:
        response_path = urlparse(response.url).path if response.url else ""
        if config.success.redirect not in response_path:
            return (
                f"Login redirect mismatch: expected path containing "
                f"'{config.success.redirect}', got '{response_path}'"
            )

    if config.success.indicator and config.success.indicator not in response.text:
        return f"Login success indicator '{config.success.indicator}' not found in response body"

    return ""
