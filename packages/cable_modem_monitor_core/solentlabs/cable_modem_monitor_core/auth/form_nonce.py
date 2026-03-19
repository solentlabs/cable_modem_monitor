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

    Generates a random nonce, formats a credential string using the
    configured template, and POSTs to the login endpoint. The response
    is evaluated by text prefix (``Url:`` for success, ``Error:`` for
    failure).

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
            1. Generate a random alphanumeric nonce.
            2. Format the credential string from the template.
            3. POST nonce and credential to the login endpoint.
            4. Parse the text-prefix response for success/error.

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

        # Step 1: Generate nonce
        chars = string.ascii_letters + string.digits
        nonce = "".join(secrets.choice(chars) for _ in range(config.nonce_length))

        # Step 2: Format credential string
        credential = config.credential_format.format(
            nonce=nonce,
            password=password,
            username=username,
        )

        # Step 3: POST to login endpoint
        form_data = {
            config.nonce_field: credential,
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

        # Step 4: Parse text-prefix response
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
