"""Form POST with client-generated nonce authentication manager.

See MODEM_YAML_SPEC.md ``form_nonce`` strategy.
"""

from __future__ import annotations

import logging
import secrets
import string

import requests

from ..models.modem_config.auth import FormNonceAuth
from .base import AuthResult, BaseAuthManager

_logger = logging.getLogger(__name__)


class FormNonceAuthManager(BaseAuthManager):
    """Form POST with client-generated nonce.

    Generates a random nonce and POSTs username, password, and nonce
    as three separate form fields. The response is evaluated by text
    prefix (``Url:`` for success, ``Error:`` for failure).

    Args:
        config: Validated ``FormNonceAuth`` config from modem.yaml.
    """

    def __init__(self, config: FormNonceAuth) -> None:
        self._config = config

    def authenticate(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
    ) -> AuthResult:
        """Execute the nonce-based login flow.

        Steps:
            1. Generate a random numeric nonce.
            2. POST username, password, and nonce as separate form fields.
            3. Parse the text-prefix response for success/error.

        Args:
            session: Session to configure with auth state.
            base_url: Modem base URL.
            username: Username credential.
            password: Password credential.

        Returns:
            AuthResult with login response.
        """
        config = self._config
        timeout = getattr(self, "_timeout", 10)

        # Step 1: Generate nonce (digits only, per spec)
        nonce = "".join(secrets.choice(string.digits) for _ in range(config.nonce_length))

        # Step 2: POST three separate form fields
        form_data = {
            config.username_field: username,
            config.password_field: password,
            config.nonce_field: nonce,
        }
        login_url = f"{base_url}{config.action}"

        try:
            response = session.post(
                login_url,
                data=form_data,
                allow_redirects=False,
                timeout=timeout,
            )
        except requests.RequestException as e:
            return AuthResult(
                success=False,
                error=f"Nonce login POST failed: {e}",
            )

        # Step 3: Parse text-prefix response
        text = response.text.strip()

        if text.startswith(config.error_prefix):
            error_msg = text[len(config.error_prefix) :].strip()
            return AuthResult(
                success=False,
                error=f"Login rejected: {error_msg}",
            )

        response_url = ""
        if text.startswith(config.success_prefix):
            response_url = text[len(config.success_prefix) :].strip()

        _logger.debug(
            "Nonce login succeeded: status=%d, redirect=%s",
            response.status_code,
            response_url,
        )

        return AuthResult(
            success=True,
            response=response,
            response_url=response_url,
        )
